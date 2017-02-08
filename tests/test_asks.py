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


@curio_run
async def test_http_redirect():
    r = await asks.get('http://httpbin.org/redirect/1')
    assert r.history


@curio_run
async def test_http_max_redirect():
    with pytest.raises(TooManyRedirects):
        await asks.get('http://httpbin.org/redirect/2', max_redirects=1)


@curio_run
async def test_http_timeout():
    with pytest.raises(RequestTimeout):
        await asks.get('http://httpbin.org/delay/1', timeout=1)
