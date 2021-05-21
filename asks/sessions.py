"""
The disparate session (Session) is for making requests to multiple locations.
"""

from abc import ABCMeta, abstractmethod
from copy import copy
from functools import partialmethod
from urllib.parse import urlparse, urlunparse, urljoin

from h11 import RemoteProtocolError
from anyio import connect_tcp, Semaphore

from .cookie_utils import CookieTracker
from .errors import BadHttpResponse
from .req_structs import SocketQ
from .request_object import RequestProcessor
from .utils import get_netloc_port, timeout_manager


__all__ = ["Session"]


class BaseSession(metaclass=ABCMeta):
    """
    The base class for asks' sessions.
    Contains methods for creating sockets, figuring out which type of
    socket to create, and all of the HTTP methods ('GET', 'POST', etc.)
    """

    def __init__(self, headers=None, ssl_context=None):
        """
        Args:
            headers (dict): Headers to be applied to all requests.
                headers set by http method call will take precedence and
                overwrite headers set by the headers arg.
            ssl_context (ssl.SSLContext): SSL context to use for https connections.
        """
        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}

        self.ssl_context = ssl_context
        self.encoding = None
        self.source_address = None
        self._cookie_tracker = None

    @property
    @abstractmethod
    def sema(self):
        """
        A semaphore-like context manager.
        """
        ...

    async def _open_connection_http(self, location):
        """
        Creates a normal async socket, returns it.
        Args:
            location (tuple(str, int)): A tuple of net location (eg
                '127.0.0.1' or 'example.org') and port (eg 80 or 25000).
        """
        sock = await connect_tcp(
            location[0], location[1], local_host=self.source_address
        )
        sock._active = True
        return sock

    async def _open_connection_https(self, location):
        """
        Creates an async SSL socket, returns it.
        Args:
            location (tuple(str, int)): A tuple of net location (eg
                '127.0.0.1' or 'example.org') and port (eg 80 or 25000).
        """
        sock = await connect_tcp(
            location[0],
            location[1],
            ssl_context=self.ssl_context,
            local_host=self.source_address,
            tls=True,
            tls_standard_compatible=False,
        )
        sock._active = True
        return sock

    async def _connect(self, host_loc):
        """
        Simple enough stuff to figure out where we should connect, and creates
        the appropriate connection.
        """
        parsed_hostloc = urlparse(host_loc)
        scheme, host, path, parameters, query, fragment = parsed_hostloc
        if parameters or query or fragment:
            raise TypeError(
                "Supplied info beyond scheme, host."
                + " Host should be top level only: ",
                path,
            )

        host, port = get_netloc_port(parsed_hostloc)
        if scheme == "http":
            return await self._open_connection_http((host, int(port))), port
        else:
            return await self._open_connection_https((host, int(port))), port

    async def request(
        self, method, url=None, *, path="", retries=1, connection_timeout=60, **kwargs
    ):
        """
        This is the template for all of the `http method` methods for
        the Session.

        Args:
            method (str): A http method, such as 'GET' or 'POST'.
            url (str): The url the request should be made to.
            path (str): An optional kw-arg for use in Session method calls,
                for specifying a particular path. Usually to be used in
                conjunction with the base_location/endpoint paradigm.
            kwargs: Any number of the following:
                        data (dict or str): Info to be processed as a
                            body-bound query.
                        params (dict or str): Info to be processed as a
                            url-bound query.
                        headers (dict): User HTTP headers to be used in the
                            request.
                        encoding (str): The str representation of the codec to
                            process the request under.
                        json (dict): A dict to be formatted as json and sent in
                            the request body.
                        files (dict): A dict of `filename:filepath`s to be sent
                            as multipart.
                        multipart (dict): Data (files or form data) to be sent as a
                            multipart form.
                        cookies (dict): A dict of `name:value` cookies to be
                            passed in request.
                        callback (func): A callback function to be called on
                            each bytechunk of of the response body.
                        timeout (int or float): A numeric representation of the
                            longest time to wait on a complete response once a
                            request has been sent.
                        retries (int): The number of attempts to try against
                            connection errors.
                        max_redirects (int): The maximum number of redirects
                            allowed.
                        follow_redirects (bool): Whether to follow redirects
                            or return raw 3xx responses.
                        persist_cookies (True or None): Passing True
                            instantiates a CookieTracker object to manage the
                            return of cookies to the server under the relevant
                            domains.
                        auth (child of AuthBase): An object for handling auth
                            construction.
                        stream (bool): Whether or not to return a StreamResponse
                            vs Response

        When you call something like Session.get() or asks.post(), you're
        really calling a partial method that has the 'method' argument
        pre-completed.
        """

        ALLOWED_KWARGS = {
            "data",
            "params",
            "headers",
            "encoding",
            "json",
            "files",
            "multipart",
            "cookies",
            "callback",
            "timeout",
            "retries",
            "max_redirects",
            "follow_redirects",
            "persist_cookies",
            "auth",
            "stream",
        }

        unknown_kwargs = set(kwargs) - ALLOWED_KWARGS
        if unknown_kwargs:
            raise TypeError(
                "request() got unexpected keyword arguments {!r}".format(
                    ", ".join(str(x) for x in unknown_kwargs)
                )
            ) from None

        timeout = kwargs.get("timeout", None)
        req_headers = kwargs.pop("headers", None)

        if self.headers is not None:
            headers = copy(self.headers)
        if req_headers is not None:
            headers.update(req_headers)
        req_headers = headers

        async with self.sema:
            if url is None:
                url = self._make_url(path)

            retry = False

            sock = None
            try:
                sock = await timeout_manager(
                    connection_timeout, self._grab_connection, url
                )
                port = sock.port

                req_obj = RequestProcessor(
                    self,
                    method,
                    url,
                    port,
                    headers=req_headers,
                    encoding=self.encoding,
                    sock=sock,
                    persist_cookies=self._cookie_tracker,
                    **kwargs
                )

                try:
                    if timeout is None:
                        sock, r = await req_obj.make_request()
                    else:
                        sock, r = await timeout_manager(timeout, req_obj.make_request)
                except BadHttpResponse:
                    if timeout is None:
                        sock, r = await req_obj.make_request()
                    else:
                        sock, r = await timeout_manager(timeout, req_obj.make_request)

                if sock is not None:
                    try:
                        if r.headers["connection"].lower() == "close":
                            sock._active = False
                            await sock.aclose()
                    except KeyError:
                        pass
                    await self.return_to_pool(sock)

            # ConnectionErrors are special. They are the only kind of exception
            # we ever want to suppress. All other exceptions are re-raised or
            # raised through another exception.
            except ConnectionError as e:
                if retries > 0:
                    retry = True
                    retries -= 1
                else:
                    raise e

            except Exception as e:
                if sock:
                    await self._handle_exception(e, sock)
                raise

            # any BaseException is considered unlawful murder, and
            # Session.cleanup should be called to tidy up sockets.
            except BaseException as e:
                if sock:
                    await sock.aclose()
                raise e

        if retry:
            return await self.request(
                method, url, path=path, retries=retries, headers=headers, **kwargs
            )

        return r

    # These be the actual http methods!
    # They are partial methods of `request`. See the `request` docstring
    # above for information.
    get = partialmethod(request, "GET")
    head = partialmethod(request, "HEAD")
    post = partialmethod(request, "POST")
    put = partialmethod(request, "PUT")
    delete = partialmethod(request, "DELETE")
    options = partialmethod(request, "OPTIONS")
    patch = partialmethod(request, "PATCH")

    async def _handle_exception(self, e, sock):
        """
        Given an exception, we want to handle it appropriately. Some exceptions we
        prefer to shadow with an asks exception, and some we want to raise directly.
        In all cases we clean up the underlying socket.
        """
        if isinstance(e, (RemoteProtocolError, AssertionError)):
            await sock.aclose()
            raise BadHttpResponse("Invalid HTTP response from server.") from e

        if isinstance(e, Exception):
            await sock.aclose()
            raise e

    @abstractmethod
    def _make_url(self):
        """
        A method who's result is concated with a uri path.
        """
        ...

    @abstractmethod
    async def _grab_connection(self, url):
        """
        A method that will return a socket-like object.
        """
        ...

    @abstractmethod
    async def return_to_pool(self, sock):
        """
        A method that will accept a socket-like object.
        """
        ...


class Session(BaseSession):
    """
    The Session class, for handling piles of requests.

    This class inherits from BaseSession, where all of the 'http method'
    methods are defined.
    """

    def __init__(
        self,
        base_location="",
        endpoint="",
        headers=None,
        encoding="utf-8",
        persist_cookies=None,
        ssl_context=None,
        connections=1,
    ):
        """
        Args:
            encoding (str): The encoding asks'll try to use on response bodies.
            persist_cookies (bool): Passing True turns on browserishlike
                stateful cookie behaviour, returning cookies to the host when
                appropriate.
            connections (int): The max number of concurrent connections to the
                host asks will allow its self to have. The default number of
                connections is 1. You may increase this value as you see fit.
        """
        super().__init__(headers, ssl_context)
        self.encoding = encoding
        self.base_location = base_location
        self.endpoint = endpoint

        if persist_cookies is True:
            self._cookie_tracker = CookieTracker()
        else:
            self._cookie_tracker = persist_cookies

        self._conn_pool = SocketQ()

        self._sema = None
        self._connections = connections

    @property
    def base_location(self):
        return self._base_location

    @base_location.setter
    def base_location(self, value):
        if not value:
            self._base_location = value
        else:
            self._base_location = self._normalise_last_slashes(value)

    @property
    def endpoint(self):
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value):
        if not value:
            self._endpoint = value
        else:
            value = self._normalise_head_slashes(value)
            self._endpoint = self._normalise_last_slashes(value)

    @property
    def sema(self):
        if self._sema is None:
            self._sema = Semaphore(self._connections)
        return self._sema

    def _checkout_connection(self, host_loc):
        try:
            index = self._conn_pool.index(host_loc)
        except ValueError:
            return None

        sock = self._conn_pool.pull(index)
        return sock

    async def return_to_pool(self, sock):
        if sock._active:
            self._conn_pool.appendleft(sock)

    async def _make_connection(self, host_loc):
        sock, port = await self._connect(host_loc)
        sock.host, sock.port = host_loc, port

        return sock

    async def _grab_connection(self, url):
        """
        The connection pool handler. Returns a connection
        to the caller. If there are no connections ready, and
        as many connections checked out as there are available total,
        we yield control to the event loop.

        If there is a connection ready or space to create a new one, we
        pop/create it, register it as checked out, and return it.

        Args:
            url (str): breaks the url down and uses the top level location
                info to see if we have any connections to the location already
                lying around.
        """
        scheme, host, _, _, _, _ = urlparse(url)
        host_loc = urlunparse((scheme, host, "", "", "", ""))

        sock = self._checkout_connection(host_loc)

        if sock is None:
            sock = await self._make_connection(host_loc)

        return sock

    def _make_url(self, path):
        """
        Puts together the hostloc and current endpoint for use in request uri.
        """
        if not self.base_location:
            raise ValueError("No base_location set. Cannot construct url.")

        if path:
            path = self._normalise_last_slashes(path)
            path = self._normalise_head_slashes(path)

        return "".join((self.base_location, self.endpoint, path))

    @staticmethod
    def _normalise_last_slashes(url_segment):
        """
        Drop any last /'s
        """
        return url_segment if not url_segment.endswith("/") else url_segment[:-1]

    @staticmethod
    def _normalise_head_slashes(url_segment):
        """
        Add any missing head /'s
        """
        return url_segment if url_segment.startswith("/") else "/" + url_segment

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        await self._conn_pool.free_pool()
