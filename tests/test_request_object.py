# pylint: disable=no-member
from typing import Any, Union, cast

import h11
import pytest

from asks.request_object import RequestProcessor
from asks.response_objects import Response, StreamResponse


def _catch_response(monkeypatch: pytest.MonkeyPatch,
                    headers: list[tuple[str, str]],
                    data: bytes,
                    http_version: bytes = b"1.1"
                    ) -> Union[Response, StreamResponse]:
    req = RequestProcessor(None, "get", "toot-toot", None)
    events = [
        h11._events.Response(status_code=200, headers=headers,
                             http_version=http_version),
        h11._events.Data(data=data),
        h11._events.EndOfMessage(),
    ]

    async def _recv_event(hconn: Any) -> h11._events.Event:
        return events.pop(0)

    monkeypatch.setattr(req, "_recv_event", _recv_event)
    monkeypatch.setattr(req, "host", "lol")
    cr = req._catch_response(cast(h11.Connection, None))
    try:
        cr.send(None)
    except StopIteration as e:
        response = e.value
    return cast(Union[Response, StreamResponse], response)


def test_http1_1(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _catch_response(
        monkeypatch, [("Content-Length", "5")], b"hello")
    assert response.body == b"hello"


def test_http1_1_connection_close(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _catch_response(
        monkeypatch, [("Connection", "close")], b"hello")
    assert response.body == b"hello"


def test_http1_0_no_content_length(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _catch_response(monkeypatch, [], b"hello", b"1.0")
    assert response.body == b"hello"


@pytest.mark.parametrize(
    ["data", "query_str"],
    [
        [{"foo": "bar", "spam": None}, "?foo=bar"],
        [{"zero": 0}, "?zero=0"],
        [{"empty": ""}, "?empty="],
        [{"false": False}, "?false=False"],
    ],
)
def test_dict_to_query(data: dict[str, Any], query_str: str) -> None:
    assert RequestProcessor._dict_to_query(data) == query_str
