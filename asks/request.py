# pylint: disable=wildcard-import
# pylint: disable=no-else-return
# pylint: disable=not-callable
from numbers import Number
from os.path import basename
from urllib.parse import urlparse, urlunparse, quote
import json as _json
from random import randint
import mimetypes

from curio.file import aopen

from .auth import PreResponseAuth, PostResponseAuth
from .req_structs import CaseInsensitiveDict as c_i_Dict
from .response_objects import Response
from .http_req_parser import HttpParser
from .errors import TooManyRedirects


_BOUNDARY = "8banana133744910kmmr13ay5fa56" + str(randint(1e3, 9e3))


class Request:

    def __init__(self, method, uri, port, **kwargs):
        # These are kwargsable attribs.
        self.method = method
        self.uri = uri
        self.port = port
        self.auth = None
        self.data = None
        self.params = None
        self.headers = None
        self.encoding = None
        self.json = None
        self.files = None
        self.cookies = {}
        self.callback = None
        self.timeout = None
        self.max_redirects = float('inf')
        self.history_objects = []
        self.sock = None
        self.persist_cookies = None

        self.__dict__.update(kwargs)

        # These are unkwargsable, and set by the code.
        self.scheme = None
        self.netloc = None
        self.path = None
        self.query = None
        self.target_netloc = None

    async def make_request(self):
        '''
        Acts as the central hub for preparing requests to be sent, and
        returning them upon completion. Generally just pokes through
        self's attribs and makes decisions about what to do.
        '''
        self.scheme, self.netloc, self.path, _, self.query, _ = urlparse(
            self.uri)

        host = (self.netloc if (self.port == '80' or
                                self.port == '443')
                else self.netloc + ':' + self.port)

        # default header construction
        asks_headers = c_i_Dict([('Host', host),
                                 ('Connection', 'keep-alive'),
                                 ('Accept-Encoding', 'gzip, deflate'),
                                 ('Accept', '*/*'),
                                 ('Content-Length', '0'),
                                 ('User-Agent', 'python-asks/0.0.1')
                                 ])

        # check for a CookieTracker object, and if it's there inject
        # the relevant cookies in to the (next) request.
        if self.persist_cookies is not None:
            self.cookies.update(
                self.persist_cookies.get_additional_cookies(
                    self.netloc, self.path))

        # formulate path / query and intended extra querys for use in uri
        self.path = self._build_path()

        package = [' '.join((self.method, self.path, 'HTTP/1.1'))]

        # handle building the request body, if any
        body = ''
        if any((self.data, self.files, self.json)):
            content_type, content_len, body = await self._formulate_body()
            asks_headers['Content-Type'] = content_type
            asks_headers['Content-Length'] = content_len

        # add custom headers, if any
        # note that custom headers take precedence
        if self.headers is not None:
            asks_headers.update(self.headers)

        # add auth
        if self.auth is not None:
            asks_headers.update(await self.auth_handler_pre())
            asks_headers.update(await self.auth_handler_post_get_auth())

        # add all headers to package
        for k, v in asks_headers.items():
            package.append(k + ': ' + v)

        # add cookies
        if self.cookies:
            cookie_str = ''
            for k, v in self.cookies.items():
                cookie_str += '{}={}; '.format(k, v)
            package.append('Cookie: ' + cookie_str[:-1])
        # call i/o handling func
        response_obj = await self.request_io(package, body)

        return response_obj

    async def request_io(self, package, body):
        '''
        Takes care of the i/o side of the request once it's been built,
        and calls a couple of cleanup functions to check for redirects / store
        cookies and the likes.
        '''
        await self._send(package, body)
        response_obj = await self._catch_response()

        response_obj._parse_cookies(self.netloc)

        # If there's a cookie tracker object, store any cookies we
        # might've picked up along our travels.
        if self.persist_cookies is not None:
            self.persist_cookies._store_cookies(response_obj)

        # Have a crack at guessing the encoding of the response.
        response_obj._guess_encoding()

        # Check to see if there's a PostResponseAuth set, and does magic.
        if self.auth is not None:
            response_obj = await self.auth_handler_post_check_retry(
                response_obj)

        # check redirects
        if self.method != 'HEAD':
            if self.max_redirects < 0:
                raise TooManyRedirects
            response_obj = await self._redirect(response_obj)
        response_obj.history = self.history_objects

        return response_obj

    def _build_path(self):
        '''
        Constructs the actual request URL with accompanying query if any.
        '''
        if not self.path:
            self.path = '/'
        if self.query:
            self.path = self.path + '?' + self.query
        if self.params:
            try:
                if self.query:
                    self.path = self.path + self._dict_2_query(
                        self.params, base_query=True)
                else:
                    self.path = self.path + self._dict_2_query(self.params)
            except AttributeError:
                self.path = self.path + '?' + self._queryify(self.params)
        return self.path

    async def _redirect(self, response_obj):
        '''
        Calls the _check_redirect method of the supplied response object
        in order to determine if the http status code indicates a redirect.

        If it does, it calls the appropriate method with the redirect
        location, returning the response object. Furthermore, if there is
        a redirect, this function is recursive in a roundabout way, storing
        the previous response object in history_objects, and passing this
        persistent list on to the next or final call.
        '''
        redirect, force_get, location = False, None, None
        if 300 <= response_obj.status_code < 400:
            if response_obj.status_code in [301, 305]:
                # redirect / force GET / location
                redirect = True
                force_get = False
                location = response_obj.headers['Location']
            else:
                redirect = True
                force_get = True
                location = response_obj.headers['Location']

        if redirect:
            redirect_uri = urlparse(location.strip())
            # relative redirect
            if not redirect_uri.netloc:
                self.uri = urlunparse(
                    (self.scheme, self.netloc, *redirect_uri[2:]))

            # absolute-redirect
            else:
                self.uri = location.strip()

            # follow redirect with correct func
            if force_get:
                self.history_objects.append(response_obj)
                self.method = 'GET'
            else:
                self.history_objects.append(response_obj)
            self.max_redirects -= 1
            response_obj = await self.make_request()
        return response_obj

    async def _formulate_body(self):
        '''
        Takes user suppied data / files and forms it / them
        appropriately, returning the contents type, len,
        and the request body its self.
        '''
        c_type, body = None, ''
        multipart_ctype = ' multipart/form-data; boundary={}'.format(_BOUNDARY)
        if self.files is not None and self.data is not None:
            c_type = multipart_ctype
            wombo_combo = {**self.files, **self.data}
            body = await self._multipart(wombo_combo)

        elif self.files is not None:
            c_type = multipart_ctype
            body = await self._multipart(self.files)

        elif self.data is not None:
            c_type = ' application/x-www-form-urlencoded'
            try:
                body = self._dict_2_query(self.data, params=False)
            except AttributeError:
                body = self.data
                c_type = ' text/html'

        elif self.json is not None:
            c_type = ' application/json'
            body = _json.dumps(self.json)

        return c_type, str(len(body)), body

    def _dict_2_query(self, data, params=True, base_query=False):
        '''
        Turns python dicts in to valid body-queries or queries for use directly
        in the request url. Unlike the stdlib quote() and it's variations,
        this also works on iterables like lists which are normally not valid.

        The use of lists in this manner is not a great idea unless
        the server supports it. Caveat emptor.
        '''
        query = []

        for k, v in data.items():
            if not v:
                continue
            if isinstance(v, (str, Number)):
                query.append(self._queryify(
                    (k + '=' + '+'.join(str(v).split()))))
            elif isinstance(v, dict):
                for key in v:
                    query.append(self._queryify((k + '=' + key)))
            elif hasattr(v, '__iter__'):
                for elm in v:
                    query.append(
                        self._queryify((k + '=' +
                                       '+'.join(str(elm).split()))))

        if params and query:
            if not base_query:
                return '?' + '&'.join(query)
            else:
                return '&' + '&'.join(query)

        return '&'.join(query)

    async def _multipart(self, files_dict):
        '''
        Forms multipart requests from a dict with name, path k/vs. Name
        does not have to be the actual file name.
        '''
        boundary = bytes(_BOUNDARY, self.encoding)
        hder_format = 'Content-Disposition: form-data; name="{}"'
        hder_format_io = '; filename="{}"'

        multip_pkg = b''

        num_of_parts = len(files_dict)

        for index, kv in enumerate(files_dict.items(), start=1):
            multip_pkg += (b'--' + boundary + b'\r\n')
            k, v = kv

            try:
                async with aopen(v, 'rb') as o_file:
                    pkg_body = b''.join(await o_file.readlines()) + b'\r\n'
                multip_pkg += bytes(hder_format.format(k) +
                                    hder_format_io.format(basename(v)),
                                    self.encoding)
                mime_type = mimetypes.guess_type(basename(v))
                if not mime_type[1]:
                    mime_type = 'application/octet-stream'
                else:
                    mime_type = '/'.join(mime_type)
                multip_pkg += bytes('; Content-Type: ' + mime_type,
                                    self.encoding)
                multip_pkg += b'\r\n'*2 + pkg_body

            except (TypeError, FileNotFoundError):
                pkg_body = bytes(v, self.encoding) + b'\r\n'
                multip_pkg += bytes(hder_format.format(k) +
                                    '\r\n'*2, self.encoding)
                multip_pkg += pkg_body

            if index == num_of_parts:
                multip_pkg += b'--' + boundary + b'--\r\n'
        return multip_pkg

    def _queryify(self, query):
        '''
        Turns stuff in to a valid url query.
        '''
        return quote(query.encode(self.encoding, errors='strict'),
                     safe='/=+?&')

    async def _catch_response(self):
        '''
        Instanciates the parser which manages incoming data, first getting
        the headers, storing cookies, and then parsing the response's body,
        if any. Supports normal and chunked response bodies.

        This function also instances the Response class in which the response
        satus line, headers, cookies, and body is stored.

        It should be noted that in order to remain preformant, if the user
        wishes to do any file IO it should use async files or risk long wait
        times and risk connection issues server-side when using callbacks.

        If a callback is used, the response's body will be the __name__ of
        the callback function.
        '''
        parser = HttpParser(self.sock)
        resp = await parser.parse_stream_headers(self.timeout)
        cookies = resp.pop('cookies')
        statuscode = int(resp.pop('status_code'))
        parse_kwargs = {}
        try:
            content_len = int(resp['headers']['Content-Length'])

            if content_len > 0:
                if self.callback:
                    parse_kwargs = {'length': content_len,
                                    'callback': self.callback}
                    resp['body'] = ''
                else:
                    parse_kwargs = {'length': content_len}

        except KeyError:
            try:
                if resp['headers']['Transfer-Encoding'].strip() == 'chunked':
                    parse_kwargs = {'chunked': True}
            except KeyError:
                pass
        if parse_kwargs:
            resp['body'] = await parser.parse_body(**parse_kwargs)
        else:
            resp['body'] = None
        return Response(
            self.encoding, cookies, statuscode, method=self.method, **resp)

    async def _send(self, package, body):
        '''
        Takes a package (a list of str items) and shoots 'em off in to
        the ether.
        '''
        http_package = bytes(
            ('\r\n'.join(package) + '\r\n\r\n'), self.encoding)

        if body:
            try:
                http_package += body
            except TypeError:
                http_package += bytes(body, self.encoding)

        await self.sock.write(http_package)

    async def auth_handler_pre(self):
        '''
        If the user supplied auth does not rely on any response
        (is a PreResponseAuth object) then we call the auth's __call__
        returning a dict to update the request's headers with.
        '''
        if isinstance(self.auth, PreResponseAuth):
            return await self.auth(self)
        return {}

    async def auth_handler_post_get_auth(self):
        '''
        If the user supplied auth does rely on a response
        (is a PostResponseAuth object) then we call the auth's __call__
        returning a dict to update the request's headers with, as long
        as there is an appropriate 401'd response object to calculate auth
        details from.
        '''
        if isinstance(self.auth, PostResponseAuth):
            if self.history_objects:
                authable_resp = self.history_objects[-1]
                if authable_resp.status_code == 401:
                    if not self.auth.auth_attempted:
                        self.auth.auth_attempted = True
                        return await self.auth(authable_resp, self)
        return {}

    async def auth_handler_post_check_retry(self, response_obj):
        '''
        The other half of auth_handler_post_check_retry (what a mouthfull).
        If auth has not yet been attempted and the most recent response
        object is a 401, we store that response object and retry the request
        in exactly the same manner as before except with the correct auth.

        If it fails a second time, we simply return the failed response.
        '''
        if isinstance(self.auth, PostResponseAuth):
            if response_obj.status_code == 401:
                if not self.auth.auth_attempted:
                    self.history_objects.append(response_obj)
                    r = await self.make_request()
                    self.auth.auth_attempted = False
                    return r
                else:
                    response_obj.history = self.history_objects
                    return response_obj
        return response_obj
