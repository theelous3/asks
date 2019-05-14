# pylint: disable=no-member

import h11
import pytest

from asks.request_object import RequestProcessor


def _catch_response(monkeypatch, headers, data):
    req = RequestProcessor(None, 'get', "toot-toot", None)
    events = [
        h11._events.Response(status_code=200, headers=headers),
        h11._events.Data(data=data),
        h11._events.EndOfMessage(),
    ]
    async def _recv_event(hconn):
        return events.pop(0)
    monkeypatch.setattr(req, '_recv_event', _recv_event)
    monkeypatch.setattr(req, 'host', 'lol')
    cr = req._catch_response(None)
    try:
        cr.send(None)
    except StopIteration as e:
        response = e.value
    return response


def test_http1_1(monkeypatch):
    response = _catch_response(monkeypatch, [('Content-Length', '5')], b'hello')
    assert response.body == b'hello'


def test_http1_0(monkeypatch):
    response = _catch_response(monkeypatch, [('Connection', 'close')], b'hello')
    assert response.body == b'hello'


@pytest.mark.parametrize(['data', 'query_str'], [
    [{'foo': 'bar', 'spam': None}, '?foo=bar'],
    [{'zero': 0}, '?zero=0'],
    [{'empty': ''}, '?empty='],
    [{'false': False}, '?false=False'],
])
def test_dict_to_query(data, query_str):
    assert RequestProcessor._dict_to_query(data) == query_str
