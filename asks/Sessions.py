'''
Experimental! Probably borked.
Initial testing shows this is working a-ok, but no guarantees!

TO DO:
    * Write tests
'''
from collections import deque
from urllib.parse import urlparse

import curio
from curio.meta import AsyncObject

import asks.asks as asks_
from .cookie_utils import CookieTracker


__all__ = ['Session']


class Session(AsyncObject):

    async def __init__(self,
                       host,
                       port=443,
                       endpoint=None,
                       encoding='utf-8',
                       store_cookies=None,
                       connections=5,
                       rate=1):

        self.encoding = encoding
        self.endpoint = endpoint
        self.host = host
        self.port = port
        self.netloc = ''

        if store_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = store_cookies

        self.connections = connections
        self.connection_pool = deque(maxlen=connections)

        await self._run()

    async def _run(self):
        self._get_schema()
        for _ in range(self.connections):
            self.connection_pool.append(await self._connect())

    def _get_schema(self):
        if not self.host.startswith('http'):
            self.host = 'https://' + self.host

    async def _connect(self):
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

    async def grab_connection(self):
        while True:
            try:
                return self.connection_pool.pop()
            except IndexError:
                await curio.sleep(0)
                pass

    def _make_url(self):
        return self.host + (self.endpoint or '')

    async def get(self, path='', *args, **kwargs):
        url = self._make_url() + path
        sock = await self.grab_connection()

        r = await asks_.get(url,
                            encoding=self.encoding,
                            sock=sock,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)

        self.connection_pool.appendleft(sock)
        return r

    async def head(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def post(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def put(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def delete(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def options(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r
