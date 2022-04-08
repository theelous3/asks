import codecs
import json as _json
from types import SimpleNamespace
from typing import Any, Iterator, Optional

import h11
from async_generator import async_generator, yield_

from .errors import BadStatus
from .http_utils import decompress, parse_content_encoding
from .req_structs import SocketLike
from .utils import timeout_manager


class BaseResponse:
    """
    A response object supporting a range of methods and attribs
    for accessing the status line, header, cookies, history and
    body of a response.
    """

    def __init__(
        self,
        encoding: str,
        http_version: str,
        status_code: int,
        reason_phrase: str,
        headers: dict[str, str],
        body: bytes,
        method: str,
        url: str,
    ) -> None:
        self.encoding = encoding
        self.http_version = http_version
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.headers = headers
        self.body = body
        self.method = method
        self.url = url
        self.history: list["BaseResponse"] = []
        self.cookies: list["Cookie"] = []

    def raise_for_status(self) -> None:
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

    def __repr__(self) -> str:
        return "<{} {} {}>".format(
            self.__class__.__name__, self.status_code, self.reason_phrase
        )

    def _guess_encoding(self) -> None:
        try:
            guess = self.headers["content-type"].split("=")[1]
            codecs.lookup(guess)
            self.encoding = guess
        except LookupError:  # IndexError/KeyError are LookupError subclasses
            pass

    def _decompress(self, encoding: Optional[str] = None) -> Any:
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

    async def __aenter__(self) -> "BaseResponse":
        return self

    async def __aexit__(self, *exc_info: Any) -> Any:
        ...


class Response(BaseResponse):
    def json(self, **kwargs: Any) -> Any:
        """
        If the response's body is valid json, we load it as a python dict
        and return it.
        """
        body = self._decompress(self.encoding)
        return _json.loads(body, **kwargs)

    @property
    def text(self) -> Any:
        """
        Returns the (maybe decompressed) decoded version of the body.
        """
        return self._decompress(self.encoding)

    @property
    def content(self) -> Any:
        """
        Returns the content as-is after decompression, if any.
        """
        return self._decompress()

    @property
    def raw(self) -> bytes:
        """
        Returns the response body as received.
        """
        return self.body


class StreamResponse(BaseResponse):
    ...


class StreamBody:
    def __init__(
        self,
        h11_connection: h11.Connection,
        sock: SocketLike,
        content_encoding: Optional[str] = None,
        encoding: Optional[str] = None,
    ):
        self.h11_connection = h11_connection
        self.sock = sock
        self.content_encoding = content_encoding
        self.encoding = encoding
        # TODO: add decompress data to __call__ args
        self.decompress_data = True
        self.timeout: Optional[float] = None
        self.read_size = 10000

    @async_generator
    async def __aiter__(self) -> None:
        if self.content_encoding is not None:
            decompressor = decompress(parse_content_encoding(self.content_encoding))
        while True:
            event = await self._recv_event()
            if isinstance(event, h11.Data):
                data = event.data
                if self.content_encoding is not None:
                    if self.decompress_data:
                        data = decompressor.send(event.data)
                await yield_(data)
            elif isinstance(event, h11.EndOfMessage):
                break

    async def _recv_event(self) -> Any:
        while True:
            event = self.h11_connection.next_event()

            if event is h11.NEED_DATA:
                data = await timeout_manager(
                    self.timeout, self.sock.receive, self.read_size
                )
                self.h11_connection.receive_data(data)
                continue

            return event

    def __call__(self, timeout: Optional[float] = None) -> "StreamBody":
        self.timeout = timeout
        return self

    async def __aenter__(self) -> "StreamBody":
        return self

    async def close(self) -> None:
        await self.sock.aclose()

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()


class Cookie(SimpleNamespace):
    """
    A simple cookie object, for storing cookie stuff :)
    Needs to be made compatible with the API's cookies kw arg.
    """

    def __init__(self, host: str, data: dict[str, Any]) -> None:
        self.name: Optional[str] = None
        self.value: Optional[str] = None
        self.domain: Optional[str] = None
        self.path: Optional[str] = None
        self.secure: bool = False
        self.comment: Optional[str] = None

        self.__dict__.update(data)

        super().__init__(**self.__dict__)
        self.host = host

    def __repr__(self) -> str:
        if self.name is not None:
            return "<Cookie {} from {}>".format(self.name, self.host)
        else:
            return "<Cookie {} from {}>".format(self.value, self.host)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for k, v in self.__dict__.items():
            yield k, v
