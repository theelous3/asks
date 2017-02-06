import sys
sys.path.append('..')
import curio

import asks
from asks.exceptions import TooManyRedirects, RequestTimeout

import pytest


def curio_run(func):
    def func_wrapper(*args, **kwargs):
        return curio.run(func(*args, **kwargs))
    return func_wrapper


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
        r = await asks.get('http://httpbin.org/redirect/2', max_redirects=1)


@curio_run
async def test_http_timeout():
    with pytest.raises(RequestTimeout):
        r = await asks.get('http://httpbin.org/delay/1', timeout=1)
