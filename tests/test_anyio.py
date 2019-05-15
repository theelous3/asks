# pylint: disable=wrong-import-position

import ssl
from os import path
from tempfile import NamedTemporaryFile
from functools import partial

import pytest

from anyio import create_task_group

from overly import (
    Server,
    ssl_socket_wrapper,
    default_ssl_cert,
    send_200,
    send_204,
    send_303,
    send_400,
    send_404,
    send_500,
    delay,
    send_request_as_json,
    accept_cookies_and_respond,
    finish,
    HttpMethods,

)


import asks
import curio
from asks.errors import TooManyRedirects, BadStatus, RequestTimeout


_TEST_LOC = ("localhost", 25001)
_SSL_CONTEXT = ssl.create_default_context(cadata=default_ssl_cert)


import time

def curio_run(func):
    def func_wrapper(*args, **kwargs):
        kernel = curio.Kernel()
        r = kernel.run(func(*args, **kwargs))
        kernel.run(shutdown=True)
    return func_wrapper



@Server(_TEST_LOC, steps=[send_200, finish])
@curio_run
@pytest.mark.anyio
async def test_http_get(server):
    r = await asks.get(server.http_test_url)
    assert r.status_code == 200


# GET tests
@Server(_TEST_LOC, steps=[send_200, finish], socket_wrapper=ssl_socket_wrapper)
@curio_run
@pytest.mark.anyio
async def test_https_get(server):
    r = await asks.get(server.https_test_url, ssl_context=_SSL_CONTEXT)
    assert r.status_code == 200


# @curio_run
# @pytest.mark.anyio
# async def test_bad_www_and_schema_get():
#     r = await asks.get('http://reddit.com')
#     assert r.status_code == 200


@Server(_TEST_LOC, steps=[send_400, finish])
@curio_run
@pytest.mark.anyio
async def test_http_get_client_error(server):
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match('400 Client Error: BAD REQUEST')
    assert excinfo.value.status_code == 400


@Server(_TEST_LOC, steps=[send_500, finish])
@curio_run
@pytest.mark.anyio
async def test_http_get_server_error(server):
    r = await asks.get(server.http_test_url)
    with pytest.raises(BadStatus) as excinfo:
        r.raise_for_status()
    assert excinfo.match('500 Server Error: INTERNAL SERVER ERROR')
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
    r = await asks.get(server.http_test_url + '/redirect_1')
    assert len(r.history) == 1

    # make sure history doesn't persist across responses
    r.history.append('not a response obj')
    r = await asks.get(server.http_test_url + '/redirect_1')
    assert len(r.history) == 1


@Server(
    _TEST_LOC,
    max_requests=3,
    steps=[
        [(HttpMethods.GET, "/redirect_max"), partial(send_303, headers=[('location', 'redirect_max1')]), finish],
        [(HttpMethods.GET, "/redirect_max1"), partial(send_303, headers=[('location', 'redirect_max')]), finish],
    ],
)
@curio_run
async def test_http_max_redirect_error(server):
    with pytest.raises(TooManyRedirects):
        await asks.get(server.http_test_url + '/redirect_max', max_redirects=1)


@Server(
    _TEST_LOC,
    max_requests=2,
    steps=[
        [(HttpMethods.GET, "/redirect_once"), partial(send_303, headers=[('location', '/')]), finish],
        [(HttpMethods.GET, "/"), send_200, finish],
    ],
)
@curio_run
async def test_http_under_max_redirect(server):
    r = await asks.get(server.http_test_url + '/redirect_once', max_redirects=2)
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
    r = await asks.get(server.http_test_url,
                       params={'cheese': 'the best'})
    j = r.json()
    assert next(v == 'the best' for k, v in j['params'] if k == 'cheese')


# Data set test


@Server(_TEST_LOC, steps=[send_request_as_json, finish])
@curio_run
async def test_data_dict_set(server):
    r = await asks.post(server.http_test_url,
                        data={'cheese': 'please bby'})
    j = r.json()
    assert next(v == 'please bby' for k, v in j['form'] if k == 'cheese')


# Cookie send test


@Server(_TEST_LOC, steps=[accept_cookies_and_respond, finish])
@curio_run
@pytest.mark.anyio
async def test_cookie_dict_send(server):
    r = await asks.get(server.http_test_url,
                       cookies={
                           'Test-Cookie': 'Test Cookie Value',
                           'koooookie': 'pie'
                        })
    j = r.json()
    assert r.headers['cookie'] == r"""Test-Cookie="Test Cookie Value"; koooookie=pie"""
    assert 'Test-Cookie' in j['cookies']


# # Custom headers test
# @pytest.mark.anyio
# async def test_header_set():
#     r = await asks.get('http://httpbin.org/headers',
#                        headers={'Asks-Header': 'Test Header Value'})
#     j = r.json()
#     assert 'Asks-Header' in j['headers']
#     assert 'cOntenT-tYPe' in r.headers


# # File send test
# TEST_DIR = path.dirname(path.abspath(__file__))
# TEST_FILE1 = path.join(TEST_DIR, 'test_file1.txt')
# TEST_FILE2 = path.join(TEST_DIR, 'test_file2')


# @pytest.mark.anyio
# async def test_file_send_single():
#     r = await asks.post('http://httpbin.org/post',
#                         files={'file_1': TEST_FILE1})
#     j = r.json()
#     assert j['files']['file_1'] == 'Compooper'


# @pytest.mark.anyio
# async def test_file_send_double():
#     r = await asks.post('http://httpbin.org/post',
#                         files={'file_1': TEST_FILE1,
#                                'file_2': TEST_FILE2})
#     j = r.json()
#     assert j['files']['file_2'] == 'My slug <3'


# @pytest.mark.anyio
# async def test_file_and_data_send():
#     r = await asks.post('http://httpbin.org/post',
#                         files={'file_1': TEST_FILE1,
#                                'data_1': 'watwatwatwat'})
#     j = r.json()
#     assert j['form']['data_1'] == 'watwatwatwat'


# # JSON send test
# @pytest.mark.anyio
# async def test_json_send():
#     r = await asks.post('http://httpbin.org/post',
#                         json={'key_1': True,
#                               'key_2': 'cheesestring'})
#     j = r.json()
#     assert j['json']['key_1'] is True
#     assert j['json']['key_2'] == 'cheesestring'


# # Test decompression
# @pytest.mark.anyio
# async def test_gzip():
#     r = await asks.get('http://httpbin.org/gzip')
#     assert r.text


# @pytest.mark.anyio
# async def test_deflate():
#     r = await asks.get('http://httpbin.org/deflate')
#     assert r.text


# # Test chunked TE
# @pytest.mark.anyio
# async def test_chunked_te():
#     r = await asks.get('http://httpbin.org/range/3072')
#     assert r.status_code == 200


# # Test stream response
# @pytest.mark.anyio
# async def test_stream():
#     img = b''
#     r = await asks.get('http://httpbin.org/image/png', stream=True)
#     async for chunk in r.body:
#         img += chunk
#     assert len(img) == 8090


# # Test connection close without content-length and transfer-encoding
# @pytest.mark.anyio
# async def test_connection_close():
#     r = await asks.get('https://www.ua-region.com.ua/search/?q=rrr')
#     assert r.text


# # Test callback
# @pytest.mark.anyio
# async def test_callback():
#     async def callback_example(chunk):
#         nonlocal callback_data
#         callback_data += chunk

#     callback_data = b''
#     await asks.get('http://httpbin.org/image/png',
#                    callback=callback_example)
#     assert len(callback_data) == 8090


# # Session Tests
# # =============

# # Test Session with two pooled connections on four get requests.
# async def hsession_t_smallpool(s):
#     r = await s.get(path='/get')
#     assert r.status_code == 200


# @pytest.mark.anyio
# async def test_hsession_smallpool():
#     from asks.sessions import Session
#     s = Session('http://httpbin.org', connections=2)
#     async with create_task_group() as g:
#         for _ in range(10):
#             await g.spawn(hsession_t_smallpool, s)


# # Test stateful Session
# async def hsession_t_stateful(s):
#     r = await s.get()
#     assert r.status_code == 200


# @pytest.mark.anyio
# async def test_session_stateful():
#     from asks.sessions import Session
#     s = Session(
#         'https://google.ie', persist_cookies=True)
#     async with create_task_group() as g:
#         await g.spawn(hsession_t_stateful, s)
#     assert 'www.google.ie' in s._cookie_tracker.domain_dict.keys()


# async def session_t_stateful_double_worker(s):
#     r = await s.get()
#     assert r.status_code == 200


# @pytest.mark.anyio
# async def test_session_stateful_double():
#     from asks.sessions import Session
#     s = Session('https://google.ie', persist_cookies=True)
#     async with create_task_group() as g:
#         for _ in range(4):
#             await g.spawn(session_t_stateful_double_worker, s)


# # Test Session with two pooled connections on four get requests.
# async def session_t_smallpool(s):
#     r = await s.get('http://httpbin.org/get')
#     assert r.status_code == 200


# @pytest.mark.anyio
# async def test_Session_smallpool():
#     from asks.sessions import Session
#     s = Session(connections=2)
#     async with create_task_group() as g:
#         for _ in range(10):
#             await g.spawn(session_t_smallpool, s)


# def test_instantiate_session_outside_of_event_loop():
#     from asks.sessions import Session
#     try:
#         Session()
#     except RuntimeError:
#         pytest.fail("Could not instantiate Session outside of event loop")
