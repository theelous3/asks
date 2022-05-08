# pylint: disable=abstract-method
import base64
import re
from abc import ABCMeta, abstractmethod
from hashlib import md5
from random import choice
from string import ascii_lowercase, digits
from typing import Any

__all__ = ["AuthBase", "PreResponseAuth", "PostResponseAuth", "BasicAuth", "DigestAuth"]


class AuthBase(metaclass=ABCMeta):
    """
    Base class for all auth classes. All user exposed auth classes
    should implement their own __call__ method, returning a dictionary
    for use in headers.
    """

    @abstractmethod
    async def __call__(
        self,
        response_obj: "response_objects.Response",
        req_obj: "request_object.RequestProcessor",
    ) -> dict[str, str]:
        """Not Implemented"""


class PreResponseAuth(AuthBase):
    """
    Auth class for response independant auth.
    """

    pass


class PostResponseAuth(AuthBase):
    """
    Auth class for response dependant auth.
    """

    auth_attempted: bool

    def __init__(self) -> None:
        self.auth_attempted = False


class BasicAuth(PreResponseAuth):
    """
    Ye Olde Basic HTTP Auth.
    """

    def __init__(self, auth_info: Any, encoding: str = "utf-8"):
        self.auth_info = auth_info
        self.encoding = encoding

    async def __call__(
        self,
        response_obj: "response_objects.Response",
        req_obj: "request_object.RequestProcessor",
    ) -> dict[str, str]:
        usrname, psword = [bytes(x, self.encoding) for x in self.auth_info]
        encoded_auth = str(base64.b64encode(usrname + b":" + psword), self.encoding)
        return {"Authorization": "Basic {}".format(encoded_auth)}


class DigestAuth(PostResponseAuth):
    """
    Semi-incomplete HTTP Digest Auth. Works fine with auth / auth-int,
    but lacks domain space checking and such.

    It will work, but be slightly more resource intensive than it should.
    To be completed!

    Also, it's 2018. Stop using digest auth.
    """

    _HDR_VAL_PARSE = re.compile(r'\b(\w+)=(?:"([^\\"]+)"|(\S+))')

    domain_space: list[Any]

    def __init__(self, auth_info: Any, encoding: str = "utf-8") -> None:
        super().__init__()
        self.auth_info = auth_info
        self.encoding = encoding
        self.domain_space = []
        self.nonce = None
        self.nonce_count = 1

    async def __call__(
        self,
        response_obj: "response_objects.Response",
        req_obj: "request_object.RequestProcessor",
    ) -> dict[str, str]:

        usrname, psword = [bytes(x, self.encoding) for x in self.auth_info]
        try:
            auth_resp_value = response_obj.headers["www-authenticate"]
        except KeyError:
            return {}
        auth_dict = dict()
        value_list = re.findall(self._HDR_VAL_PARSE, auth_resp_value)
        for match in value_list:
            k, v = [x for x in match if x != ""]
            auth_dict[k.lower()] = bytes(v, self.encoding)
        cnonce = bytes(
            "".join(choice(ascii_lowercase + digits) for _ in range(16)), self.encoding
        )
        ha1 = None
        ha2 = None
        response = None
        qop = None

        try:
            if auth_dict["algorithm"].lower() == b"md5-sess":
                ha1 = bytes(
                    md5(
                        bytes(
                            md5(
                                b":".join((usrname, auth_dict["realm"], psword))
                                + b":"
                                + auth_dict["nonce"]
                                + b":"
                                + cnonce
                            ).hexdigest(),
                            self.encoding,
                        )
                    ).hexdigest(),
                    self.encoding,
                )
                if auth_dict["nonce"] == self.nonce:
                    self.nonce_count += 1
                else:
                    self.nonce_count = 1
        except KeyError:
            # if an algorithm wasn't specified, we move on
            pass

        if ha1 is None:
            ha1 = bytes(
                md5(b":".join((usrname, auth_dict["realm"], psword))).hexdigest(),
                self.encoding,
            )

        bytes_path = bytes(req_obj.path or "", self.encoding)
        bytes_method = bytes(req_obj.method, self.encoding)
        try:
            if b"auth-int" in auth_dict["qop"].lower():

                if isinstance(response_obj.raw, str):
                    raise ValueError("response_obj.raw is str when it shouldn't")

                hashed_body = bytes(
                    md5(response_obj.raw or b"").hexdigest(), self.encoding
                )
                ha2 = bytes(
                    md5(b":".join((bytes_method, bytes_path, hashed_body))).hexdigest(),
                    self.encoding,
                )
                qop = "auth-int"
            else:
                qop = "auth"
        except KeyError:
            pass

        if ha2 is None:
            ha2 = bytes(
                md5(bytes_method + b":" + bytes_path).hexdigest(), self.encoding
            )

        try:
            if auth_dict["qop"]:
                bytes_nc = bytes("{:08x}".format(self.nonce_count), self.encoding)
                response = md5(
                    b":".join(
                        (
                            ha1,
                            auth_dict["nonce"],
                            bytes_nc,
                            cnonce,
                            bytes(qop or "", self.encoding),
                            ha2,
                        )
                    )
                ).hexdigest()
                if auth_dict["nonce"] == self.nonce:
                    self.nonce_count += 1
                else:
                    self.nonce_count = 1
        except KeyError:
            response = md5(b":".join((ha1, auth_dict["nonce"], ha2))).hexdigest()

        response_items = [
            'username="{}"'.format(str(usrname, self.encoding)),
            'realm="{}"'.format(str(auth_dict["realm"], self.encoding)),
            'nonce="{}"'.format(str(auth_dict["nonce"], self.encoding)),
            'uri="{}"'.format(req_obj.path),
            'response="{}"'.format(response),
            'opaque="{}"'.format(str(auth_dict["opaque"], self.encoding)),
        ]
        if qop is not None:
            response_items.append("qop={}".format(qop))

        response_items.extend(
            [
                "nc={:08x}".format(self.nonce_count),
                'cnonce="{}"'.format(str(cnonce, self.encoding)),
            ]
        )
        return {"Authorization": "Digest {}".format(", ".join(response_items))}


from . import request_object  # noqa
from . import response_objects  # noqa
