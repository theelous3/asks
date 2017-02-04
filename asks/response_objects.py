import json as _json
import gzip
import zlib

from types import SimpleNamespace

from .encode_values import encode_strings


class Response(SimpleNamespace):
    '''
    A response object supporting a range of methods and attribs
    for accessing the status line, header, cookies, history and
    body of a response.
    '''
    def __init__(self, encoding, cookies, **data):
        super().__init__(**data)
        self.encoding = encoding
        self.history = []
        self.cookies = cookies

    def __repr__(self):
        return '<Response object {}>'.format(hex(id(self)))

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v

    def _check_redirect(self):
        if self.status_code.startswith('3'):
            if self.status_code in ['301', '305']:
                # redirect / force GET / location
                return True, False, self.headers['Location']
            else:
                return True, True, self.headers['Location']
        else:
            return False, None, None

    def _guess_encoding(self):
        try:
            guess = self.headers['content-type'].split('=')[1]
        except:
            pass
        else:
            if guess in encode_strings:
                self.encoding = guess

    def _parse_cookies(self, host):
        cookie_pie = []
        for cookie in self.cookies:
            cookie_jar = {}
            name_val, *rest = cookie.split(';')
            name, value = name_val.split('=')
            cookie_jar['name'] = name
            cookie_jar['value'] = value
            for item in rest:
                try:
                    name, value = item.split('=')
                    cookie_jar[name.lower().lstrip()] = value
                except ValueError:
                    cookie_jar[item.lower().lstrip()] = True
            cookie_pie.append(cookie_jar)
        self.cookies = [Cookie(host, x) for x in cookie_pie]

    def _decompress(self, body):
        try:
            resp_encoding = self.headers['Content-Encoding'].strip()
        except KeyError:
            return body
        try:
            if resp_encoding == 'gzip':
                return gzip.decompress(body)
            elif resp_encoding == 'deflate':
                return zlib.decompress(body)
        except KeyError:
            pass
        return body

    def encoding(self, new_encoding):
        self.encoding = new_encoding

    def json(self):
        body = self._decompress(self.body)
        try:
            return _json.loads(body.decode(encoding=self.encoding,
                                            errors='replace'))
        except AttributeError:
            return None

    @property
    def text(self):
        try:
            return self._decompress(self.body).decode(self.encoding,
                                                      errors='replace')
        except AttributeError:
            return self._decompress(self.body)

    @property
    def content(self):
        return self._decompress(self.body)

    @property
    def raw(self):
        return self.body


class Cookie(SimpleNamespace):
    '''
    A simple cookie object, for storing cookie stuff :)
    Needs to be made compatible with the API's cookies kw arg.
    '''
    def __init__(self, host, data):
        self.name = None
        self.value = None
        self.domain = None
        self.path = None
        self.secure = False
        self.expires = None
        self.comment = None
        for k, v in data.items():
                setattr(self, k, v)
        super().__init__(**self.__dict__)
        self.host = host

    def __repr__(self):
        return '<Cookie {} from {}>'.format(self.name, self.host)

    def __iter__(self):
        for k, v in self.__dict__.items():
            yield k, v
