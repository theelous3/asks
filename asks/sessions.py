'''
The two session classes.

The disparate session (DSession) is for making requests to multiple locations.

'''

# pylint: disable=no-else-return
# pylint: disable=no-member
from urllib.parse import urlparse, urlunparse
from functools import partialmethod

import curio
from curio import socket, open_connection

from .request import Request
from .cookie_utils import CookieTracker
from .req_structs import SocketQ
from .utils import get_netloc_port
from .errors import RequestTimeout


__all__ = ['HSession', 'DSession']


class BaseSession:
    '''
    The base class for asks' sessions.
    Contains methods for creating sockets, figuring out which type of
    socket to create, and all of the HTTP methods ('GET', 'POST', etc.)
    '''
    async def _open_connection_http(self, location):
        '''
        Creates a normal async socket, returns it.
        '''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        await sock.connect(location)
        sock._active = True
        return sock

    async def _open_connection_https(self, location):
        '''
        Creates an async SSL socket, returns it.
        '''
        sock = await open_connection(location[0],
                                     443,
                                     ssl=True,
                                     server_hostname=location[0])
        sock._active = True
        return sock

    async def _connect(self, host_loc=None):
        '''
        Simple enough stuff to figure out where we should connect, and creates
        the appropriate connection.
        '''
        scheme, netloc, path, parameters, query, fragment = urlparse(
            host_loc or self.host)
        if parameters or query or fragment:
            raise ValueError('Supplied info beyond scheme, netloc.' +
                             ' Host should be top level only:\n', path)

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
        the HSession and DSession.

        Args:
            method (str): A http method, such as 'GET' or 'POST'.
            url (str): The url the request should be made to.
            path (str): An optional kw-arg for use in HSession method calls.
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
                            instanciates a CookieTracker object to manage the
                            return of cookies to the server under the relevant
                            domains.
                        auth (child of AuthBase): An object for handling auth
                            construction.

        When you call something like DSession.get() or asks.post(), you're
        really calling a partial method that has the 'method' argument
        pre-completed.

        When this method is used in a DSession, like so:
            s = asks.DSession()
            s.get('https://example.org')
        ...you're passing your url string under the `url` keyword positional
        arg. All DSession methods bar a direct call to `request` pass the
        `method` argument implicitly.

        When this method is used in a HSession, like this:
            s = asks.HSession('https://example.org')
            s.get()
        ...both the method *and* url are passed implicitly. The url in this
        case is the concatenation of .host and .endpoint. You may further
        augment the url by explicitly using the `path` kw-arg.
            s = asks.HSession('https://example.org')
            s.endpoint = '/chat'
            s.get(path='/chat-room-1')
            # results in a call to 'https://example.org/chat/chat-room-1'
        '''
        timeout = kwargs.pop('timeout', None)

        if url is None:
            url = self._make_url() + path
            sock = await self._grab_connection()
            port = self.port
        else:
            sock = await self._grab_connection(url)
            port = sock.port
        req_obj = Request(self,
                          method,
                          url,
                          port,
                          encoding=self.encoding,
                          sock=sock,
                          persist_cookies=self.cookie_tracker_obj,
                          **kwargs)

        if timeout is None:
            sock, r = await req_obj.make_request()
        else:
            response_task = await curio.spawn(req_obj.make_request())
            try:
                sock, r = await curio.timeout_after(
                    timeout, response_task.join())
            except curio.TaskTimeout:
                await response_task.cancel()
                raise RequestTimeout

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


class HSession(BaseSession):
    '''
    The Homogeneous Session.
    This type of session is built to deal with many requests to a single host.
    An example of this, would be dealing with an api or scraping all of the
    comics from xkdc.

    You instance it with the top level domain you'll be working with, and
    can basically just start calling methods on it right away.
    '''
    def __init__(self,
                 host,
                 endpoint=None,
                 encoding='utf-8',
                 persist_cookies=None,
                 connections=1):
        '''
        Args:
            host (str): The top level domain to which all of the
                requests will be made. Example: 'https://example.org'
            endpoint (str): The base uri can be augmented further. Example:
                '/chat'. Calling one of the http method methods without a
                further path, like .get(), would result in a request to
                'https://example.org/chat'
            encoding (str): The encoding asks'll try to use on response bodies.
            persist_cookies (bool): Passing True turns on browserishlike
                stateful cookie behaviour, returning cookies to the host when
                appropriate.
            connections (int): The max number of concurrent connections to the
                host asks will allow its self to have. The default number of
                connections is ONE. You *WILL* want to change this value to
                suit your application and the limits of the remote host you're
                working with.
        '''
        self.encoding = encoding
        self.endpoint = endpoint
        self.host = host
        self.port = None

        if persist_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = persist_cookies

        self.conn_pool = SocketQ(maxlen=connections)
        self.checked_out_sockets = SocketQ(maxlen=connections)
        self.sema = curio.BoundedSemaphore(value=connections)
        self.in_connection_counter = 0

    async def _grab_connection(self, off_base_loc=False):
        '''
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready, and
        as many connections checked out as there are available total,
        we yield control to the event loop.

        If there is a connection ready or space to create a new one, we
        pop it, register it as checked out, and return it.

        Args:
            off_base_loc (str): Passing a uri here indicates that we are
                straying from the base location set on instanciation, and
                creates a new connection to the provided domain.
        '''
        if off_base_loc:
            while True:
                if self.in_connection_counter < self.conn_pool.maxlen:
                    sock, port = await self._connect(host_loc=off_base_loc)
                    self.checked_out_sockets.append(sock)
                    self.in_connection_counter += 1
                    break
                else:
                    await curio.sleep(0)
                    continue
            return sock, port
        while True:
            try:
                sock = self.conn_pool.pop()
                self.checked_out_sockets.append(sock)
                self.in_connection_counter += 1
                break
            except IndexError:
                if self.in_connection_counter < self.conn_pool.maxlen:
                    self.in_connection_counter += 1
                    sock, self.port = (await self._connect())
                    self.checked_out_sockets.append(sock)
                    break
            await curio.sleep(0)
            continue

        return sock

    async def _replace_connection(self, sock):
        '''
        Unregisteres socket objects as checked out and returns them to pool.
        '''
        while True:
            if sock._active:
                self.checked_out_sockets.remove(sock)
                self.conn_pool.appendleft(sock)
                break
            else:
                sock_new, _ = await self._connect()
                self.checked_out_sockets.remove(sock)
                self.conn_pool.appendleft(sock_new)
                break
            await curio.sleep(0)
            continue
        self.in_connection_counter -= 1

    def _make_url(self):
        '''
        Puts together the hostloc and current endpoint for use in request uri.
        '''
        return self.host + (self.endpoint or '')


class DSession(BaseSession):
    '''
    The disparate session class, for handling piles of unrelated requests.
    This is just like requests' Session.

    This class inherits from BaseSession, where all of the 'http method'
    methods are defined.
    '''
    def __init__(self,
                 encoding='utf-8',
                 persist_cookies=None,
                 connections=20):
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

        if persist_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = persist_cookies

        self.conn_pool = SocketQ(maxlen=connections)
        self.checked_out_sockets = SocketQ(maxlen=connections)
        self.sema = curio.BoundedSemaphore(value=1)
        self.in_connection_counter = 0

    def _checkout_connection(self, host_loc):
        try:
            index = self.conn_pool.index(host_loc)
        except ValueError:
            return None
        sock = self.conn_pool.pull(index)
        self.checked_out_sockets.append(sock)
        self.in_connection_counter += 1
        return sock

    async def _replace_connection(self, sock):
        if sock._active:
            self.checked_out_sockets.remove(sock)
        else:
            self.checked_out_sockets.remove(sock)
            sock = (await self._make_connection(sock.host))

        self.conn_pool.appendleft(sock)
        self.in_connection_counter -= 1

    async def _make_connection(self, host_loc):
        sock, port = await self._connect(host_loc=host_loc)
        sock.host, sock.port = host_loc, port
        return sock

    async def _grab_connection(self, url):
        '''
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready, and
        as many connections checked out as there are available total,
        we yield control to the event loop.

        If there is a connection ready or space to create a new one, we
        pop it, register it as checked out, and return it.

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
            if self.in_connection_counter < self.conn_pool.maxlen:
                self.in_connection_counter += 1
                sock = await self._make_connection(host_loc)
                self.checked_out_sockets.append(sock)
                break
            await curio.sleep(0)
            continue

        return sock
