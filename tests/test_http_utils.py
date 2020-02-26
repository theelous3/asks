import zlib
import gzip

import pytest

from asks import http_utils

INPUT_DATA = b'abcdefghijklmnopqrstuvwxyz'
UNICODE_INPUT_DATA = '\U0001f408\U0001F431' * 5

@pytest.mark.parametrize('compressor,name',
                         [(zlib.compress, 'deflate'),
                          (gzip.compress, 'gzip')])
def test_decompress_one_zlib(compressor, name):
    data = zlib.compress(INPUT_DATA)
    decompressor = http_utils.decompress_one('deflate')
    result = b''
    for i in range(len(data)):
        b = data[i:i+1]
        result += decompressor.send(b)
    assert result == INPUT_DATA

def test_decompress():
    # we don't expect to see multiple compression types in the wild
    # but test anyway
    data = zlib.compress(gzip.compress(INPUT_DATA))
    decompressor = http_utils.decompress(['gzip', 'deflate'])
    result = b''
    for i in range(len(data)):
        b = data[i:i+1]
        result += decompressor.send(b)
    assert result == INPUT_DATA

def test_decompress_decoding():
    data = zlib.compress(UNICODE_INPUT_DATA.encode('utf-8'))
    decompressor = http_utils.decompress(['deflate'], encoding='utf-8')
    result = ''
    for i in range(len(data)):
        b = data[i:i+1]
        res = decompressor.send(b)
        result += res
    assert result == UNICODE_INPUT_DATA
