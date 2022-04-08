"""
Simple exceptions to be raised in case of errors.
"""

from typing import Any


class AsksException(Exception):
    """
    Base exception for all asks errors.
    """

    pass


class TooManyRedirects(AsksException):
    pass


class ConnectivityError(AsksException):
    """
    Base exception for network failure errors.
    """

    pass


class BadHttpResponse(AsksException):
    pass


class BadStatus(AsksException):
    def __init__(
        self,
        err: Any,
        response: "response_objects.BaseResponse",
        status_code: int = 500,
    ) -> None:
        super().__init__(err)
        self.response = response
        self.status_code = status_code

    pass


class RequestTimeout(ConnectivityError):
    pass


class ServerClosedConnectionError(ConnectivityError):
    pass


from . import response_objects  # noqa
