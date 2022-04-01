"""
This module takes care of the construction of requests, and the io
for sending them, as well as receiving responses.

This is the oldest part of asks, and as such is currently not the cleanest
it could be. Refactors are required to bring it up to spec!
"""
__all__ = ["RequestProcessor"]


from numbers import Number
from os.path import basename
from urllib.parse import urljoin, urlparse, urlunparse, quote_plus
import json as _json
from random import randint
import mimetypes
import re

from anyio import open_file, EndOfStream
import h11

from .utils import requote_uri
from .cookie_utils import parse_cookies
from .auth import PreResponseAuth, PostResponseAuth
from .req_structs import CaseInsensitiveDict as c_i_dict
from .response_objects import Response, StreamResponse, StreamBody
from .errors import TooManyRedirects
from .multipart import build_multipart_body


_BOUNDARY = "8banana133744910kmmr13a56!102!" + str(randint(10 ** 3, 10 ** 9))
_WWX_MATCH = re.compile(r"\Aww.\.")


class RequestProcessor:
    """
    Handles the building, formatting and i/o of requests once the calling
    session passes the required info and calls `make_request`.

    Args:
        session (child of BaseSession): A reference to the calling session.

        method (str): The HTTP method to be used in the request.

        uri (str): The full uri path to be requested. May not include query.

        port (str): The port we want to use on the net location.

        auth (child of AuthBase): An object for handling auth construction.

        data (dict or str): Info to be processed as a body-bound query.

        params (dict or str): Info to be processed as a url-bound query.

        headers (dict): User HTTP headers to be used in the request.

        encoding (str): The str representation of the codec to process the
            request under.

        json (dict): A dict to be formatted as json and sent in request body.

        files (dict): A dict of `filename:filepath`s to be sent as multipart.

        multipart (dict): Info to be sent as multipart/form-data.

        cookies (dict): A dict of `name:value` cookies to be passed in request.

        callback (func): A callback function to be called on each bytechunk of
            of the response body.

        stream (bool): Whether or not to return a StreamResponse vs Response

        timeout (int or float): A numeric representation of the longest time to
            wait on a complete response once a request has been sent.

        max_redirects (int): The maximum number of redirects allowed.

        follow_redirects (bool): Whether to follow redirects or return raw 3xx
            responses.

        persist_cookies (True or None): Passing True instantiates a
            CookieTracker object to manage the return of cookies to the server
            under the relevant domains.

        sock (StreamSock): The socket object to be used for the request. This
            socket object may be updated on `connection: close` headers.
    """

    def __init__(self, session, method, uri, port, **kwargs):
        # These are kwargsable attribs.
        self.session = session
        self.method = method.upper()
        self.uri = uri
        self.port = port
        self.auth = None
        self.auth_off_domain = None
        self.body = None
        self.data = None
        self.params = None
        self.headers = None
        self.encoding = None
        self.json = None
        self.files = None
        self.multipart = None
        self.cookies = {}
        self.callback = None
        self.stream = None
        self.timeout = None
        self.max_redirects = 20
        self.follow_redirects = True
        self.sock = None
        self.persist_cookies = None
        self.mimetype = None

        # IS THIS SUCH A SIN? Maybe. Hacky at best but hey.
        # All of the above instance vars are valid args/kwargs.
        self.__dict__.update(kwargs)

        # These are unkwargsable, and set by the code.
        self.history_objects = []
        self.scheme = None
        self.host = None
        self.path = None
        self.query = None
        self.uri_parameters = None
        self.target_netloc = None
        self.req_url = None

        self.initial_scheme = None
        self.initial_netloc = None

        self.streaming = False

    async def make_request(self, redirect=False):
        """
        Acts as the central hub for preparing requests to be sent, and
        returning them upon completion. Generally just pokes through
        self's attribs and makes decisions about what to do.

        Returns:
            sock: The socket to be returned to the calling session's
                pool.
            Response: The response object, after any redirects. If there were
                redirects, the redirect responses will be stored in the final
                response object's `.history`.
        """
        h11_connection = h11.Connection(our_role=h11.CLIENT)
        (
            self.scheme,
            self.host,
            self.path,
            self.uri_parameters,
            self.query,
            _,
        ) = urlparse(self.uri)

        if not redirect:
            self.initial_scheme = self.scheme
            self.initial_netloc = self.host

        # leave default the host on 80 / 443
        # otherwise use the base host with :port appended.
        host = (
            self.host
            if (self.port == "80" or self.port == "443")
            else self.host.split(":")[0] + ":" + self.port
        )

        # default header construction
        asks_headers = c_i_dict(
            [
                ("Host", host),
                ("Connection", "close"),
                ("Accept-Encoding", "gzip, deflate"),
                ("Accept", "*/*"),
                ("Content-Length", "0"),
                ("User-Agent", "python-asks/3.0.0"),
            ]
        )

        # check for a CookieTracker object, and if it's there inject
        # the relevant cookies in to the (next) request.
        # What the fuck is this shit.
        if self.persist_cookies is not None:
            self.cookies.update(
                self.persist_cookies.get_additional_cookies(self.host, self.path)
            )

        # formulate path / query and intended extra querys for use in uri
        self._build_path()

        # handle building the request body, if any
        body = ""
        if any((self.data, self.files, self.json is not None, self.multipart is not None)):
            content_type, content_len, body = await self._formulate_body()
            asks_headers["Content-Type"] = content_type
            asks_headers["Content-Length"] = content_len
            self.body = body

        # add custom headers, if any
        # note that custom headers take precedence
        if self.headers is not None:
            asks_headers.update(self.headers)

        # add auth
        if self.auth is not None:
            asks_headers.update(await self._auth_handler_pre())
            asks_headers.update(await self._auth_handler_post_get_auth())

        # add cookies
        if self.cookies:
            cookie_str = ""
            for k, v in self.cookies.items():
                cookie_str += "{}={}; ".format(k, v)
            asks_headers["Cookie"] = cookie_str[:-1]

        # Construct h11 body object, if any body.
        if body:
            if not isinstance(body, bytes):
                body = bytes(body, self.encoding)
                asks_headers["Content-Length"] = str(len(body))
            req_body = h11.Data(data=body)
        else:
            req_body = None

        # Construct h11 request object.
        req = h11.Request(
            method=self.method, target=self.path, headers=asks_headers.items()
        )

        # call i/o handling func
        response_obj = await self._request_io(req, req_body, h11_connection)

        # check to see if the final socket object is suitable to be returned
        # to the calling session's connection pool.
        # We don't want to return sockets that are of a difference schema or
        # different top level domain, as they are less likely to be useful.
        if redirect:
            if not (
                self.scheme == self.initial_scheme and self.host == self.initial_netloc
            ):
                self.sock._active = False
                await self.sock.aclose()

        if self.streaming:
            return None, response_obj

        if asks_headers.get('connection', '') == 'close' and self.sock._active:
            await self.sock.aclose()
            return None, response_obj

        return self.sock, response_obj

    async def _request_io(self, h11_request, h11_body, h11_connection):
        """
        Takes care of the i/o side of the request once it's been built,
        and calls a couple of cleanup functions to check for redirects / store
        cookies and the likes.

        Args:
            h11_request (h11.Request): A h11.Request object
            h11_body (h11.Data): A h11.Data object, representing the request
                                 body.
            h11_connection (h11.Connection): The h11 connection for the request.

        Returns:
            (Response): The final response object, including any response
                        objects in `.history` generated by redirects.

        Notes:
            This function sets off a possible call to `_redirect` which
            is semi-recursive.
        """
        await self._send(h11_request, h11_body, h11_connection)
        response_obj = await self._catch_response(h11_connection)
        parse_cookies(response_obj, self.host)

        # If there's a cookie tracker object, store any cookies we
        # might've picked up along our travels.
        if self.persist_cookies is not None:
            self.persist_cookies._store_cookies(response_obj)

        # Have a crack at guessing the encoding of the response.
        response_obj._guess_encoding()

        # Check to see if there's a PostResponseAuth set, and does magic.
        if self.auth is not None:
            response_obj = await self._auth_handler_post_check_retry(response_obj)

        # check redirects
        if self.method != "HEAD":
            if self.max_redirects < 0:
                raise TooManyRedirects
            if self.follow_redirects:
                response_obj = await self._redirect(response_obj)
        response_obj.history = self.history_objects

        return response_obj

    def _build_path(self):
        """
        Constructs the actual request URL with accompanying query if any.

        Returns:
            None: But does modify self.path, which contains the final
                request path sent to the server.

        """
        if not self.path:
            self.path = "/"

        if self.uri_parameters:
            self.path = self.path + ";" + requote_uri(self.uri_parameters)

        if self.query:
            self.path = self.path + "?" + self.query

        if self.params:
            try:
                if self.query:
                    self.path = self.path + self._dict_to_query(
                        self.params, base_query=True
                    )
                else:
                    self.path = self.path + self._dict_to_query(self.params)
            except AttributeError:
                self.path = self.path + "?" + self.params

        self.path = requote_uri(self.path)

        self.req_url = urlunparse(
            (self.scheme, self.host, (self.path or ""), "", "", "")
        )

    async def _redirect(self, response_obj):
        """
        Calls the _check_redirect method of the supplied response object
        in order to determine if the http status code indicates a redirect.

        Returns:
            Response: May or may not be the result of recursive calls due
            to redirects!

        Notes:
            If it does redirect, it calls the appropriate method with the
            redirect location, returning the response object. Furthermore,
            if there is a redirect, this function is recursive in a roundabout
            way, storing the previous response object in `.history_objects`.
        """
        redirect, force_get, location = False, None, None
        if 300 <= response_obj.status_code < 400:
            if response_obj.status_code == 303:
                self.data, self.json, self.files = None, None, None
            if response_obj.status_code in [301, 305]:
                # redirect / force GET / location
                redirect = True
                force_get = False
            else:
                redirect = True
                force_get = True
            location = response_obj.headers["Location"]

        if redirect:
            allow_redirect = True
            location = urljoin(self.uri, location.strip())
            if self.auth is not None:
                if not self.auth_off_domain:
                    allow_redirect = await self._location_auth_protect(location)
            self.uri = location
            l_scheme, l_netloc, *_ = urlparse(location)
            if l_scheme != self.scheme or l_netloc != self.host:
                await self._get_new_sock()

            # follow redirect with correct http method type
            if force_get:
                self.history_objects.append(response_obj)
                self.method = "GET"
            else:
                self.history_objects.append(response_obj)
            self.max_redirects -= 1

            try:
                if response_obj.headers["connection"].lower() == "close":
                    await self._get_new_sock()
            except KeyError:
                pass
            if allow_redirect:
                _, response_obj = await self.make_request()
        return response_obj

    async def _get_new_sock(self):
        """
        On 'Connection: close' headers we've to create a new connection.
        This reaches in to the parent session and pulls a switcheroo, dunking
        the current connection and requesting a new one.
        """
        self.sock._active = False
        self.sock = await self.session._grab_connection(self.uri)
        self.port = self.sock.port

    async def _formulate_body(self):
        """
        Takes user supplied data / files and forms it / them
        appropriately, returning the contents type, len,
        and the request body its self.

        Returns:
            The str mime type for the Content-Type header.
            The len of the body.
            The body as a str.
        """
        c_type, body = None, ""
        multipart_ctype = "multipart/form-data; boundary={}".format(_BOUNDARY)

        if self.data is not None:
            if self.files or self.json or self.multipart is not None:
                raise TypeError(
                    "data arg cannot be used in conjunction with"
                    "files, json or multipart arg."
                )
            c_type = "application/x-www-form-urlencoded"
            try:
                body = self._dict_to_query(self.data, params=False)
            except AttributeError:
                body = self.data
                c_type = self.mimetype or "text/plain"

        elif self.files is not None:
            if self.data or self.json or self.multipart is not None:
                raise TypeError(
                    "files arg cannot be used in conjunction with"
                    "data, json or multipart arg."
                )
            c_type = multipart_ctype
            body = await self._multipart(self.files)

        elif self.json is not None:
            if self.data or self.files or self.multipart is not None:
                raise TypeError(
                    "json arg cannot be used in conjunction with"
                    "data, files or multipart arg."
                )
            c_type = "application/json"
            body = _json.dumps(self.json)

        elif self.multipart is not None:
            if self.data or self.json or self.files is not None:
                raise TypeError(
                    "multipart arg cannot be used in conjunction with"
                    "data, json or files arg."
                )
            c_type = multipart_ctype
            body = await build_multipart_body(self.multipart, self.encoding, _BOUNDARY)

        return c_type, str(len(body)), body

    @staticmethod
    def _dict_to_query(data, params=True, base_query=False):
        """
        Turns python dicts in to valid body-queries or queries for use directly
        in the request url. Unlike the stdlib quote() and it's variations,
        this also works on iterables like lists which are normally not valid.

        The use of lists in this manner is not a great idea unless
        the server supports it. Caveat emptor.

        Returns:
            Query part of url (or body).
        """
        query = []

        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, (str, Number)):
                query.append("=".join(quote_plus(x) for x in (k, str(v))))
            elif isinstance(v, dict):
                for key in v:
                    query.append("=".join(quote_plus(x) for x in (k, key)))
            elif hasattr(v, "__iter__"):
                for elm in v:
                    query.append(
                        "=".join(
                            quote_plus(x)
                            for x in (k, quote_plus("+".join(str(elm).split())))
                        )
                    )

        if params and query:
            if not base_query:
                return requote_uri("?" + "&".join(query))
            else:
                return requote_uri("&" + "&".join(query))

        return requote_uri("&".join(query))

    async def _multipart(self, files_dict):
        """
        Forms multipart requests from a dict with name, path k/vs. Name
        does not have to be the actual file name.

        Args:
            files_dict (dict): A dict of `filename:filepath`s, to be sent
            as multipart files.

        Returns:
            multip_pkg (str): The strings representation of the content body,
            multipart formatted.
        """
        boundary = bytes(_BOUNDARY, self.encoding)
        hder_format = 'Content-Disposition: form-data; name="{}"'
        hder_format_io = '; filename="{}"'

        multip_pkg = b""

        num_of_parts = len(files_dict)

        for index, kv in enumerate(files_dict.items(), start=1):
            multip_pkg += b"--" + boundary + b"\r\n"
            k, v = kv

            try:
                pkg_body = await self._file_manager(v)
                multip_pkg += bytes(
                    hder_format.format(k) + hder_format_io.format(basename(v)),
                    self.encoding,
                )
                mime_type = mimetypes.guess_type(basename(v))
                if not mime_type[1]:
                    mime_type = "application/octet-stream"
                else:
                    mime_type = "/".join(mime_type)
                multip_pkg += bytes("\r\nContent-Type: " + mime_type, self.encoding)
                multip_pkg += b"\r\n" * 2 + pkg_body

            except (TypeError, FileNotFoundError):
                pkg_body = bytes(v, self.encoding) + b"\r\n"
                multip_pkg += bytes(hder_format.format(k) + "\r\n" * 2, self.encoding)
                multip_pkg += pkg_body

            if index == num_of_parts:
                multip_pkg += b"--" + boundary + b"--\r\n"

        return multip_pkg

    async def _file_manager(self, path):
        async with await open_file(path, "rb") as f:
            return b"".join(await f.readlines()) + b"\r\n"

    async def _catch_response(self, h11_connection):
        """
        Instantiates the parser which manages incoming data, first getting
        the headers, storing cookies, and then parsing the response's body,
        if any.

        This function also instances the Response class in which the response
        status line, headers, cookies, and body is stored.

        It should be noted that in order to remain preformant, if the user
        wishes to do any file IO it should use async files or risk long wait
        times and risk connection issues server-side when using callbacks.

        If a callback is used, the response's body will be None.

        Returns:
            The most recent response object.
        """

        response = await self._recv_event(h11_connection)

        resp_data = {
            "encoding": self.encoding,
            "method": self.method,
            "status_code": response.status_code,
            "reason_phrase": str(response.reason, "utf-8"),
            "http_version": str(response.http_version, "utf-8"),
            "headers": c_i_dict(
                [
                    (str(name, "utf-8"), str(value, "utf-8"))
                    for name, value in response.headers
                ]
            ),
            "body": bytearray(),
            "url": self.req_url,
        }

        for header in response.headers:
            if header[0].lower() == b"set-cookie":
                try:
                    resp_data["headers"]["set-cookie"].append(str(header[1], "utf-8"))
                except (KeyError, AttributeError):
                    resp_data["headers"]["set-cookie"] = [str(header[1], "utf-8")]

        # check whether we should receive body according to RFC 7230
        # https://tools.ietf.org/html/rfc7230#section-3.3.3
        get_body = False
        try:
            if int(resp_data["headers"]["content-length"]) > 0:
                get_body = True
        except KeyError:
            try:
                if "chunked" in resp_data["headers"]["transfer-encoding"].lower():
                    get_body = True
            except KeyError:
                connection_close = resp_data["headers"].get("connection", "").lower() == "close"
                http_1 = response.http_version == b"1.0"
                if connection_close or http_1:
                    get_body = True

        if get_body:
            if self.callback is not None:
                endof = await self._body_callback(h11_connection)

            elif self.stream:
                if not (
                    (
                        self.scheme == self.initial_scheme
                        and self.host == self.initial_netloc
                    )
                    or resp_data["headers"]["connection"].lower() == "close"
                ):
                    self.sock._active = False

                resp_data["body"] = StreamBody(
                    h11_connection,
                    self.sock,
                    resp_data["headers"].get("content-encoding", None),
                    resp_data["encoding"],
                )

                self.streaming = True

            else:
                while True:
                    data = await self._recv_event(h11_connection)

                    if isinstance(data, h11.Data):
                        resp_data["body"] += data.data

                    elif isinstance(data, h11.EndOfMessage):
                        break

        else:
            endof = await self._recv_event(h11_connection)
            assert isinstance(endof, h11.EndOfMessage)

        if self.streaming:
            return StreamResponse(**resp_data)

        return Response(**resp_data)

    async def _recv_event(self, h11_connection):
        while True:
            event = h11_connection.next_event()
            if event is h11.NEED_DATA:
                try:
                    data = await self.sock.receive()
                except EndOfStream:
                    data = b""
                h11_connection.receive_data(data)
                continue
            return event

    async def _send(self, request_bytes, body_bytes, h11_connection):
        """
        Takes a package and body, combines then, then shoots 'em off in to
        the ether.

        Args:
            package (list of str): The header package.
            body (str): The str representation of the body.
        """
        await self.sock.send(h11_connection.send(request_bytes))
        if body_bytes is not None:
            await self.sock.send(h11_connection.send(body_bytes))

        data = h11_connection.send(h11.EndOfMessage())
        if data:
            await self.sock.send(data)

    async def _auth_handler_pre(self):
        """
        If the user supplied auth does not rely on any response
        (is a PreResponseAuth object) then we call the auth's __call__
        returning a dict to update the request's headers with.
        """
        # pylint: disable=not-callable
        if isinstance(self.auth, PreResponseAuth):
            return await self.auth(self)
        return {}

    async def _auth_handler_post_get_auth(self):
        """
        If the user supplied auth does rely on a response
        (is a PostResponseAuth object) then we call the auth's __call__
        returning a dict to update the request's headers with, as long
        as there is an appropriate 401'd response object to calculate auth
        details from.
        """
        # pylint: disable=not-callable
        if isinstance(self.auth, PostResponseAuth):
            if self.history_objects:
                authable_resp = self.history_objects[-1]
                if authable_resp.status_code == 401:
                    if not self.auth.auth_attempted:
                        self.auth.auth_attempted = True
                        return await self.auth(authable_resp, self)
        return {}

    async def _auth_handler_post_check_retry(self, response_obj):
        """
        The other half of _auth_handler_post_check_retry (what a mouthful).
        If auth has not yet been attempted and the most recent response
        object is a 401, we store that response object and retry the request
        in exactly the same manner as before except with the correct auth.

        If it fails a second time, we simply return the failed response.
        """
        if isinstance(self.auth, PostResponseAuth):
            if response_obj.status_code == 401:
                if not self.auth.auth_attempted:
                    self.history_objects.append(response_obj)
                    _, r = await self.make_request()
                    self.auth.auth_attempted = False
                    return r
                else:
                    response_obj.history = self.history_objects
                    return response_obj
        return response_obj

    async def _location_auth_protect(self, location):
        """
        Checks to see if the new location is
            1. The same top level domain
            2. As or more secure than the current connection type

        Returns:
            True (bool): If the current top level domain is the same
                and the connection type is equally or more secure.
                False otherwise.
        """
        netloc_sans_port = self.host.split(":")[0]
        netloc_sans_port = netloc_sans_port.replace(
            (re.match(_WWX_MATCH, netloc_sans_port)[0]), ""
        )

        base_domain = ".".join(netloc_sans_port.split(".")[-2:])

        l_scheme, l_netloc, _, _, _, _ = urlparse(location)
        location_sans_port = l_netloc.split(":")[0]
        location_sans_port = location_sans_port.replace(
            (re.match(_WWX_MATCH, location_sans_port)[0]), ""
        )

        location_domain = ".".join(location_sans_port.split(".")[-2:])

        if base_domain == location_domain:
            if l_scheme < self.scheme:
                return False
            else:
                return True

    async def _body_callback(self, h11_connection):
        """
        A callback func to be supplied if the user wants to do something
        directly with the response body's stream.
        """
        # pylint: disable=not-callable
        while True:
            next_event = await self._recv_event(h11_connection)
            if isinstance(next_event, h11.Data):
                await self.callback(next_event.data)
            else:
                return next_event
