'''
Experimental!
Has minimal tests, but currently working well!

TO DO:
    * Write more tests.
    * Especially for DSession
'''

# pylint: disable=no-else-return
# pylint: disable=no-member
from urllib.parse import urlparse, urlunparse
from functools import partialmethod

import curio
from curio import socket, open_connection

from asks.request import Request
from .cookie_utils import CookieTracker
from .req_structs import SocketQ
from .utils import get_netloc_port


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
        if url is None:
            url = self._make_url() + path
            sock = await self._grab_connection()
            port = self.port
        else:
            sock = await self._grab_connection(url)
            port = sock.port
        req = Request(method,
                      url,
                      port,
                      encoding=self.encoding,
                      sock=sock,
                      persist_cookies=self.cookie_tracker_obj,
                      **kwargs)
        r = await req.make_request()
        await self._replace_connection(sock)
        return r

    # These be the actual http methods!
    get = partialmethod(request, 'GET')
    head = partialmethod(request, 'HEAD')
    post = partialmethod(request, 'POST')
    put = partialmethod(request, 'PUT')
    delete = partialmethod(request, 'DELETE')
    options = partialmethod(request, 'OPTIONS')


class Session(BaseSession):
    '''
    The heart of asks. Async and connection pooling are a wonderful
    combination. This session class is a quick, efficent, and (if you like,
    sateful) abstraction over the base http method functions.

    >>> async def main():
    ...    s = await Session('https://url.com')
    ...    for _ in range(1000):
    ...        r = await s.get()
    '''
    def __init__(self,
                 host,
                 endpoint=None,
                 encoding='utf-8',
                 cookie_interactions=None,
                 connections=1):

        self.encoding = encoding
        self.endpoint = endpoint
        self.host = host
        self.port = None

        if cookie_interactions is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = cookie_interactions

        self.connection_pool = SocketQ(maxlen=connections)
        self.checked_out_sockets = SocketQ(maxlen=connections)

    async def _grab_connection(self):
        '''
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready, and
        no fewer connections checked out than total available,
        we yield control to the event loop.

        If there is a connection ready, we pop it, register it
        as checked out, and return it.
        '''
        while True:
            try:
                sock = self.connection_pool.pop()
                self.checked_out_sockets.append(sock)
                return sock
            except IndexError:
                if len(self.checked_out_sockets) < self.connection_pool.maxlen:
                    sock, self.port = (await self._connect())
                    self.checked_out_sockets.append(sock)
                    return sock
                else:
                    await curio.sleep(0)

    async def _replace_connection(self, sock):
        '''
        Unregistered socket objects as checked out and returns them.
        '''
        if sock._file is not None:  # Don't think this is valid check.
            self.checked_out_sockets.remove(sock)
            self.connection_pool.appendleft(sock)
        else:
            self.checked_out_sockets.remove(sock)
            self.connection_pool.appendleft((await self._connect()[0]))

    def _make_url(self):
        return self.host + (self.endpoint or '')


class DSession(BaseSession):
    '''
    The disparate session class, for handling piles of unrelated requests.
    '''
    def __init__(self,
                 encoding='utf-8',
                 cookie_interactions=None,
                 connections=20):
        self.encoding = encoding

        if cookie_interactions is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = cookie_interactions

        self.connection_pool = SocketQ(maxlen=connections)
        self.checked_out_sockets = SocketQ(maxlen=connections)

    def _checkout_connection(self, host_loc):
        index = self.connection_pool.index(host_loc)
        sock = self.connection_pool.pull(index)
        self.checked_out_sockets.append(sock)
        return sock

    async def _replace_connection(self, sock):
        if sock._file is not None:
            self.checked_out_sockets.remove(sock)

        else:
            self.checked_out_sockets.remove(sock)
            sock = (await self._make_connection(sock.host))

        self.connection_pool.appendleft(sock)

    async def _make_connection(self, host_loc):
        sock, port = await self._connect(host_loc=host_loc)
        sock.host, sock.port = host_loc, port
        return sock

    async def _grab_connection(self, url):
        scheme, netloc, _, _, _, _ = urlparse(url)
        host_loc = urlunparse((scheme, netloc, '', '', '', ''))
        while True:
            if host_loc in self.connection_pool:
                sock = self._checkout_connection(host_loc)
                break
            elif host_loc in self.checked_out_sockets:
                if len(self.checked_out_sockets) < self.connection_pool.maxlen:
                    sock = await self._make_connection(host_loc)
                    self.checked_out_sockets.append(sock)
                    break
                else:
                    await curio.sleep(0)
                    continue
            else:
                sock = await self._make_connection(host_loc)
                self.checked_out_sockets.append(sock)
        return sock
