"""
Utilities for handling some aspects of http
"""


__all__ = ["decompress", "decompress_one", "parse_content_encoding"]


import codecs
from typing import Iterator, Optional
from zlib import MAX_WBITS, decompressobj

from .utils import processor


def parse_content_encoding(content_encoding: str) -> list[str]:
    compressions = [x.strip() for x in content_encoding.split(",")]
    return compressions


@processor
def decompress(
    compressions: list[str], encoding: Optional[str] = None
) -> Iterator[bytes]:
    encoded: Optional[bytes] = b""
    decoded: bytes = b""
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
        encoded = yield decoded
        if encoded is not None:
            for decompressor in decompressors:
                encoded = decompressor.send(encoded)
            decoded = encoded


# https://tools.ietf.org/html/rfc7230#section-4.2.1 - #section-4.2.3

DECOMPRESS_WBITS = {
    "deflate": MAX_WBITS,
    "gzip": MAX_WBITS + 16,
    "x-gzip": MAX_WBITS + 16,
}


@processor
def decompress_one(compression: str) -> Iterator[bytes]:
    encoded: Optional[bytes] = b""
    decoded: bytes = b""
    decompressor = decompressobj(wbits=DECOMPRESS_WBITS[compression])
    while True:
        encoded = yield decoded
        if encoded is not None:
            decoded = decompressor.decompress(encoded)
    yield decompressor.flush()


@processor
def make_decoder_shim(encoding: str) -> Iterator[str]:
    encoded: Optional[bytes] = b""
    decoded: str = ""
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    while True:
        encoded = yield decoded
        if encoded is not None:
            decoded = decoder.decode(encoded)
    yield decoder.decode(b"", final=True)
