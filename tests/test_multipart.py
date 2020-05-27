"""Tests for the generation of multipart/form-data request bodies."""
from collections import OrderedDict
from io import BytesIO
from unittest.mock import MagicMock, patch
from pathlib import Path

import pytest

from anyio import aopen
from asks.multipart import build_multipart_body, MultipartData

TEST_DIR = Path(__file__).absolute().parent


@pytest.fixture
def mock_aopen():
    async def mock_aopen(*args, **kwargs):
        class FakeAsyncFile:
            async def read(self):
                return b'dummyfile\n'

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args, **kwargs):
                pass

            name = 'test.txt'

        return FakeAsyncFile()

    with patch('asks.multipart.aopen', mock_aopen):
        yield mock_aopen


@pytest.mark.curio
async def test_multipart_body_dummy_file():
    assert await build_multipart_body(
        values=OrderedDict({
            'file': MultipartData(
                b'dummyfile\n',
                mime_type='text/plain',
                basename='test.txt'
            ),
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!5649',
    ) == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_not_file_argument():
    assert await build_multipart_body(
        values=OrderedDict({
            'file': MultipartData(
                b'dummyfile\n',
                mime_type='text/plain',
                basename='test.txt'
            ),
            'notfile': 'abc',
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!8423',
    ) == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_file_like_argument():
    # Simulate an open file with a BytesIO.
    f = BytesIO(b'dummyfile\n')
    f.name = 'test.txt'

    assert await build_multipart_body(
        values=OrderedDict({
            'file': f,
            'notfile': 'abc',
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!8423',
    ) == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_path_argument(mock_aopen):
    assert await build_multipart_body(
        values=OrderedDict({
            'file': Path('test.txt'),
            'notfile': 'abc',
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!8423',
    ) == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423--\r\n'



@pytest.mark.curio
async def test_multipart_body_with_multiple_arguments(mock_aopen):
    # Simulate an open file with a BytesIO.
    f = BytesIO(b'dummyfile2\n')
    f.name = 'test.jpg'

    assert await build_multipart_body(
        values=OrderedDict({
            'file': Path('test.txt'),
            'file2': f,
            'notfile': 'abc',
            'integer': 3,
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!8423',
    ) == b'--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="file2"; filename="test.jpg"; Content-Type: image/jpeg\r\n\r\ndummyfile2\n\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="notfile"\r\n\r\nabc\r\n--8banana133744910kmmr13a56!102!8423\r\nContent-Disposition: form-data; name="integer"\r\n\r\n3\r\n--8banana133744910kmmr13a56!102!8423--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_custom_metadata(mock_aopen):
    # Simulate an open file with a BytesIO.
    f = BytesIO(b'dummyfile but it is a jpeg\n')
    f.name = 'test.jpg'

    assert await build_multipart_body(
        values=OrderedDict({
            'file': MultipartData(
                f,
                mime_type='text/plain',
                basename='test.txt'
            ),
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!5649',
    ) == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test.txt"; Content-Type: text/plain\r\n\r\ndummyfile but it is a jpeg\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_real_test_file():
    assert await build_multipart_body(
        values=OrderedDict({
            'file': TEST_DIR / 'test_multipart.txt',
        }),
        encoding='utf8',
        boundary_data='8banana133744910kmmr13a56!102!5649',
    ) == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test_multipart.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'


@pytest.mark.curio
async def test_multipart_body_with_real_pre_opened_test_file():
    async with await aopen(TEST_DIR / 'test_multipart.txt', 'rb') as f:
        print(type(f))

        assert await build_multipart_body(
            values=OrderedDict({
                'file': f,
            }),
            encoding='utf8',
            boundary_data='8banana133744910kmmr13a56!102!5649',
        ) == b'--8banana133744910kmmr13a56!102!5649\r\nContent-Disposition: form-data; name="file"; filename="test_multipart.txt"; Content-Type: text/plain\r\n\r\ndummyfile\n\r\n--8banana133744910kmmr13a56!102!5649--\r\n'
