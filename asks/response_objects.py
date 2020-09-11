import codecs
from types import SimpleNamespace
import json as _json

from async_generator import async_generator, yield_
import h11

from .http_utils import decompress, parse_content_encoding
from .utils import timeout_manager
from .errors import BadStatus


class BaseResponse:
    """
    A response object supporting a range of methods and attribs
    for accessing the status line, header, cookies, history and
    body of a response.
    """

    def __init__(
        self,
        encoding,
        http_version,
        status_code,
        reason_phrase,
        headers,
        body,
        method,
        url,
    ):
        self.encoding = encoding
        self.http_version = http_version
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.headers = headers
        self.body = body
        self.method = method
        self.url = url
        self.history = []
        self.cookies = []

    def raise_for_status(self):
        """
        Raise BadStatus if one occurred.
        """
        if 400 <= self.status_code < 500:
            raise BadStatus(
                "{} Client Error: {} for url: {}".format(
                    self.status_code, self.reason_phrase, self.url
                ),
                self,
                self.status_code,
            )
        elif 500 <= self.status_code < 600:
            raise BadStatus(
                "{} Server Error: {} for url: {}".format(
                    self.status_code, self.reason_phrase, self.url
                ),
                self,
                self.status_code,
            )

    def __repr__(self):
        return "<{} {} {}>".format(
            self.__class__.__name__, self.status_code, self.reason_phrase
        )

    def _guess_encoding(self):
        try:
            guess = self.headers["content-type"].split("=")[1]
            codecs.lookup(guess)
            self.encoding = guess
        except LookupError:  # IndexError/KeyError are LookupError subclasses
            pass

    def _decompress(self, encoding=None):
        content_encoding = self.headers.get("Content-Encoding", None)
        if content_encoding is not None:
            decompressor = decompress(
                parse_content_encoding(content_encoding), encoding
            )
            r = decompressor.send(self.body)
            return r
        else:
            if encoding is not None:
                return self.body.decode(encoding, errors="replace")
            else:
                return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        ...


class Response(BaseResponse):
    def json(self, **kwargs):
        """
        If the response's body is valid json, we load it as a python dict
        and return it.
        """
        body = self._decompress(self.encoding)
        return _json.loads(body, **kwargs)

    @property
    def text(self):
        """
        Returns the (maybe decompressed) decoded version of the body.
        """
        return self._decompress(self.encoding)

    @property
    def content(self):
        """
        Returns the content as-is after decompression, if any.
        """
        return self._decompress()

    @property
    def raw(self):
        """
        Returns the response body as received.
        """
        return self.body


class StreamResponse(BaseResponse):
    ...


class StreamBody:
    def __init__(self, h11_connection, sock, content_encoding=None, encoding=None):
        self.h11_connection = h11_connection
        self.sock = sock
        self.content_encoding = content_encoding
        self.encoding = encoding
        # TODO: add decompress data to __call__ args
        self.decompress_data = True
        self.timeout = None
        self.read_size = 10000

    @async_generator
    async def __aiter__(self):
        if self.content_encoding is not None:
            decompressor = decompress(parse_content_encoding(self.content_encoding))
        while True:
            event = await self._recv_event()
            if isinstance(event, h11.Data):
                if self.content_encoding is not None:
                    if self.decompress_data:
                        event.data = decompressor.send(event.data)
                await yield_(event.data)
            elif isinstance(event, h11.EndOfMessage):
                break

    async def _recv_event(self):
        while True:
            event = self.h11_connection.next_event()

            if event is h11.NEED_DATA:
                data = await timeout_manager(
                    self.timeout, self.sock.receive, self.read_size
                )
                self.h11_connection.receive_data(data)
                continue

            return event

    def __call__(self, timeout=None):
        self.timeout = timeout
        return self

    async def __aenter__(self):
        return self

    async def close(self):
        await self.sock.aclose()

    async def __aexit__(self, *exc_info):
        await self.close()


class Cookie(SimpleNamespace):
    """
    A simple cookie object, for storing cookie stuff :)
    Needs to be made compatible with the API's cookies kw arg.
    """

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
            return "<Cookie {} from {}>".format(self.name, self.host)
        else:
            return "<Cookie {} from {}>".format(self.value, self.host)

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v
