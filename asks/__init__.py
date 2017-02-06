from numbers import Number
from os.path import basename
from urllib.parse import urlparse, urlunparse, quote
import json as _json

from curio import socket
from curio.file import aopen

from .req_structs import CaseInsensitiveDict as c_i_Dict
from .response_objects import Response
from .http_req_parser import HttpParser
from .exceptions import TooManyRedirects


__all__ = ['get', 'head', 'post', 'put', 'delete', 'options']


_BOUNDARY = "8banana133744910kmmr13ay5fa56"

_HTTP_METHODS = {}


def _method_map(func):
    '''
    A simple decorator to store HTTP methods in a dict for use in redirects.
    '''
    _HTTP_METHODS[func.__name__.upper()] = func
    return func


async def _build_request(uri,
                         auth=None,
                         data=None,
                         params=None,
                         headers=None,
                         method=None,
                         encoding='utf-8',
                         json=None,
                         files=None,
                         cookies=None,
                         callback=None,
                         timeout=9999,
                         max_redirects=float('inf'),
                         history_objects=[]):
    '''
    Takes kw args from any of the public api HTTP methods (get, post, etc.)
    and acts as a request builder, and center point for sending
    those requests, recieving the responses, handling any redirects
    along the way and returning the final response object.

    Currently a slight disaster of a function. Needs to be broken up a
    little more, especially the section regarding redirects.
    '''
    scheme, netloc, path, parameters, query, fragment = urlparse(uri)
    try:
        netloc, port = netloc.split(':')
        cnect_to = netloc, int(port)
    except ValueError:
        cnect_to = (netloc, 80)

    host = (cnect_to[0] if cnect_to[1] == 80 else
            ':'.join(map(str, cnect_to)))

    # default header construction
    _headers = c_i_Dict([('Host', ' ' + host),
                         ('Connection', ' keep-alive'),
                         ('Accept-Encoding', ' gzip, deflate'),
                         ('Accept', ' */*'),
                         ('Content-Length', ' 0'),
                         ('User-Agent', ' python-asks/0.0.1')
                         ])

    # formulate path / query and intended extra querys for use in uri
    path = _build_path(path, query, params, encoding)

    package = [' '.join((method, path, 'HTTP/1.1'))]

    # handle building the request body, if any
    if any((data, files, json)):
        content_type, content_len, query_data = await _formulate_body(encoding,
                                                                      data,
                                                                      files,
                                                                      json)
        _headers['Content-Type'] = content_type
        _headers['Content-Length'] = content_len
    else:
        query_data = ''

    # add custom headers, if any
    # note that custom headers take precedence
    if headers:
        _headers = {**_headers, **headers}

    # add all headers to package
    for k, v in _headers.items():
        package.append(k + ': ' + v)

    # add cookies
    if cookies:
        for k, v in cookies.items():
            package.append('Cookie: {}={}'.format(k, v))

    # begin interfacing with remote server
    sock = await _open_connection(cnect_to)
    parser = HttpParser(sock)
    async with sock:
        # send
        await _send(sock,
                    package,
                    encoding,
                    data)

        # recv and return Response object
        response_obj = await _catch_response(sock,
                                             encoding,
                                             timeout,
                                             callback)

    response_obj._parse_cookies(_headers['Host'])
    response_obj._guess_encoding()
    # check redirects
    if method != 'HEAD':
        if max_redirects < 0:
            raise TooManyRedirects
        else:
            max_redirects -= 1
        response_obj = await _redirect(method,
                                       response_obj,
                                       (scheme, host.strip()),
                                       history_objects,
                                       encoding=encoding,
                                       timeout=timeout,
                                       max_redirects=max_redirects)

    response_obj.history = history_objects
    return response_obj


def _build_path(path, query, params, encoding):
    '''
    Constructs from supplied args the actual request URL with
    accompanying query if any.
    '''
    if not path:
        path = '/'
    if query:
        path = path + '?' + query
    if params:
        try:
            if query:
                path = path + _dict_to_query(params, encoding, base_query=True)
            else:
                path = path + _dict_to_query(params, encoding)
        except AttributeError:
            path = path + '?' + _queryify(params, encoding)
    return path


async def _redirect(method,
                    response_obj,
                    current_netloc,
                    history_objects,
                    **kwargs):
    '''
    Calls the _check_redirect method of the supplied response object
    in order to determine if the http status code indicates a redirect.

    If it does, it calls the appropriate method with the next request
    location, returning the response object. Furthermore, if there is
    a redirect, this function is recursive in a roundabout way, storing
    the previous response object in history_objects, and passing this
    persistent list on to the next or final call.
    '''
    redirect, force_get, location = response_obj._check_redirect()
    if redirect:
        redirect_uri = urlparse(location.strip())
        # relative redirect
        if not redirect_uri.netloc:
            new_uri = urlunparse((*current_netloc,
                                 *redirect_uri[2:]))

        # absolute-redirect
        else:
            new_uri = location.strip()

        # follow redirect with correct func
        if force_get:
            history_objects.append(response_obj)
            next_call = get
        else:
            history_objects.append(response_obj)
            next_call = _HTTP_METHODS[method]

        response_obj = await next_call(new_uri,
                                       history_objects=history_objects,
                                       **kwargs)
    return response_obj


async def _formulate_body(encoding, data, files, json):
    '''
    Takes user suppied data / files and forms it / them
    appropriately, returning the contents type, len,
    and the request body its self.
    '''
    c_type, content_len, query_data = None, '0', ''
    multipart_ctype = ' multipart/form-data; boundary={}'.format(_BOUNDARY)
    if files and data:
        c_type = multipart_ctype
        wombo_combo = {**files, **data}
        query_data = await _multipart(wombo_combo, encoding)

    elif files:
        c_type = multipart_ctype
        query_data = await _multipart(files, encoding)

    elif data:
        c_type = ' application/x-www-form-urlencoded'
        try:
            query_data = _dict_to_query(data, encoding, params=False)
        except AttributeError:
            query_data = data
            c_type = ' text/html'

    elif json:
        c_type = ' application/json'
        query_data = _json.dumps(json)

    return c_type, str(len(query_data)), query_data


def _dict_to_query(data, encoding, params=True, base_query=False):
    '''
    Turns python dicts in to valid body-queries or queries for use directly
    in the request url. Unlike the stdlib quote() and it's variations,
    this also works on iterables like lists which are normally not valid.

    The use of lists in this manner is, I suppose not a great idea unless
    the server supports it. Caveat emptor.
    '''
    query = []

    for k, v in data.items():
        if not v:
            continue
        if isinstance(v, (str, Number)):
            query.append(_queryify((k + '=' + '+'.join(str(v).split())),
                                   encoding))
        elif isinstance(v, dict):
            for key in v.keys():
                query.append(_queryify((k + '=' + key), encoding))
        elif hasattr(v, '__iter__'):
            for elm in v:
                query.append(_queryify((k + '=' + '+'.join(str(elm).split())),
                                       encoding))

    if params and query:
        if not base_query:
            return '?' + '&'.join(query)
        else:
            return '&' + '&'.join(query)

    return '&'.join(query)


async def _multipart(files_dict, encoding):
    '''
    Forms multipart requests from a dict with name, path k/vs. Name
    does not have to be the actual file name.
    '''
    boundary = b"--8banana133744910kmmr13ay5fa56"
    hder_format = 'Content-Disposition: form-data; name="{}"'
    hder_format_io = hder_format + '; filename="{}"'

    multip_pkg = b''

    num_of_parts = len(files_dict)

    for index, kv in enumerate(files_dict.items(), start=1):
        multip_pkg += boundary + b'\r\n'
        k, v = kv

        try:
            async with aopen(v, 'rb') as o_file:
                pkg_body = b''.join(await o_file.readlines()) + b'\r\n'
            multip_pkg += bytes(hder_format_io.format(k, basename(v)) +
                                '\r\n'*2,
                                encoding)
            multip_pkg += pkg_body

        except (TypeError, FileNotFoundError):
            pkg_body = bytes(v, encoding) + b'\r\n'
            multip_pkg += bytes(hder_format.format(k) + '\r\n'*2, encoding)
            multip_pkg += pkg_body

        if index == num_of_parts:
            multip_pkg += boundary + b'--\r\n'

    return multip_pkg


def _queryify(query, encoding):
    '''
    Turns stuff in to a valid url query.
    '''
    return quote(query.encode(encoding, errors='strict'),
                 safe='/=+?&')


async def _catch_response(sock, encoding, timeout, callback):
    '''
    Instanciates the parser which manages incoming data, first getting
    the headers, storing cookies, and then parsing the response's body,
    if any. Supports normal and chunked response bodies.

    This function also instances the Response class in which the response
    satus line, headers, cookies, and body is stored.

    Has an optional arg for callbacks passed by _build_request in which
    the user can supply a function to be called on each chunk of data recieved.

    It should be noted that in order to remain preformant, if the user wishes
    to do any file IO it should use async files or risk long wait times and
    risk connection issues server-side.

    If a callback is used, the response's body will be the __name__ of
    the callback function.
    '''
    parser = HttpParser(sock)
    resp = await parser.parse_stream_headers(timeout)
    cookies = resp.pop('cookies')
    statuscode = int(resp.pop('status_code'))
    parse_kwargs = {}
    try:
        content_len = int(resp['headers']['Content-Length'])

        if content_len > 0:
            if callback:
                parse_kwargs = {'length': content_len, 'callback': callback}
                await parser.parse_body(length=content_len,
                                        callback=callback)
                resp['body'] = '{}'.format(callback.__name__)
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
    return Response(encoding, cookies, statuscode, **resp)


async def _open_connection(location):
    '''
    Creates an async socket, set to stream mode and returns it.
    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    await sock.connect(location)
    sock = sock.as_stream()
    return sock


async def _send(sock, package, encoding, body):
    '''
    Takes a package (a list of str items) and shoots 'em off in to the ether.
    '''
    http_package = bytes(('\r\n'.join(package) + '\r\n\r\n'), encoding)

    if body:
        try:
            http_package += body
        except TypeError:
            http_package += bytes(body, encoding)

    await sock.write(http_package)


@_method_map
async def get(uri, **kwargs):
    return await _build_request(uri, method='GET', **kwargs)


@_method_map
async def head(uri, **kwargs):
    return await _build_request(uri, method='HEAD', **kwargs)


@_method_map
async def post(uri, **kwargs):
    return await _build_request(uri, method='POST', **kwargs)


@_method_map
async def put(uri, **kwargs):
    return await _build_request(uri, method='PUT', **kwargs)


@_method_map
async def delete(uri, **kwargs):
    return await _build_request(uri, method='DELETE', **kwargs)


@_method_map
async def options(uri, **kwargs):
    return await _build_request(uri, method='OPTIONS', **kwargs)
