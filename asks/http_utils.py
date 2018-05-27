"""
Utilities for handling some aspects of http
"""


__all__ = ['decompress', 'parse_content_encoding']


from gzip import decompress as gdecompress
from zlib import decompress as zdecompress

from .utils import processor


_compression_mapping = {
    'gzip': gdecompress,
    'deflate': zdecompress
}


def parse_content_encoding(content_encoding: str) -> [str]:
    compressions = [x.strip() for x in content_encoding.split(',')]
    return compressions


@processor
def decompress(compressions, encoding=None):
    data = b''
    while True:
        if encoding:
            data = yield data.decode(encoding, errors='replace')
        else:
            data = yield data
        for compression in compressions:
            if compression in _compression_mapping:
                data = _compression_mapping[compression](data)
