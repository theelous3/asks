import sys

import curio
import pytest

sys.path.append('..')   # noqa
import asks
from asks.errors import TooManyRedirects, RequestTimeout


def curio_run(func):
    def func_wrapper(*args, **kwargs):
        return curio.run(func(*args, **kwargs))
    return func_wrapper


# GET tests
@curio_run
async def test_https_get():
    r = await asks.get('https://www.reddit.com')
    print(r.content)
    assert r.status_code == 200


@curio_run
async def test_https_get_alt():
    r = await asks.get('www.google.ie')
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
    r = await asks.get('http://httpbin.org/delay/1', timeout=2)
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

    r = await asks.get('http://httpbin.org/headers',
                       headers={'content-LENGTH': '0'})
    j = r.json()
    assert j['headers']['Content-Length'] == '0'


# File send test
@curio_run
async def test_file_send_single():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': 'test_file.txt'})
    print(r.text)
    j = r.json()
    assert j['files']['file_1'] == 'Compooper'


@curio_run
async def test_file_send_double():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': 'test_file.txt',
                               'file_2': 'testr'})
    print(r.text)
    j = r.json()
    assert j['files']['file_2'] == 'My slug <3'


@curio_run
async def test_file_and_data_send():
    r = await asks.post('http://httpbin.org/post',
                        files={'file_1': 'test_file.txt',
                               'data_1': 'watwatwatwat'})
    print(r.text)
    j = r.json()
    assert j['form']['data_1'] == 'watwatwatwat'


# JSON send test
@curio_run
async def test_json_send():
    r = await asks.post('http://httpbin.org/post',
                        json={'key_1': True,
                              'key_2': 'cheesestring'})
    print(r.text)
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
async def test_chunked_te():
    r = await asks.get('http://httpbin.org/range/3072')
    assert r.status_code == 200
