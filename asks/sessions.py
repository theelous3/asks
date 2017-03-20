'''
Experimental!
Has minimal tests, but currently working well!

TO DO:
    * Write more tests.
    * Especially for DSession
'''

# pylint: disable=no-else-return
from collections import deque
from urllib.parse import urlparse, urlunparse

import curio
from curio.meta import AsyncObject
from curio import socket, open_connection

from asks.request import Request
from .cookie_utils import CookieTracker
from .req_structs import SocketQ


__all__ = ['Session', 'DSession']


class BaseSession:
    '''
    The base class for asks' session.
    '''
    async def _open_connection_http(self, location):
        '''
        Creates an async socket, set to stream mode and returns it.
        '''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        await sock.connect(location)
        sock = sock.as_stream()
        return sock

    async def _open_connection_https(self, location):
        '''
        Creates an async SSL socket, set to stream mode and returns it.
        '''
        sock = await open_connection(location[0],
                                     443,
                                     ssl=True,
                                     server_hostname=location[0])
        sock = sock.as_stream()
        return sock

    async def _connect(self, host_loc=None):
        '''
        Simple enough stuff to figure out where we should connect, and creates
        the appropriate connection.
        '''
        scheme, netloc, path, parameters, query, fragment = urlparse(
            host_loc or self.host)
        if any((path, parameters, query, fragment)):
            if path == '/':
                pass
            else:
                raise ValueError('Supplied info beyond scheme, netloc.' +
                                 ' Host should be top level only:\n', path)

        try:
            netloc, port = netloc.split(':')
        except ValueError:
            if scheme == 'https':
                port = '443'
            else:
                port = '80'

        if scheme == 'http':
            return await self._open_connection_http(
                (netloc, int(port))), port
        else:
            return await self._open_connection_https(
                (netloc, int(port))), port


class Session(BaseSession, AsyncObject):
    '''
    The heart of asks. Async and connection pooling are a wonderful
    combination. This session class is a quick, efficent, and (if you like,
    sateful) abstraction over the base http method functions.

    >>> async def main():
    ...    s = await Session('https://url.com')
    ...    for _ in range(1000):
    ...        r = await s.get()
    '''
    async def __init__(self,
                       host,
                       port=443,
                       endpoint=None,
                       encoding='utf-8',
                       store_cookies=None,
                       connections=1):

        self.encoding = encoding
        self.endpoint = endpoint
        self.host = host
        self.port = port

        if store_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = store_cookies

        self.connection_pool = deque(maxlen=connections)

        # a function call in __init__!? Oh my!
        # It's ok. This sets in motion the building of our connection pool.
        await self._run()

    async def _run(self):
        for _ in range(self.connection_pool.maxlen):
            s, _ = await self._connect()
            self.connection_pool.append(s)

    async def _grab_connection(self):
        '''
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready,
        we yield control to the event loop.
        '''
        while True:
            try:
                return self.connection_pool.pop()
            except IndexError:
                await curio.sleep(0)

    async def _replace_connection(self, sock):
        if sock._file is not None:
            self.connection_pool.appendleft(sock)
        else:
            self.connection_pool.appendleft(await self._connect()[0])

    def _make_url(self):
        return self.host + (self.endpoint or '')

    async def get(self, path='', **kwargs):
        '''
        Public methods for getting / posting and so forth.
        Gets the target location, and begins requesting a
        connection from the pool. Once it gets a socket it does
        it's business, and returns the socet back to the pool
        before returning the final response object.
        '''
        url = self._make_url() + path
        sock = await self._grab_connection()
        req = Request('GET',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r

    async def head(self, path='', **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        req = Request('HEAD',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r

    async def post(self, path='', **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        req = Request('POST',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r

    async def put(self, path='', **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        req = Request('PUT',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r

    async def delete(self, path='', **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        req = Request('DELETE',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r

    async def options(self, path='', **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        req = Request('OPTIONS',
                      url,
                      port=self.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()

        await self._replace_connection(sock)
        return r


class DSession(BaseSession):
    '''
    The disparate session class, for handling piles of unrelated requests.
    '''
    def __init__(self, encoding='utf-8', store_cookies=None, connections=20):
        self.encoding = encoding

        if store_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = store_cookies

        self.connection_pool = SocketQ(maxlen=connections)

    def _checkout_connection(self, host_loc):
        index = self.connection_pool.index(host_loc)
        return self.connection_pool.pull(index)

    def _replace_connection(self, sock):
        if sock._file is not None:
            self.connection_pool.appendleft(sock)

    async def _make_connection(self, host_loc):
        sock, port = await self._connect(host_loc=host_loc)
        sock.host, sock.port = host_loc, port
        return sock

    async def _grab_connection(self, url):
        scheme, netloc, path, parameters, query, fragment = urlparse(url)
        host_loc = urlunparse((scheme, netloc, '', '', '', ''))
        if host_loc in self.connection_pool:
            sock = self._checkout_connection(host_loc)
        else:
            sock = await self._make_connection(host_loc)
        return sock

    async def get(self, url, **kwargs):
        '''
        Public methods for getting / posting and so forth.
        Gets the url, and begins requesting a
        connection from the pool. Once it gets a socket it does
        it's business, and returns the socet back to the pool
        before returning the final response object.
        '''
        sock = await self._grab_connection(url)
        req = Request('GET',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r

    async def head(self, url, **kwargs):
        sock = await self._grab_connection(url)
        req = Request('HEAD',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r

    async def post(self, url, **kwargs):
        sock = await self._grab_connection(url)
        req = Request('PUT',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r

    async def put(self, url, **kwargs):
        sock = await self._grab_connection(url)
        req = Request('PUT',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r

    async def delete(self, url, **kwargs):
        sock = await self._grab_connection(url)
        req = Request('DELETE',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r

    async def options(self, url, **kwargs):
        sock = await self._grab_connection(url)
        req = Request('OPTIONS',
                      url,
                      port=sock.port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req._build_request()
        self._replace_connection(sock)
        return r
