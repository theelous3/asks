import zlib
import gzip

import pytest

from asks import http_utils, Session

INPUT_DATA = b"abcdefghijklmnopqrstuvwxyz"
UNICODE_INPUT_DATA = "\U0001f408\U0001F431" * 5


@pytest.mark.parametrize(
    "compressor,name", [(zlib.compress, "deflate"), (gzip.compress, "gzip")]
)
def test_decompress_one_zlib(compressor, name):
    data = zlib.compress(INPUT_DATA)
    decompressor = http_utils.decompress_one("deflate")
    result = b""
    for i in range(len(data)):
        b = data[i : i + 1]
        result += decompressor.send(b)
    assert result == INPUT_DATA


def test_decompress():
    # we don't expect to see multiple compression types in the wild
    # but test anyway
    data = zlib.compress(gzip.compress(INPUT_DATA))
    decompressor = http_utils.decompress(["gzip", "deflate"])
    result = b""
    for i in range(len(data)):
        b = data[i : i + 1]
        result += decompressor.send(b)
    assert result == INPUT_DATA


def test_decompress_decoding():
    data = zlib.compress(UNICODE_INPUT_DATA.encode("utf-8"))
    decompressor = http_utils.decompress(["deflate"], encoding="utf-8")
    result = ""
    for i in range(len(data)):
        b = data[i : i + 1]
        res = decompressor.send(b)
        result += res
    assert result == UNICODE_INPUT_DATA


@pytest.mark.parametrize(
    "url_segments,expected",
    [
        (
            ("http://example.com", "", ""),
            "http://example.com"
        ),
        (
            ("http://example.com", "some_endpoint", ""),
            "http://example.com/some_endpoint"
        ),
        (
            ("http://example.com/", "/some_endpoint", ""),
            "http://example.com/some_endpoint"
        ),
        (
            ("http://example.com/", "/some_endpoint", "some/path"),
            "http://example.com/some_endpoint/some/path"
        ),
        (
            ("http://example.com/", "/some_endpoint", "/some/path/"),
            "http://example.com/some_endpoint/some/path"
        ),
        (
            ("http://example.com/", "/some_endpoint/", "/some/path/"),
            "http://example.com/some_endpoint/some/path"
        ),
        (
            ("http://example.com/", "", "/some/path/"),
            "http://example.com/some/path"
        )
    ]
)
def test_api_url_construction(url_segments, expected):
    base_location, endpoint, path = url_segments
    session = Session(base_location=base_location, endpoint=endpoint)
    constructed_url = session._make_url(path)
    assert constructed_url == expected


def test_api_url_construction_but_no_base():
    base_location, endpoint, path = ("", "/some_endpoint", "/some_path")
    session = Session(base_location=base_location, endpoint=endpoint)
    with pytest.raises(ValueError):
        constructed_url = session._make_url(path)
