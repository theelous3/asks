"""Tests for the generation of multipart/form-data request bodies."""
from collections import OrderedDict
from io import BytesIO
from pathlib import Path

import pytest
from anyio import open_file

from asks.multipart import MultipartData, build_multipart_body

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def dummy_file_path(tmpdir_factory):
    dummy = tmpdir_factory.mktemp("multipart").join("test.txt")

    with open(dummy, "w") as f:
        print("dummyfile", file=f)

    return Path(dummy)


async def test_multipart_body_dummy_file():
    assert (
        await build_multipart_body(
            values=OrderedDict(
                {
                    "file": MultipartData(
                        b"dummyfile\n", mime_type="text/plain", basename="test.txt"
                    ),
                }
            ),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!5649",
        )
        == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'
    )


async def test_multipart_body_with_not_file_argument():
    assert (
        await build_multipart_body(
            values=OrderedDict(
                {
                    "file": MultipartData(
                        b"dummyfile\n", mime_type="text/plain", basename="test.txt"
                    ),
                    "notfile": "abc",
                }
            ),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!8423",
        )
        == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'
    )


async def test_multipart_body_with_file_like_argument():
    # Simulate an open file with a BytesIO.
    f = BytesIO(b"dummyfile\n")
    f.name = "test.txt"

    assert (
        await build_multipart_body(
            values=OrderedDict({"file": f, "notfile": "abc",}),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!8423",
        )
        == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'
    )


async def test_multipart_body_with_path_argument(dummy_file_path):
    assert (
        await build_multipart_body(
            values=OrderedDict({"file": dummy_file_path, "notfile": "abc",}),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!8423",
        )
        == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'
    )


async def test_multipart_body_with_multiple_arguments(dummy_file_path):
    # Simulate an open file with a BytesIO.
    f = BytesIO(b"dummyfile2\n")
    f.name = "test.jpg"

    assert (
        await build_multipart_body(
            values=OrderedDict(
                {"file": dummy_file_path, "file2": f, "notfile": "abc", "integer": 3,}
            ),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!8423",
        )
        == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file2"; filename="test.jpg"\r\nContent-Type: image/jpeg\r\n\r\ndummyfile2\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="integer"\r\n\r\n3\r\n--8banana133744910kmmr13a56!102!8423--\r\n'
    )


async def test_multipart_body_with_custom_metadata():
    # Simulate an open file with a BytesIO.
    f = BytesIO(b"dummyfile but it is a jpeg\n")
    f.name = "test.jpg"

    assert (
        await build_multipart_body(
            values=OrderedDict(
                {"file": MultipartData(f, mime_type="text/plain", basename="test.txt"),}
            ),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!5649",
        )
        == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile but it is a jpeg\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'
    )


async def test_multipart_body_with_real_test_file(dummy_file_path):
    assert (
        await build_multipart_body(
            values=OrderedDict({"file": dummy_file_path,}),
            encoding="utf8",
            boundary_data="8banana133744910kmmr13a56!102!5649",
        )
        == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'
    )


async def test_multipart_body_with_real_pre_opened_test_file(dummy_file_path):
    async with await open_file(dummy_file_path, "rb") as f:
        assert (
            await build_multipart_body(
                values=OrderedDict({"file": f,}),
                encoding="utf8",
                boundary_data="8banana133744910kmmr13a56!102!5649",
            )
            == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\nContent-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'
        )
