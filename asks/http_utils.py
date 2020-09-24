"""
Utilities for handling some aspects of http
"""


__all__ = ["decompress", "decompress_one", "parse_content_encoding"]


import codecs
from zlib import decompressobj, MAX_WBITS

from .utils import processor


def parse_content_encoding(content_encoding: str) -> [str]:
    compressions = [x.strip() for x in content_encoding.split(",")]
    return compressions


@processor
def decompress(compressions, encoding=None):
    data = b""
    # https://tools.ietf.org/html/rfc7231
    # "If one or more encodings have been applied to a representation, the
    # sender that applied the encodings MUST generate a Content-Encoding
    # header field that lists the content codings in the order in which
    # they were applied."
    # Thus, reversed(compressions).
    decompressors = [
        decompress_one(compression) for compression in reversed(compressions)
    ]
    if encoding:
        decompressors.append(make_decoder_shim(encoding))
    while True:
        data = yield data
        for decompressor in decompressors:
            data = decompressor.send(data)


# https://tools.ietf.org/html/rfc7230#section-4.2.1 - #section-4.2.3

DECOMPRESS_WBITS = {
    "deflate": MAX_WBITS,
    "gzip": MAX_WBITS + 16,
    "x-gzip": MAX_WBITS + 16,
}


@processor
def decompress_one(compression):
    data = b""
    decompressor = decompressobj(wbits=DECOMPRESS_WBITS[compression])
    while True:
        data = yield data
        data = decompressor.decompress(data)
    yield decompressor.flush()


@processor
def make_decoder_shim(encoding):
    data = b""
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    while True:
        data = yield data
        data = decoder.decode(data)
    yield decoder.decode(b"", final=True)
