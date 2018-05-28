'''
The disparate session (Session) is for making requests to multiple locations.
'''

from abc import ABCMeta, abstractmethod
from copy import copy
from functools import partialmethod
from urllib.parse import urlparse, urlunparse

from h11 import RemoteProtocolError

from multio import asynclib

from .cookie_utils import CookieTracker
from .errors import RequestTimeout, BadHttpResponse
from .req_structs import SocketQ
from .request_object import Request
from .utils import get_netloc_port

__all__ = ['Session']


class BaseSession(metaclass=ABCMeta):
    '''
    The base class for asks' sessions.
    Contains methods for creating sockets, figuring out which type of
    socket to create, and all of the HTTP methods ('GET', 'POST', etc.)
    '''

    def __init__(self, headers=None):
        '''
        Args:
            headers (dict): Headers to be applied to all requests.
                headers set by http method call will take precedence and
                overwrite headers set by the headers arg.
        '''
        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}

        self.encoding = None
        self.source_address = None
        self._cookie_tracker_obj = None

    @property
    @abstractmethod
    def sema(self):
        """
        A semaphore-like context manager.
        """
        ...

    async def _open_connection_http(self, location):
        '''
        Creates a normal async socket, returns it.
        Args:
            location (tuple(str, int)): A tuple of net location (eg
                '127.0.0.1' or 'example.org') and port (eg 80 or 25000).
        '''
        sock = await asynclib.open_connection(location[0],
                                              location[1],
                                              ssl=False,
                                              source_addr=self.source_address)
        sock._active = True
        return sock

    async def _open_connection_https(self, location):
        '''
        Creates an async SSL socket, returns it.
        Args:
            location (tuple(str, int)): A tuple of net location (eg
                '127.0.0.1' or 'example.org') and port (eg 80 or 25000).
        '''
        sock = await asynclib.open_connection(location[0],
                                              location[1],
                                              ssl=True,
                                              server_hostname=location[0],
                                              source_addr=self.source_address)
        sock._active = True
        return sock

    async def _connect(self, host_loc):
        '''
        Simple enough stuff to figure out where we should connect, and creates
        the appropriate connection.
        '''
        scheme, netloc, path, parameters, query, fragment = urlparse(
            host_loc)
        if parameters or query or fragment:
            raise ValueError('Supplied info beyond scheme, netloc.' +
                             ' Host should be top level only: ', path)

        netloc, port = get_netloc_port(scheme, netloc)
        if scheme == 'http':
            return await self._open_connection_http(
                (netloc, int(port))), port
        else:
            return await self._open_connection_https(
                (netloc, int(port))), port

    async def request(self, method, url=None, *, path='', retries=1, **kwargs):
        '''
        This is the template for all of the `http method` methods for
        the Session.

        Args:
            method (str): A http method, such as 'GET' or 'POST'.
            url (str): The url the request should be made to.
            path (str): An optional kw-arg for use in Session method calls,
                for specifying a particular path. Usually to be used in
                conjunction with the base_location/endpoint paradigm.
            kwargs: Any number of the following:
                        data (dict or str): Info to be processed as a
                            body-bound query.
                        params (dict or str): Info to be processed as a
                            url-bound query.
                        headers (dict): User HTTP headers to be used in the
                            request.
                        encoding (str): The str representation of the codec to
                            process the request under.
                        json (dict): A dict to be formatted as json and sent in
                            the request body.
                        files (dict): A dict of `filename:filepath`s to be sent
                            as multipart.
                        cookies (dict): A dict of `name:value` cookies to be
                            passed in request.
                        callback (func): A callback function to be called on
                            each bytechunk of of the response body.
                        timeout (int or float): A numeric representation of the
                            longest time to wait on a complete response once a
                            request has been sent.
                        max_redirects (int): The maximum number of redirects
                            allowed.
                        persist_cookies (True or None): Passing True
                            instantiates a CookieTracker object to manage the
                            return of cookies to the server under the relevant
                            domains.
                        auth (child of AuthBase): An object for handling auth
                            construction.

        When you call something like Session.get() or asks.post(), you're
        really calling a partial method that has the 'method' argument
        pre-completed.
        '''
        timeout = kwargs.get('timeout', None)
        req_headers = kwargs.pop('headers', None)

        if self.headers is not None:
            headers = copy(self.headers)
        if req_headers is not None:
            headers.update(req_headers)
        req_headers = headers

        async with self._sema:

            if url is None:
                url = self._make_url() + path

            retry = False

            try:
                sock = await self._grab_connection(url)
                port = sock.port

                req_obj = Request(self,
                                  method,
                                  url,
                                  port,
                                  headers=req_headers,
                                  encoding=self.encoding,
                                  sock=sock,
                                  persist_cookies=self._cookie_tracker_obj,
                                  **kwargs)

                if timeout is None:
                    sock, r = await req_obj.make_request()
                else:
                    sock, r = await self.timeout_manager(timeout, req_obj)

                if sock is not None:
                    try:
                        if r.headers['connection'].lower() == 'close':
                            await sock.close()
                            sock._active = False
                    except KeyError:
                        pass
                    await self._replace_connection(sock)

            except (RemoteProtocolError, AssertionError) as e:
                await sock.close()
                sock._active = False
                await self._replace_connection(sock)
                raise BadHttpResponse('Invalid HTTP response from server.') from e

            except ConnectionError as e:
                if retries > 0:
                    retry = True
                    retries -= 1
                else:
                    raise e

        if retry:
            return (await self.request(method,
                                       url,
                                       path=path,
                                       retries=retries,
                                       headers=headers,
                                       **kwargs))

        return r

    # These be the actual http methods!
    # They are partial methods of `request`. See the `request` docstring
    # above for information.
    get = partialmethod(request, 'GET')
    head = partialmethod(request, 'HEAD')
    post = partialmethod(request, 'POST')
    put = partialmethod(request, 'PUT')
    delete = partialmethod(request, 'DELETE')
    options = partialmethod(request, 'OPTIONS')

    async def timeout_manager(self, timeout, req_obj):
        try:
            async with asynclib.timeout_after(timeout):
                sock, r = await req_obj.make_request()
        except asynclib.TaskTimeout as e:
            raise RequestTimeout from e
        return sock, r

    @abstractmethod
    def _make_url(self):
        """
        A method who's result is concated with a uri path.
        """
        ...

    @abstractmethod
    async def _grab_connection(self, url):
        """
        A method that will return a socket-like object.
        """
        ...

    @abstractmethod
    async def _replace_connection(self, sock):
        """
        A method that will accept a socket-like object.
        """
        ...


class Session(BaseSession):
    '''
    The Session class, for handling piles of requests.

    This class inherits from BaseSession, where all of the 'http method'
    methods are defined.
    '''

    def __init__(self,
                 base_location=None,
                 endpoint=None,
                 headers=None,
                 encoding='utf-8',
                 persist_cookies=None,
                 connections=1):
        '''
        Args:
            encoding (str): The encoding asks'll try to use on response bodies.
            persist_cookies (bool): Passing True turns on browserishlike
                stateful cookie behaviour, returning cookies to the host when
                appropriate.
            connections (int): The max number of concurrent connections to the
                host asks will allow its self to have. The default number of
                connections is 1. You may increase this value as you see fit.
        '''
        super().__init__(headers)
        self.encoding = encoding
        self.base_location = base_location
        self.endpoint = endpoint

        if persist_cookies is True:
            self._cookie_tracker_obj = CookieTracker()
        else:
            self._cookie_tracker_obj = persist_cookies

        self._conn_pool = SocketQ()
        self._checked_out_sockets = SocketQ()

        self._sema = asynclib.Semaphore(connections)

    @property
    def sema(self):
        return self._sema

    def _checkout_connection(self, host_loc):
        try:
            index = self._conn_pool.index(host_loc)
        except ValueError:
            return None

        sock = self._conn_pool.pull(index)
        self._checked_out_sockets.append(sock)
        return sock

    async def _replace_connection(self, sock):
        if sock._active:
            self._checked_out_sockets.remove(sock)
            self._conn_pool.appendleft(sock)
        else:
            self._checked_out_sockets.remove(sock)

    async def _make_connection(self, host_loc):
        sock, port = await self._connect(host_loc)
        sock.host, sock.port = host_loc, port
        return sock

    async def _grab_connection(self, url):
        '''
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready, and
        as many connections checked out as there are available total,
        we yield control to the event loop.

        If there is a connection ready or space to create a new one, we
        pop/create it, register it as checked out, and return it.

        Args:
            url (str): breaks the url down and uses the top level location
                info to see if we have any connections to the location already
                lying around.
        '''
        scheme, netloc, _, _, _, _ = urlparse(url)
        host_loc = urlunparse((scheme, netloc, '', '', '', ''))

        sock = self._checkout_connection(host_loc)
        if sock is not None:
            return sock
        else:
            sock = await self._make_connection(host_loc)
            self._checked_out_sockets.append(sock)

        return sock

    def _make_url(self):
        '''
        Puts together the hostloc and current endpoint for use in request uri.
        '''
        return (self.base_location or '') + (self.endpoint or '')

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._conn_pool.free_pool()
