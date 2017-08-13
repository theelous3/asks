import codecs
from types import SimpleNamespace
import json as _json
from gzip import decompress as gdecompress
from zlib import decompress as zdecompress

import h11

from asks import _async_lib


class Response:
    '''
    A response object supporting a range of methods and attribs
    for accessing the status line, header, cookies, history and
    body of a response.
    '''
    def __init__(self,
                 encoding,
                 http_version,
                 status_code,
                 reason_phrase,
                 headers,
                 body,
                 method):
        self.encoding = encoding
        self.http_version = http_version
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.headers = headers
        self.body = body
        self.method = method
        self.history = []
        self.cookies = []

    def __repr__(self):
        return '<Response {} {}>'.format(self.status_code, self.reason_phrase)

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v

    def _guess_encoding(self):
        try:
            guess = self.headers['content-type'].split('=')[1]
            codecs.lookup(guess)
            self.encoding = guess
        except LookupError:  # IndexError/KeyError are LookupError subclasses
            pass

    def _parse_cookies(self, host):
        '''
        Why the hell is this here.
        '''
        cookie_pie = []
        try:
            for cookie in self.headers['set-cookie']:
                cookie_jar = {}
                name_val, *rest = cookie.split(';')
                name, value = name_val.split('=', 1)
                cookie_jar['name'] = name.strip()
                cookie_jar['value'] = value
                for item in rest:
                    try:
                        name, value = item.split('=')
                        cookie_jar[name.lower().lstrip()] = value
                    except ValueError:
                        cookie_jar[item.lower().lstrip()] = True
                cookie_pie.append(cookie_jar)
            self.cookies = [Cookie(host, x) for x in cookie_pie]
        except KeyError:
            pass

    def _decompress(self, body):
        try:
            resp_encoding = self.headers['Content-Encoding'].strip()
        except KeyError:
            return body
        if resp_encoding == 'gzip':
            return gdecompress(body)
        elif resp_encoding == 'deflate':
            return zdecompress(body)
        return body

    def json(self):
        '''
        If the response's body is valid json, we load it as a python dict
        and return it.
        '''
        body = self._decompress(self.body)
        try:
            return _json.loads(body.decode(self.encoding, errors='replace'))
        except AttributeError:
            return None

    @property
    def text(self):
        '''
        Returns the (maybe decompressed) decoded version of the body.
        '''
        try:
            return self._decompress(self.body).decode(self.encoding,
                                                      errors='replace')
        except AttributeError:
            return self._decompress(self.body)

    @property
    def content(self):
        '''
        Returns the content as-is after decompression, if any.
        '''
        return self._decompress(self.body)

    @property
    def raw(self):
        '''
        Returns the response body as received.
        '''
        return self.body


class Cookie(SimpleNamespace):
    '''
    A simple cookie object, for storing cookie stuff :)
    Needs to be made compatible with the API's cookies kw arg.
    '''
    def __init__(self, host, data):
        self.name = None
        self.value = None
        self.domain = None
        self.path = None
        self.secure = False
        self.expires = None
        self.comment = None

        self.__dict__.update(data)

        super().__init__(**self.__dict__)
        self.host = host

    def __repr__(self):
        if self.name is not None:
            return '<Cookie {} from {}>'.format(self.name, self.host)
        else:
            return '<Cookie {} from {}>'.format(self.value, self.host)

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v


class StreamBody:

    def __init__(self, session, hconnection, sock):
        self.session = session
        self.hconnection = hconnection
        self.sock = sock

    async def __aiter__(self):
        while True:
            event = await self._recv_event()
            if isinstance(event, h11.Data):
                yield event.data
            elif isinstance(event, h11.EndOfMessage):
                await self.session._replace_connection(self.sock)
                break

    async def _recv_event(self):
        while True:
            event = self.hconnection.next_event()
            if event is h11.NEED_DATA:
                self.hconnection.receive_data(
                    (await _async_lib.recv(self.sock, 10000)))
                continue
            return event

    async def __aenter__(self):
        return self

    async def close(self):
        if self.sock in self.session.checked_out_sockets:
            self.sock._active = False
            await self.session._replace_connection(self.sock)

    async def __aexit__(self, *exc_info):
        await self.close()
