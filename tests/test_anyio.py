# pylint: disable=wrong-import-position

import ssl
from os import path
from functools import partial

import pytest

from anyio import create_task_group
import curio

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
from asks.errors import TooManyRedirects, BadStatus, RequestTimeout


_TEST_LOC = ("localhost", 25001)
_SSL_CONTEXT = ssl.create_default_context(cadata=default_ssl_cert)


def curio_run(func):
    def func_wrapper(*args, **kwargs):
        kernel = curio.Kernel()
        kernel.run(func(*args, **kwargs))
        kernel.run(shutdown=True)

    return func_wrapper


@Server(_TEST_LOC, steps=[send_200, finish])
@curio_run
async def test_http_get(server):
    r = await asks.get(server.http_test_url)
    assert r.status_code == 200


# GET tests


@Server(_TEST_LOC, steps=[send_200, finish], socket_wrapper=ssl_socket_wrapper)
@curio_run
async def test_https_get(server):
    # If we use ssl_context= to trust the CA, then we can successfully do a
    # GET over https.
    r = await asks.get(server.https_test_url, ssl_context=_SSL_CONTEXT)
    assert r.status_code == 200


@Server(_TEST_LOC, steps=[send_200, finish], socket_wrapper=ssl_socket_wrapper)
@curio_run
async def test_https_get_checks_cert(server):
    try:
        expected_error = ssl.SSLCertVerificationError
    except AttributeError:
        # If we're running in Python <3.7, we won't have the specific error
        # that will be raised, but we can expect it to raise an SSLError
        # nonetheless
        expected_error = ssl.SSLError

    # The server's certificate isn't signed by any real CA. By default, asks
    # should notice that, and raise an error.
    with pytest.raises(expected_error):
        await asks.get(server.https_test_url)


# @curio_run
# async def test_bad_www_and_schema_get():
#     r = await asks.get('http://reddit.com')
#     assert r.status_code == 200


@Server(_TEST_LOC, steps=[send_400, finish])
@curio_run
async def test_http_get_client_error(server):
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match("400 Client Error: BAD REQUEST")
    assert excinfo.value.status_code == 400


@Server(_TEST_LOC, steps=[send_500, finish])
@curio_run
async def test_http_get_server_error(server):
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match("500 Server Error: INTERNAL SERVER ERROR")
    assert excinfo.value.status_code == 500


# Redirect tests


@Server(
    _TEST_LOC,
    max_requests=4,
    steps=[
        [(HttpMethods.GET, "/redirect_1"), send_303, finish],
        [(HttpMethods.GET, "/"), send_200, finish],
        [(HttpMethods.GET, "/redirect_1"), send_303, finish],
        [(HttpMethods.GET, "/"), send_200, finish],
    ],
    ordered_steps=True,
)
@curio_run
async def test_http_redirect(server):
    r = await asks.get(server.http_test_url + "/redirect_1")
    assert len(r.history) == 1

    # make sure history doesn't persist across responses
    r.history.append("not a response obj")
    r = await asks.get(server.http_test_url + "/redirect_1")
    assert len(r.history) == 1


@Server(
    _TEST_LOC,
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
@curio_run
async def test_http_max_redirect_error(server):
    with pytest.raises(TooManyRedirects) as err:
        r = await asks.get(server.http_test_url + "/redirect_max", max_redirects=1)
    resp = err.value.response
    assert resp.history[0].url == server.http_test_url + "/redirect_max"
    assert len(err.value.response.history) == 1

@Server(
    _TEST_LOC,
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
@curio_run
async def test_redirect_relative_url(server):
    r = await asks.get(server.http_test_url + "/path/redirect", max_redirects=1)
    assert len(r.history) == 1
    assert r.url == "http://{0}:{1}/foo/bar".format(*_TEST_LOC)


@Server(
    _TEST_LOC,
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
@curio_run
async def test_http_under_max_redirect(server):
    r = await asks.get(server.http_test_url + "/redirect_once", max_redirects=2)
    assert r.status_code == 200


# Timeout tests


@Server(_TEST_LOC, steps=[delay(2), send_200, finish])
@curio_run
async def test_http_timeout_error(server):
    with pytest.raises(RequestTimeout):
        await asks.get(server.http_test_url, timeout=1)


@Server(_TEST_LOC, steps=[send_200, finish])
@curio_run
async def test_http_timeout(server):
    r = await asks.get(server.http_test_url, timeout=10)
    assert r.status_code == 200


# Param set test


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_param_dict_set(server):
    r = await asks.get(server.http_test_url, params={"cheese": "the best"})
    j = r.json()
    assert next(v == "the best" for k, v in j["params"] if k == "cheese")


# Data set test


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_data_dict_set(server):
    r = await asks.post(server.http_test_url, data={"cheese": "please bby"})
    j = r.json()
    assert next(v == "please bby" for k, v in j["form"] if k == "cheese")


# Cookie send test


@Server(_TEST_LOC, steps=[accept_cookies_and_respond, finish])
@curio_run
async def test_cookie_dict_send(server):

    cookies = {"Test-Cookie": "Test Cookie Value", "koooookie": "pie"}

    r = await asks.get(server.http_test_url, cookies=cookies)

    for cookie in r.cookies:
        assert cookie.name in cookies
        if " " in cookie.value:
            assert cookie.value == '"' + cookies[cookie.name] + '"'
        else:
            assert cookie.value == cookies[cookie.name]


# Custom headers test


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_header_set(server):
    r = await asks.get(
        server.http_test_url, headers={"Asks-Header": "Test Header Value"}
    )
    j = r.json()

    assert any(k == "asks-header" for k, _ in j["headers"])
    assert "cOntenT-tYPe" in r.headers


# File send test


TEST_DIR = path.dirname(path.abspath(__file__))
TEST_FILE1 = path.join(TEST_DIR, "test_file1.txt")
TEST_FILE2 = path.join(TEST_DIR, "test_file2")


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_file_send_single(server):
    r = await asks.post(server.http_test_url, files={"file_1": TEST_FILE1})
    j = r.json()

    assert any(file_data["name"] == "file_1" for file_data in j["files"])

    file_data = next(
        file_data for file_data in j["files"] if file_data["name"] == "file_1"
    )
    assert file_data["file"] == "Compooper"


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_file_send_double(server):
    r = await asks.post(
        server.http_test_url, files={"file_1": TEST_FILE1, "file_2": TEST_FILE2}
    )
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


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_file_send_file_and_form_data(server):
    r = await asks.post(
        server.http_test_url,
        files={"file_1": TEST_FILE1, "data_1": "watwatwatwat=yesyesyes"},
    )
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


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_json_send(server):
    r = await asks.post(
        server.http_test_url, json={"key_1": True, "key_2": "cheesestring"}
    )
    j = r.json()

    json_1 = next(iter(j["json"]))

    assert json_1["json"]["key_1"] is True
    assert json_1["json"]["key_2"] == "cheesestring"


# Test decompression


@Server(_TEST_LOC, steps=[partial(send_gzip, data="wolowolowolo"), finish])
@curio_run
async def test_gzip(server):
    r = await asks.get(server.http_test_url)
    assert r.text == "wolowolowolo"


@Server(_TEST_LOC, steps=[partial(send_deflate, data="wolowolowolo"), finish])
@curio_run
async def test_deflate(server):
    r = await asks.get(server.http_test_url)
    assert r.text == "wolowolowolo"


# Test chunks and streaming


@Server(_TEST_LOC, steps=[partial(send_chunked, data=["ham "] * 10), finish])
@curio_run
async def test_chunked(server):
    r = await asks.get(server.http_test_url)
    assert r.text == "ham ham ham ham ham ham ham ham ham ham "


@Server(_TEST_LOC, steps=[partial(send_chunked, data=["ham "] * 10), finish])
@curio_run
async def test_stream(server):
    data = b""
    r = await asks.get(server.http_test_url, stream=True)
    async for chunk in r.body:
        data += chunk
    assert data == b"ham ham ham ham ham ham ham ham ham ham "


# Test callback


@Server(_TEST_LOC, steps=[partial(send_chunked, data=["ham "] * 10), finish])
@curio_run
async def test_callback(server):
    async def callback_example(chunk):
        nonlocal callback_data
        callback_data += chunk

    callback_data = b""
    await asks.get(server.http_test_url, callback=callback_example)
    assert callback_data == b"ham ham ham ham ham ham ham ham ham ham "


# Test connection close without content-length and transfer-encoding


@Server(
    _TEST_LOC,
    steps=[partial(send_200_blank_headers, headers=[("connection", "close")]), finish],
)
@curio_run
async def test_connection_close_no_content_len(server):
    r = await asks.get(server.http_test_url)
    assert r.text == "200"


# Session Tests
# =============

# Test Session with two pooled connections on ten get requests.


@Server(
    _TEST_LOC,
    steps=[partial(send_200_blank_headers, headers=[("connection", "close")]), finish],
    max_requests=10,
)
@curio_run
async def test_session_smallpool(server):
    async def worker(s):
        r = await s.get(path="/get")
        assert r.status_code == 200

    s = asks.Session(server.http_test_url, connections=2)
    async with create_task_group() as g:
        for _ in range(10):
            await g.spawn(worker, s)


# Test stateful Session


# TODO check the "" quoting of cookies here (probably in overly)
@Server(_TEST_LOC, steps=[accept_cookies_and_respond, finish])
@curio_run
async def test_session_stateful(server):
    s = asks.Session(server.http_test_url, persist_cookies=True)
    await s.get(cookies={"Test-Cookie": "Test Cookie Value"})
    assert ":".join(str(x) for x in _TEST_LOC) in s._cookie_tracker.domain_dict.keys()
    assert (
        s._cookie_tracker.domain_dict[":".join(str(x) for x in _TEST_LOC)][0].value
        == '"Test Cookie Value"'
    )


# Test session instantiates outside event loop


def test_instantiate_session_outside_of_event_loop():
    try:
        asks.Session()
    except RuntimeError:
        pytest.fail("Could not instantiate Session outside of event loop")


@curio_run
async def test_session_unknown_kwargs():
    with pytest.raises(TypeError, match="request\(\) got .*"):
        session = asks.Session("https://httpbin.org/get")
        await session.request("GET", ko=7, foo=0, bar=3, shite=3)
        pytest.fail("Passing unknown kwargs does not raise TypeError")

