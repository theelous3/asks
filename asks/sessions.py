'''
Experimental!
Has minimal tests, but currently working well!

TO DO:
    * Write more tests.
'''
from collections import deque
from urllib.parse import urlparse

import curio
from curio.meta import AsyncObject

import asks.asks as asks_
from .cookie_utils import CookieTracker


__all__ = ['Session']


class Session(AsyncObject):
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
        self.netloc = ''

        if store_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = store_cookies

        self.connection_pool = deque(maxlen=connections)

        # a function call in __init__!? Oh my!
        # It's ok. This sets in motion the building of our connection pool.
        await self._run()

    async def _run(self):
        self._get_schema()
        for _ in range(self.connection_pool.maxlen):
            self.connection_pool.append(await self._connect())

    def _get_schema(self):
        '''
        Figures out the appropriate http type.
        '''
        if not self.host.startswith('http'):
            self.host = 'https://' + self.host

    async def _connect(self):
        '''
        Simple enough stuff to figure out where we should connect, and creates
        the appropriate connection.
        '''
        scheme, netloc, path, parameters, query, fragment = urlparse(self.host)
        if any((path, parameters, query, fragment)):
            if path == '/':
                pass
            else:
                raise ValueError('Supplied info beyond scheme, netloc.' +
                                 ' Host should be top level only.')
        self.netloc = netloc
        if scheme == 'http':
            self.port = 80
            return await asks_._open_connection_http(
                (self.netloc, self.port))
        else:
            return await asks_._open_connection_https(
                (self.netloc, self.port))

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

    def _make_url(self):
        return self.host + (self.endpoint or '')

    async def get(self, path='', *args, **kwargs):
        '''
        Public methods for getting / posting and so forth.
        Gets the target location, and begins requesting a
        connection from the pool. Once it gets a socket it does
        it's business, and returns the socet back to the pool
        before returning the final response object.
        '''
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.get(url,
                            encoding=self.encoding,
                            sock=sock,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def head(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.head(url,
                             encoding=self.encoding,
                             sock=sock,
                             persist_cookies=self.cookie_tracker_obj,
                             **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def post(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.post(url,
                             encoding=self.encoding,
                             sock=sock,
                             persist_cookies=self.cookie_tracker_obj,
                             **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def put(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.put(url,
                            encoding=self.encoding,
                            sock=sock,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def delete(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.delete(url,
                               encoding=self.encoding,
                               sock=sock,
                               persist_cookies=self.cookie_tracker_obj,
                               **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def options(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self._grab_connection()

        r = await asks_.options(url,
                                encoding=self.encoding,
                                sock=sock,
                                persist_cookies=self.cookie_tracker_obj,
                                **kwargs)

        self.connection_pool.appendleft(sock)
        return r
