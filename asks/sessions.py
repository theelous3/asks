'''
The disparate session (Session) is for making requests to multiple locations.
'''

# pylint: disable=no-else-return
# pylint: disable=no-member
from urllib.parse import urlparse, urlunparse
from functools import partialmethod

from asks import _async_lib

from .request import Request
from .cookie_utils import CookieTracker
from .req_structs import SocketQ
from .utils import get_netloc_port
from .errors import RequestTimeout


__all__ = ['Session']


class BaseSession:
    '''
    The base class for asks' sessions.
    Contains methods for creating sockets, figuring out which type of
    socket to create, and all of the HTTP methods ('GET', 'POST', etc.)
    '''
    async def _open_connection_http(self, location, port=None):
        '''
        Creates a normal async socket, returns it.
        '''
        sock = await _async_lib.open_connection(location[0],
                                                location[1],
                                                ssl=False)
        sock._active = True
        return sock

    async def _open_connection_https(self, location, port=None):
        '''
        Creates an async SSL socket, returns it.
        '''
        sock = await _async_lib.open_connection(location[0],
                                                location[1],
                                                ssl=True,
                                                server_hostname=location[0])
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

    async def request(self, method, url=None, *, path='', **kwargs):
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
        timeout = kwargs.pop('timeout', None)

        if url is None:
            url = self._make_url() + path
            sock = await self._grab_connection(url)
            port = sock.port
        else:
            sock = await self._grab_connection(url)
            port = sock.port

        req_obj = Request(self,
                          method,
                          url,
                          port,
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
                    sock._active = False
            except KeyError:
                pass
            await self._replace_connection(sock)

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
            try:
                async with _async_lib.timeout_after(timeout):
                    async with _async_lib.task_manager() as m:
                        response_task = await m.spawn(
                            req_obj.make_request)
                    sock, r = response_task.result
            except _async_lib.TaskTimeout:
                raise RequestTimeout
        except AttributeError:
            try:
                with _async_lib.timeout_after(timeout):
                    async with _async_lib.task_manager() as m:
                        response_task = m.spawn(req_obj.make_request)
                    sock, r = response_task.result.unwrap()
            except _async_lib.TaskTimeout:
                raise RequestTimeout
        return sock, r


class Session(BaseSession):
    '''
    The Session class, for handling piles of requests.

    This class inherits from BaseSession, where all of the 'http method'
    methods are defined.
    '''
    def __init__(self,
                 base_location=None,
                 endpoint=None,
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
                connections is 20. You may increase or decrease this value
                as you see fit.
        '''
        self.encoding = encoding
        self.base_location = base_location
        self.endpoint = endpoint

        if persist_cookies is True:
            self._cookie_tracker_obj = CookieTracker()
        else:
            self._cookie_tracker_obj = persist_cookies

        self._conn_pool = SocketQ(maxlen=connections)
        self._checked_out_sockets = SocketQ(maxlen=connections)
        self._in_connection_counter = 0

    def _checkout_connection(self, host_loc):
        try:
            index = self._conn_pool.index(host_loc)
        except ValueError:
            return None
        sock = self._conn_pool.pull(index)
        self._checked_out_sockets.append(sock)
        self._in_connection_counter += 1
        return sock

    async def _replace_connection(self, sock):
        if sock._active:
            self._checked_out_sockets.remove(sock)
        else:
            self._checked_out_sockets.remove(sock)
            sock = (await self._make_connection(sock.host))

        self._conn_pool.appendleft(sock)
        self._in_connection_counter -= 1

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

        while True:
            sock = self._checkout_connection(host_loc)
            if sock is not None:
                break
            if self._in_connection_counter < self._conn_pool.maxlen:
                self._in_connection_counter += 1
                sock = await self._make_connection(host_loc)
                self._checked_out_sockets.append(sock)
                break
            await _async_lib.sleep(0)
            continue

        return sock

    def _make_url(self):
        '''
        Puts together the hostloc and current endpoint for use in request uri.
        '''
        return self.base_location or '' + self.endpoint or ''
