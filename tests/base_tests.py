from os import path

import pytest

import asks
from asks.errors import TooManyRedirects, RequestTimeout

TEST_DIR = path.dirname(path.abspath(__file__))
TEST_FILE1 = path.join(TEST_DIR, 'test_file1.txt')
TEST_FILE2 = path.join(TEST_DIR, 'test_file2')

class TestAsksMeta(type):
    def __new__(mcs, clsname, parents, dct):
        run = dct['run']
        for name, func in BaseTests.__dict__.items():
            if name.startswith('test'):
                dct[name] = run(func)
        return super().__new__(mcs, clsname, parents, dct)


class BaseTests:
    # GET tests
    async def test_https_get(self):
        r = await asks.get('https://www.reddit.com')
        assert r.status_code == 200


    async def test_bad_www_and_schema_get(self):
        r = await asks.get('http://reddit.com')
        assert r.status_code == 200


    async def test_https_get_alt(self):
        r = await asks.get('https://www.google.ie')
        assert r.status_code == 200


    async def test_http_get(self):
        r = await asks.get('http://httpbin.org/get')
        assert r.status_code == 200


    # Redirect tests
    async def test_http_redirect(self):
        r = await asks.get('http://httpbin.org/redirect/1')
        assert len(r.history) == 1

        # make sure history doesn't persist across responses
        r.history.append('not a response obj')
        r = await asks.get('http://httpbin.org/redirect/1')
        assert len(r.history) == 1


    async def test_http_max_redirect_error(self):
        with pytest.raises(TooManyRedirects):
            await asks.get('http://httpbin.org/redirect/2', max_redirects=1)


    async def test_http_max_redirect(self):
        r = await asks.get('http://httpbin.org/redirect/1', max_redirects=2)
        assert r.status_code == 200


    # Timeout tests
    async def test_http_timeout_error(self):
        with pytest.raises(RequestTimeout):
            await asks.get('http://httpbin.org/delay/1', timeout=1)


    async def test_http_timeout(self):
        r = await asks.get('http://httpbin.org/delay/1', timeout=10)
        assert r.status_code == 200


    # Param set test
    async def test_param_dict_set(self):
        r = await asks.get('http://httpbin.org/response-headers',
                           params={'cheese': 'the best'})
        j = r.json()
        assert j['cheese'] == 'the best'


    # Data set test
    async def test_data_dict_set(self):
        r = await asks.post('http://httpbin.org/post',
                            data={'cheese': 'please'})
        j = r.json()
        assert j['form']['cheese'] == 'please'


    # Cookie send test
    async def test_cookie_dict_send(self):
        r = await asks.get('http://httpbin.org/cookies',
                           cookies={'Test-Cookie': 'Test Cookie Value'})
        j = r.json()
        assert 'Test-Cookie' in j['cookies']


    # Custom headers test
    async def test_header_set(self):
        r = await asks.get('http://httpbin.org/headers',
                           headers={'Asks-Header': 'Test Header Value'})
        j = r.json()
        assert 'Asks-Header' in j['headers']
        assert 'cOntenT-tYPe' in r.headers


    async def test_file_send_single(self):
        r = await asks.post('http://httpbin.org/post',
                            files={'file_1': TEST_FILE1})
        j = r.json()
        assert j['files']['file_1'] == 'Compooper'


    async def test_file_send_double(self):
        r = await asks.post('http://httpbin.org/post',
                            files={'file_1': TEST_FILE1,
                                   'file_2': TEST_FILE2})
        j = r.json()
        assert j['files']['file_2'] == 'My slug <3'


    async def test_file_and_data_send(self):
        r = await asks.post('http://httpbin.org/post',
                            files={'file_1': TEST_FILE1,
                                   'data_1': 'watwatwatwat'})
        j = r.json()
        assert j['form']['data_1'] == 'watwatwatwat'


    # JSON send test
    async def test_json_send(self):
        r = await asks.post('http://httpbin.org/post',
                            json={'key_1': True,
                                  'key_2': 'cheesestring'})
        j = r.json()
        assert j['json']['key_1'] is True
        assert j['json']['key_2'] == 'cheesestring'


    # Test decompression
    async def test_gzip(self):
        r = await asks.get('http://httpbin.org/gzip')
        assert r.text


    async def test_deflate(self):
        r = await asks.get('http://httpbin.org/deflate')
        assert r.text


    # Test chunked TE
    async def test_chunked_te(self):
        r = await asks.get('http://httpbin.org/range/3072')
        assert r.status_code == 200


    # Test stream response
    async def test_stream(self):
        img = b''
        r = await asks.get('http://httpbin.org/image/png', stream=True)
        async for chunk in r.body:
            img += chunk
        assert len(img) == 8090


    # Test connection close without content-length and transfer-encoding
    async def test_connection_close(self):
        r = await asks.get('https://www.ua-region.com.ua/search/?q=rrr')
        assert r.text


    async def test_callback(self):
        callback_data = b''
        async def callback_example(chunk):
            nonlocal callback_data
            callback_data += chunk

        await asks.get('http://httpbin.org/image/png',
                       callback=callback_example)
        assert len(callback_data) == 8090


# Session Tests
# =============

async def hsession_t_smallpool(s):
    r = await s.get(path='/get')
    assert r.status_code == 200


# Test stateful Session
async def hsession_t_stateful(s):
    r = await s.get()
    assert r.status_code == 200


async def session_t_stateful_double_worker(s):
    r = await s.get()
    assert r.status_code == 200


async def session_t_smallpool(s):
    r = await s.get('http://httpbin.org/get')
    assert r.status_code == 200
