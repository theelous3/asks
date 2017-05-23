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
        if not any((parameters, query, fragment)):
            if path == '/':
                pass
        else:
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
    get = partialmethod(request, 'GET')
    head = partialmethod(request, 'HEAD')
    post = partialmethod(request, 'POST')
    put = partialmethod(request, 'PUT')
    delete = partialmethod(request, 'DELETE')
    options = partialmethod(request, 'OPTIONS')


class HSession(BaseSession):
    '''
    The Homogeneous Session.
    This type of session is build to deal with many requests to a single host.
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
            host (str): The top level domain to which most/all of the
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
                host asks will allow its self to have.
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
        self._pool_lock = False

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
            sock, port = await self._connect(host_loc=off_base_loc)
            self.checked_out_sockets.append(sock)
            return sock, port
        while True:
            if not self._pool_lock:
                try:
                    sock = self.conn_pool.pop()
                    self.checked_out_sockets.append(sock)
                    break
                except IndexError:
                    if len(self.checked_out_sockets) + len(self.conn_pool)\
                      < self.conn_pool.maxlen:
                        self._pool_lock = True
                        sock, self.port = (await self._connect())
                        self.checked_out_sockets.append(sock)
                        self._pool_lock = False
                        break
            await curio.sleep(0)
            continue

        return sock

    async def _replace_connection(self, sock):
        '''
        Unregisteres socket objects as checked out and returns them to pool.
        '''
        while True:
            if not self._pool_lock:
                self._pool_lock = True
                if sock._active:
                    self.checked_out_sockets.remove(sock)
                    self.conn_pool.appendleft(sock)
                    self._pool_lock = False
                    break
                else:
                    sock_new, _ = await self._connect()
                    self.checked_out_sockets.remove(sock)
                    self.conn_pool.appendleft(sock_new)
                    self._pool_lock = False
                    break
            await curio.sleep(0)
            continue

    def _make_url(self):
        '''
        Puts together the hostloc and current endpoint for use in request uri.
        '''
        return self.host + (self.endpoint or '')


class DSession(BaseSession):
    '''
    The disparate session class, for handling piles of unrelated requests.
    This is just like requests' Session.
    '''
    def __init__(self,
                 encoding='utf-8',
                 persist_cookies=None,
                 connections=20):
        self.encoding = encoding

        if persist_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = persist_cookies

        self.conn_pool = SocketQ(maxlen=connections)
        self.checked_out_sockets = SocketQ(maxlen=connections)
        self._pool_lock = False

    def _checkout_connection(self, host_loc):
        index = self.conn_pool.index(host_loc)
        sock = self.conn_pool.pull(index)
        self.checked_out_sockets.append(sock)
        return sock

    async def _replace_connection(self, sock):
        if sock._active:
            self.checked_out_sockets.remove(sock)
        else:
            self.checked_out_sockets.remove(sock)
            sock = (await self._make_connection(sock.host))

        self.conn_pool.appendleft(sock)

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
            if host_loc in self.conn_pool:
                sock = self._checkout_connection(host_loc)
                break
            if not self._pool_lock:
                if host_loc in self.checked_out_sockets:
                    if len(self.checked_out_sockets) + len(self.conn_pool)\
                      < self.conn_pool.maxlen:
                        self._pool_lock = True
                        sock = await self._make_connection(host_loc)
                        self.checked_out_sockets.append(sock)
                        self._pool_lock = False
                        break
                else:
                    if len(self.checked_out_sockets) + len(self.conn_pool)\
                      < self.conn_pool.maxlen:
                        self._pool_lock = True
                        sock = await self._make_connection(host_loc)
                        self.checked_out_sockets.append(sock)
                        self._pool_lock = False
                        break
            await curio.sleep(0)
            continue

        return sock
