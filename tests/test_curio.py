# pylint: disable=wrong-import-position
from os import path

import curio
import pytest

import asks
from asks.errors import TooManyRedirects, RequestTimeout


def curio_run(func):
    def func_wrapper(*args, **kwargs):
        kernel = curio.Kernel()
        r = kernel.run(func(*args, **kwargs))
        kernel.run(shutdown=True)
    return func_wrapper


asks.init('curio')


# GET tests
@curio_run
async def test_https_get():
    r = await asks.get('https://www.reddit.com')
    assert r.status_code == 200


@curio_run
async def test_bad_www_and_schema_get():
    r = await asks.get('http://reddit.com')
    assert r.status_code == 200


@curio_run
async def test_https_get_alt():
    r = await asks.get('https://www.google.ie')
    assert r.status_code == 200


@curio_run
async def test_http_get():
    r = await asks.get('http://httpbin.org/get')
    assert r.status_code == 200


# Redirect tests
@curio_run
async def test_http_redirect():
    r = await asks.get('http://httpbin.org/redirect/1')
    assert len(r.history) == 1

    # make sure history doesn't persist across responses
    r.history.append('not a response obj')
    r = await asks.get('http://httpbin.org/redirect/1')
    assert len(r.history) == 1


@curio_run
async def test_http_max_redirect_error():
    with pytest.raises(TooManyRedirects):
        await asks.get('http://httpbin.org/redirect/2', max_redirects=1)


@curio_run
async def test_http_max_redirect():
    r = await asks.get('http://httpbin.org/redirect/1', max_redirects=2)
    assert r.status_code == 200


# Timeout tests
@curio_run
async def test_http_timeout_error():
    with pytest.raises(RequestTimeout):
        await asks.get('http://httpbin.org/delay/1', timeout=1)


@curio_run
async def test_http_timeout():
    r = await asks.get('http://httpbin.org/delay/1', timeout=10)
    assert r.status_code == 200


# Param set test
@curio_run
async def test_param_dict_set():
    r = await asks.get('http://httpbin.org/response-headers',
                       params={'cheese': 'the best'})
    j = r.json()
    assert j['cheese'] == 'the best'


# Data set test
@curio_run
async def test_data_dict_set():
    r = await asks.post('http://httpbin.org/post',
                        data={'cheese': 'please'})
    j = r.json()
    assert j['form']['cheese'] == 'please'


# Cookie send test
@curio_run
async def test_cookie_dict_send():
    r = await asks.get('http://httpbin.org/cookies',
                       cookies={'Test-Cookie': 'Test Cookie Value'})
    j = r.json()
    assert 'Test-Cookie' in j['cookies']


# Custom headers test
@curio_run
async def test_header_set():
    r = await asks.get('http://httpbin.org/headers',
                       headers={'Asks-Header': 'Test Header Value'})
    j = r.json()
    assert 'Asks-Header' in j['headers']
    assert 'cOntenT-tYPe' in r.headers


# File send test
TEST_DIR = path.dirname(path.abspath(__file__))
TEST_FILE1 = path.join(TEST_DIR, 'test_file1.txt')
TEST_FILE2 = path.join(TEST_DIR, 'test_file2')

@curio_run
async def test_file_send_single():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': TEST_FILE1})
    j = r.json()
    assert j['files']['file_1'] == 'Compooper'


@curio_run
async def test_file_send_double():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': TEST_FILE1,
                               'file_2': TEST_FILE2})
    j = r.json()
    assert j['files']['file_2'] == 'My slug <3'


@curio_run
async def test_file_and_data_send():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': TEST_FILE1,
                               'data_1': 'watwatwatwat'})
    j = r.json()
    assert j['form']['data_1'] == 'watwatwatwat'


# JSON send test
@curio_run
async def test_json_send():
    r = await asks.post('http://httpbin.org/post',
                        json={'key_1': True,
                              'key_2': 'cheesestring'})
    j = r.json()
    assert j['json']['key_1'] is True
    assert j['json']['key_2'] == 'cheesestring'


# Test decompression
@curio_run
async def test_gzip():
    r = await asks.get('http://httpbin.org/gzip')
    assert r.text


@curio_run
async def test_deflate():
    r = await asks.get('http://httpbin.org/deflate')
    assert r.text


# Test chunked TE
@curio_run
async def test_chunked_te():
    r = await asks.get('http://httpbin.org/range/3072')
    assert r.status_code == 200


# Test stream response
@curio_run
async def test_stream():
    img = b''
    r = await asks.get('http://httpbin.org/image/png', stream=True)
    async for chunk in r.body:
        img += chunk
    assert len(img) == 8090


# Test connection close without content-length and transfer-encoding
@curio_run
async def test_connection_close():
    r = await asks.get('https://www.ua-region.com.ua/search/?q=rrr')
    assert r.text


# Test callback
callback_data = b''
async def callback_example(chunk):
    global callback_data
    callback_data += chunk


@curio_run
async def test_callback():
    await asks.get('http://httpbin.org/image/png',
                   callback=callback_example)
    assert len(callback_data) == 8090


# Session Tests
# =============

# Test Session with two pooled connections on four get requests.
async def hsession_t_smallpool(s):
    r = await s.get(path='/get')
    assert r.status_code == 200


@curio_run
async def test_hsession_smallpool():
    from asks.sessions import Session
    s = Session('http://httpbin.org', connections=2)
    async with curio.TaskGroup() as g:
        for _ in range(10):
            await g.spawn(hsession_t_smallpool(s))


# Test stateful Session
async def hsession_t_stateful(s):
    r = await s.get()
    assert r.status_code == 200


@curio_run
async def test_session_stateful():
    from asks.sessions import Session
    s = Session(
        'https://google.ie', persist_cookies=True)
    async with curio.TaskGroup() as g:
        await g.spawn(hsession_t_stateful(s))
    assert 'www.google.ie' in s._cookie_tracker_obj.domain_dict.keys()

async def session_t_stateful_double_worker(s):
    r = await s.get()
    assert r.status_code == 200


@curio_run
async def test_session_stateful_double():
    from asks.sessions import Session
    s = Session('https://google.ie', persist_cookies=True)
    async with curio.TaskGroup() as g:
        for _ in range(4):
            await g.spawn(session_t_stateful_double_worker(s))


# Session Tests
# ==============

# Test Session with two pooled connections on four get requests.
async def session_t_smallpool(s):
    r = await s.get('http://httpbin.org/get')
    assert r.status_code == 200


@curio_run
async def test_Session_smallpool():
    from asks.sessions import Session
    s = Session(connections=2)
    for _ in range(10):
        await curio.spawn(session_t_smallpool(s))
