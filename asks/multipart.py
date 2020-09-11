import mimetypes

from typing import BinaryIO, NamedTuple, Union, Optional
from pathlib import Path

from anyio import open_file, AsyncFile


_RAW_BYTES_MIMETYPE = "application/octet-stream"


class MultipartData(NamedTuple):
    """
    Describes data to be sent in a multipart/form-data.

    This should be used for manually specifying the mimetype or the basename of
    a field to be sent, and/or to send raw bytes as files.
    """

    binary_source: Union[Path, bytes, BinaryIO, AsyncFile]
    mime_type: Optional[str] = _RAW_BYTES_MIMETYPE
    basename: Optional[str] = None

    async def to_bytes(self):
        binary_source = self.binary_source

        if isinstance(binary_source, Path):
            async with await open_file(binary_source, "rb") as f:
                return await f.read()

        if isinstance(binary_source, bytes):
            return binary_source

        # else we should have a BinaryIO or an async equivalent,
        # which we can't really type-check at runtime
        result = binary_source.read()

        if isinstance(result, bytes):
            return result

        # We must then assume it is a coroutine.
        return await result


def _to_multipart_file(value):
    """
    Ensure a file-like supported type is encapsulated in a MultipartData object.

    Args:
        value: One of the supported file-like types.
        encoding: The desired encoding to send a field as.

    Returns:
        MultipartData: An object describing a multipart/form-data file field.
    """

    basename = Path(value.name).name if hasattr(value, "name") else None
    mime_type = (
        mimetypes.guess_type(basename)[0]
        if basename is not None
        else _RAW_BYTES_MIMETYPE
    )

    return MultipartData(binary_source=value, mime_type=mime_type, basename=basename,)


def _to_multipart_form_data(value, encoding):
    """
    Transform a form-data entry into a MultipartData object.

    If `value` is one of the supported file-like types, it will be seen as a
    file.  Else it will be converted into a string and sent as raw form data.

    Args:
        value: A form value to encode or a file-like supported object.
        encoding: The desired encoding to send a field as.

    Returns:
        MultipartData: An object describing a multipart/form-data field.
    """
    if isinstance(value, MultipartData):
        return value

    if isinstance(value, (Path, bytes)) or hasattr(value, "read"):
        return _to_multipart_file(value)

    # It's not a supported file type, so we do our best to transform it into form data.
    return MultipartData(
        binary_source=str(value).encode(encoding), mime_type=None, basename=None,
    )


async def build_multipart_body(values, encoding, boundary_data):
    """
    Forms a multipart request body from  a dict of form fields to values.

    Args:
        values: A dict of strings (field names) to:
                    - Path
                    - IO[bytes]
                    - An async file-like object (read() is async), opened in binary mode.
                    - bytes
                    - MultipartData
                    - Any other value that can be sent by being converted to str.
                The first four will be sent as files. MultipartData will be sent
                as a file if it has the necessary info to do so. The rest will be
                sent as ordinary data.

    Returns:
        multipart_body (bytes): The strings representation of the content body,
                                multipart formatted.
    """
    boundary = b"".join((b"--", bytes(boundary_data, encoding)))

    multipart_body = b""

    for k, v in values.items():
        multipart_data = _to_multipart_form_data(v, encoding)

        multipart_body += b"".join(
            (
                boundary,
                b"\r\n",
                'Content-Disposition: form-data; name="{}"'.format(k).encode(encoding),
                (
                    b""
                    if multipart_data.basename is None
                    else '; filename="{}"'.format(multipart_data.basename).encode(
                        encoding
                    )
                ),
                (
                    b""
                    if multipart_data.mime_type is None
                    else "\r\nContent-Type: {}".format(multipart_data.mime_type).encode(
                        encoding
                    )
                ),
                b"\r\n\r\n",
                await multipart_data.to_bytes(),
                b"\r\n",
            )
        )

    multipart_body += boundary + b"--\r\n"

    return multipart_body
