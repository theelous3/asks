# pylint: disable=wrong-import-position

import ssl
from os import path
from functools import partial
from pathlib import Path
from typing import Optional, cast

import h11
import pytest
from anyio import create_task_group, open_file, EndOfStream
from overly import (
    Server,
    ssl_socket_wrapper,
    default_ssl_cert,
    send_200,
    send_303,
    send_400,
    send_500,
    delay,
    send_request_as_json,
    accept_cookies_and_respond,
    send_gzip,
    send_deflate,
    send_chunked,
    send_200_blank_headers,
    finish,
    HttpMethods,
)

import asks
from asks.request_object import RequestProcessor
from asks.errors import TooManyRedirects, BadStatus, RequestTimeout
from asks.response_objects import Response, StreamResponse
from asks.req_structs import SocketLike

import _pytest

pytestmark = pytest.mark.anyio

_TEST_LOC = ("localhost", 25001)
_SSL_CONTEXT = ssl.create_default_context(cadata=default_ssl_cert)


@pytest.fixture
def server(request: _pytest.fixtures.SubRequest) -> Server:
    srv = Server(_TEST_LOC, **request.param)
    srv.daemon = True
    srv.start()
    srv.ready_to_go.wait()
    yield srv
    srv.kill_threads = True
    srv.join()


@pytest.mark.parametrize('server', [dict(steps=[send_200, finish])], indirect=True)
async def test_http_get(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    assert r.status_code == 200


# GET tests


@pytest.mark.parametrize('server', [
    dict(steps=[send_200, finish], socket_wrapper=ssl_socket_wrapper)
], indirect=True)
async def test_https_get(server: Server, caplog: pytest.LogCaptureFixture) -> None:
    import logging
    caplog.set_level(logging.DEBUG)
    # If we use ssl_context= to trust the CA, then we can successfully do a
    # GET over https.
    r = await asks.get(server.https_test_url, ssl_context=_SSL_CONTEXT)
    assert r.status_code == 200


@pytest.mark.parametrize('server', [
    dict(steps=[send_200, finish], socket_wrapper=ssl_socket_wrapper)
], indirect=True)
async def test_https_get_checks_cert(server: Server) -> None:
    try:
        expected_error: type = ssl.SSLCertVerificationError
    except AttributeError:
        # If we're running in Python <3.7, we won't have the specific error
        # that will be raised, but we can expect it to raise an SSLError
        # nonetheless
        expected_error = ssl.SSLError

    # The server's certificate isn't signed by any real CA. By default, asks
    # should notice that, and raise an error.
    with pytest.raises(expected_error):
        await asks.get(server.https_test_url)


# # async def test_bad_www_and_schema_get():
#     r = await asks.get('http://reddit.com')
#     assert r.status_code == 200


@pytest.mark.parametrize('server', [dict(steps=[send_400, finish])], indirect=True)
async def test_http_get_client_error(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match("400 Client Error: BAD REQUEST")
    assert excinfo.value.status_code == 400


@pytest.mark.parametrize('server', [dict(steps=[send_500, finish])], indirect=True)
async def test_http_get_server_error(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match("500 Server Error: INTERNAL SERVER ERROR")
    assert excinfo.value.status_code == 500


# Redirect tests


@pytest.mark.parametrize('server', [
    dict(
        max_requests=4,
        steps=[
            [(HttpMethods.GET, "/redirect_1"), send_303, finish],
            [(HttpMethods.GET, "/"), send_200, finish],
            [(HttpMethods.GET, "/redirect_1"), send_303, finish],
            [(HttpMethods.GET, "/"), send_200, finish],
        ],
        ordered_steps=True,
    )
], indirect=True)
async def test_http_redirect(server: Server) -> None:
    r = await asks.get(server.http_test_url + "/redirect_1")
    assert len(r.history) == 1

    # make sure history doesn't persist across responses
    r.history.append(cast(Response, "not a response obj"))
    r = await asks.get(server.http_test_url + "/redirect_1")
    assert len(r.history) == 1


@pytest.mark.parametrize('server', [
    dict(
        max_requests=3,
        steps=[
            [
                (HttpMethods.GET, "/redirect_max"),
                partial(send_303, headers=[("location", "redirect_max1")]),
                finish,
            ],
            [
                (HttpMethods.GET, "/redirect_max1"),
                partial(send_303, headers=[("location", "redirect_max")]),
                finish,
            ],
        ],
    )
], indirect=True)
async def test_http_max_redirect_error(server: Server) -> None:
    with pytest.raises(TooManyRedirects):
        await asks.get(server.http_test_url + "/redirect_max", max_redirects=1)


@pytest.mark.parametrize('server', [
    dict(
        max_requests=2,
        steps=[
            [
                (HttpMethods.GET, "/path/redirect"),
                partial(send_303, headers=[("location", "../foo/bar")]),
                finish,
            ],
            [(HttpMethods.GET, "/foo/bar"), send_200, finish],
        ],
    )
], indirect=True)
async def test_redirect_relative_url(server: Server) -> None:
    r = await asks.get(server.http_test_url + "/path/redirect", max_redirects=1)
    assert len(r.history) == 1
    assert r.url == "http://{0}:{1}/foo/bar".format(*_TEST_LOC)


@pytest.mark.parametrize('server', [
    dict(
        max_requests=2,
        steps=[
            [
                (HttpMethods.GET, "/redirect_once"),
                partial(send_303, headers=[("location", "/")]),
                finish,
            ],
            [(HttpMethods.GET, "/"), send_200, finish],
        ],
    )
], indirect=True)
async def test_http_under_max_redirect(server: Server) -> None:
    r = await asks.get(server.http_test_url + "/redirect_once", max_redirects=2)
    assert r.status_code == 200


@pytest.mark.parametrize('server', [
    dict(
        max_requests=1,
        steps=[
            [
                (HttpMethods.GET, "/redirect_once"),
                partial(send_303, headers=[("location", "/")]),
                finish,
            ],
        ],
    )
], indirect=True)
async def test_dont_follow_redirects(server: Server) -> None:
    r = await asks.get(server.http_test_url + "/redirect_once", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"

# Timeout tests


@pytest.mark.parametrize('server', [dict(steps=[delay(2), send_200, finish])], indirect=True)
async def test_http_timeout_error(server: Server) -> None:
    with pytest.raises(RequestTimeout):
        await asks.get(server.http_test_url, timeout=1)


@pytest.mark.parametrize('server', [dict(steps=[send_200, finish])], indirect=True)
async def test_http_timeout(server: Server) -> None:
    r = await asks.get(server.http_test_url, timeout=10)
    assert r.status_code == 200


# Param set test


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_param_dict_set(server: Server) -> None:
    r = await asks.get(server.http_test_url, params={"cheese": "the best"})
    if not isinstance(r, Response):
        raise TypeError("expected Response")
    j = r.json()
    assert next(v == "the best" for k, v in j["params"] if k == "cheese")


# Data set test


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_data_dict_set(server: Server) -> None:
    r = await asks.post(server.http_test_url, data={"cheese": "please bby"})
    if not isinstance(r, Response):
        raise TypeError("expected Response")
    j = r.json()
    assert next(v == "please bby" for k, v in j["form"] if k == "cheese")


# Cookie send test


@pytest.mark.parametrize('server', [
    dict(steps=[accept_cookies_and_respond, finish])
], indirect=True)
async def test_cookie_dict_send(server: Server) -> None:

    cookies = {"Test-Cookie": "Test Cookie Value", "koooookie": "pie"}

    r = await asks.get(server.http_test_url, cookies=cookies)

    for cookie in r.cookies:
        assert cookie.name in cookies
        if cookie.value and " " in cookie.value:
            assert cookie.value == '"' + cookies[cookie.name] + '"'
        else:
            assert cookie.value == cookies[cookie.name]


# Custom headers test


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_header_set(server: Server) -> None:
    r = await asks.get(
        server.http_test_url, headers={"Asks-Header": "Test Header Value"}
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")
    j = r.json()

    assert any(k == "asks-header" for k, _ in j["headers"])
    assert "cOntenT-tYPe" in r.headers


# File send test


TEST_DIR = path.dirname(path.abspath(__file__))
TEST_FILE1 = path.join(TEST_DIR, "test_file1.txt")
TEST_FILE2 = path.join(TEST_DIR, "test_file2")


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_file_send_single(server: Server) -> None:
    r = await asks.post(server.http_test_url, files={"file_1": TEST_FILE1})
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_file_send_double(server: Server) -> None:
    r = await asks.post(
        server.http_test_url, files={
            "file_1": TEST_FILE1, "file_2": TEST_FILE2}
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])
    assert any(file_data["name"] == "file_2" for file_data in j["files"])

    file_data_1 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    file_data_2 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_2"
    )
    assert file_data_1["file"] == "Compooper"
    assert file_data_2["file"] == "My slug <3"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_file_send_file_and_form_data(server: Server) -> None:
    r = await asks.post(
        server.http_test_url,
        files={"file_1": TEST_FILE1, "data_1": "watwatwatwat=yesyesyes"},
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])
    assert any(form_data["name"] == "data_1" for form_data in j["forms"])

    file_data_1 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data_1["file"] == "Compooper"

    form_data_1 = next(
        form_data for form_data in j["forms"] if form_data["name"] == "data_1"
    )
    assert form_data_1["form_data"] == "watwatwatwat=yesyesyes"


# File send test new multipart API


TEST_DIR = path.dirname(path.abspath(__file__))
TEST_FILE1 = path.join(TEST_DIR, "test_file1.txt")
TEST_FILE2 = path.join(TEST_DIR, "test_file2")


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_single(server: Server) -> None:
    r = await asks.post(server.http_test_url, multipart={"file_1": Path(TEST_FILE1)})
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_single_already_open(server: Server) -> None:
    with open(TEST_FILE1, "rb") as f:
        r = await asks.post(server.http_test_url, multipart={"file_1": f})
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_single_already_open_async(server: Server) -> None:
    async with await open_file(TEST_FILE1, "rb") as f:
        r = await asks.post(server.http_test_url, multipart={"file_1": f})
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_raw_bytes(server: Server) -> None:
    r = await asks.post(
        server.http_test_url,
        multipart={
            "file_1": asks.multipart.MultipartData(
                b"Compooper", basename="in_memory.txt",
            )
        },
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_double(server: Server) -> None:
    r = await asks.post(
        server.http_test_url,
        multipart={"file_1": Path(TEST_FILE1), "file_2": Path(TEST_FILE2)},
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])
    assert any(file_data["name"] == "file_2" for file_data in j["files"])

    file_data_1 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    file_data_2 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_2"
    )
    assert file_data_1["file"] == "Compooper"
    assert file_data_2["file"] == "My slug <3"


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_multipart_send_file_and_form_data(server: Server) -> None:
    r = await asks.post(
        server.http_test_url,
        multipart={"file_1": Path(TEST_FILE1),
                   "data_1": "watwatwatwat=yesyesyes"},
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])
    assert any(form_data["name"] == "data_1" for form_data in j["forms"])

    file_data_1 = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data_1["file"] == "Compooper"

    form_data_1 = next(
        form_data for form_data in j["forms"] if form_data["name"] == "data_1"
    )
    assert form_data_1["form_data"] == "watwatwatwat=yesyesyes"


# JSON send test


@pytest.mark.parametrize('server', [dict(steps=[send_request_as_json, finish])], indirect=True)
async def test_json_send(server: Server) -> None:
    r = await asks.post(
        server.http_test_url, json={"key_1": True, "key_2": "cheesestring"}
    )
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    j = r.json()

    json_1 = next(iter(j["json"]))

    assert json_1["json"]["key_1"] is True
    assert json_1["json"]["key_2"] == "cheesestring"


# Test decompression


@pytest.mark.parametrize('server', [
    dict(steps=[partial(send_gzip, data="wolowolowolo"), finish])
], indirect=True)
async def test_gzip(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    assert r.text == "wolowolowolo"


@pytest.mark.parametrize('server', [
    dict(steps=[partial(send_deflate, data="wolowolowolo"), finish])
], indirect=True)
async def test_deflate(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    assert r.text == "wolowolowolo"


# Test chunks and streaming


@pytest.mark.parametrize('server', [
    dict(steps=[partial(send_chunked, data=["ham "] * 10), finish])
], indirect=True)
async def test_chunked(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    if not isinstance(r, Response):
        raise TypeError("expected Response")

    assert r.text == "ham ham ham ham ham ham ham ham ham ham "


@pytest.mark.parametrize('server', [
    dict(steps=[partial(send_chunked, data=["ham "] * 10), finish])
], indirect=True)
async def test_stream(server: Server) -> None:
    data = b""
    r = await asks.get(server.http_test_url, stream=True)
    if not isinstance(r, StreamResponse):
        raise TypeError("expected StreamResponse")

    async for chunk in r.body:
        data += chunk
    assert data == b"ham ham ham ham ham ham ham ham ham ham "


# Test callback


@pytest.mark.parametrize('server', [
    dict(steps=[partial(send_chunked, data=["ham "] * 10), finish])
], indirect=True)
async def test_callback(server: Server) -> None:
    callback_data = b""

    async def callback_example(chunk: bytearray) -> None:
        nonlocal callback_data
        callback_data += chunk

    await asks.get(server.http_test_url, callback=callback_example)
    assert callback_data == b"ham ham ham ham ham ham ham ham ham ham "


# Test connection close without content-length and transfer-encoding


@pytest.mark.parametrize('server', [
    dict(
        steps=[partial(send_200_blank_headers, headers=[
                       ("connection", "close")]), finish],
    )
], indirect=True)
async def test_connection_close_no_content_len(server: Server) -> None:
    r = await asks.get(server.http_test_url)
    if not isinstance(r, Response):
        raise TypeError("expected Response")
    assert r.text == "200"


# Session Tests
# =============

# Test Session with two pooled connections on ten get requests.


@pytest.mark.parametrize('server', [
    dict(
        steps=[partial(send_200_blank_headers, headers=[
                       ("connection", "close")]), finish],
        max_requests=10,
    )
], indirect=True)
async def test_session_smallpool(server: Server) -> None:
    async def worker(s: asks.Session) -> None:
        r = await s.get(path="/get")
        assert r.status_code == 200

    s = asks.Session(server.http_test_url, connections=2)
    async with create_task_group() as g:
        for _ in range(10):
            g.start_soon(worker, s)


# Test stateful Session


# TODO check the "" quoting of cookies here (probably in overly)
@pytest.mark.parametrize('server', [
    dict(steps=[accept_cookies_and_respond, finish])
], indirect=True)
async def test_session_stateful(server: Server) -> None:
    s = asks.Session(server.http_test_url, persist_cookies=True)
    await s.get(cookies={"Test-Cookie": "Test Cookie Value"})
    if not s._cookie_tracker:
        raise ValueError("expected s._cookie_tracker to not be None")
    assert ":".join(str(x)
                    for x in _TEST_LOC) in s._cookie_tracker.domain_dict.keys()
    assert (
        s._cookie_tracker.domain_dict[":".join(
            str(x) for x in _TEST_LOC)][0].value
        == '"Test Cookie Value"'
    )


# Test session instantiates outside event loop


def test_instantiate_session_outside_of_event_loop() -> None:
    try:
        asks.Session()
    except RuntimeError:
        pytest.fail("Could not instantiate Session outside of event loop")


async def test_session_unknown_kwargs() -> None:
    with pytest.raises(TypeError, match=r"request\(\) got .*"):
        session = asks.Session("https://httpbin.org/get")
        await session.request("GET", ko=7, foo=0, bar=3, shite=3)
        pytest.fail("Passing unknown kwargs does not raise TypeError")


async def test_recv_event_anyio2_end_of_stream() -> None:
    class MockH11Connection:
        def __init__(self) -> None:
            self.data: Optional[bytes] = None

        def next_event(self) -> type:
            if self.data == b"":
                return h11.PAUSED
            else:
                return h11.NEED_DATA

        def receive_data(self, data: bytes) -> None:
            self.data = data

    class MockSock:

        def __init__(self) -> None:
            self.host = "mocksock"
            self.port = "mocksock"
            self._active = True

        async def aclose(self) -> None:
            ...

        async def send(self, item: Optional[bytes]) -> None:
            ...

        async def receive(self) -> None:
            raise EndOfStream

    req = RequestProcessor(None, "get", "toot-toot", None)
    # TODO: fix the leaky abstraction!
    req.sock = cast(SocketLike, MockSock())

    h11_connection = MockH11Connection()
    # TODO: fix the leaky abstraction!
    event = await req._recv_event(cast(h11.Connection, h11_connection))
    assert cast(type, event) is h11.PAUSED
    assert h11_connection.data == b""
