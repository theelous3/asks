'''
Experimental! Probably borked!
Run away :D
'''

from urllib.parse import urlparse

from curio.meta import AsyncObject

import asks.asks as asks_


__all__ = ['ApiSession']


class ApiSession(AsyncObject):

    async def __init__(self,
                       host,
                       port=443,
                       endpoint=None,
                       encoding='utf-8',
                       store_cookies=False):

        self.encoding = encoding
        self.endpoint = endpoint
        self.store_cookies = store_cookies
        self.host = host
        self.port = port
        self.netloc = ''
        self.sock = None
        self.cookies = {}
        self.response_history = []
        self.current_url = None

        await self._run()

    async def _run(self):
        self._get_schema()
        await self._connect()

    def _get_schema(self):
        if not self.host.startswith('http'):
            self.host = 'https://' + self.host

    async def _connect(self):
        scheme, netloc, path, parameters, query, fragment = urlparse(self.host)
        if any((path, parameters, query, fragment)):
            raise ValueError('Supplied info beyond scheme, netloc.' +
                             ' Host should be top level only.')
        self.netloc = netloc
        if scheme == 'http':
            self.port = 80
            self.sock = await asks_._open_connection_http(
                (self.netloc, self.port))
        else:
            self.sock = await asks_._open_connection_https(
                (self.netloc, self.port))

    def _make_url(self):
        return self.host + (self.endpoint or '')

    async def get(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='GET',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    async def head(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='HEAD',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    async def post(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='POST',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    async def put(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='PUT',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    async def delete(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='DELETE',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    async def options(self, path, *args, **kwargs):
        url = self._make_url() + path
        self.set_current_endpoint(url)

        fresh_cookies = self._bake_cookies(kwargs.pop('cookies', {}))

        r = await asks_._build_request(url,
                                       method='OPTIONS',
                                       sock=self.sock,
                                       cookies=fresh_cookies,
                                       encoding=self.encoding,
                                       **kwargs)
        if self.store_cookies is True:
            self._store_cookies(r)
        return r

    def set_current_endpoint(self, url):
        scheme, netloc, path, parameters, query, fragment = urlparse(url)
        netloc.replace('www.', '')
        self.current_url = netloc + path

    def _store_cookies(self, response_obj):
        for cookie in response_obj.cookies:
            try:
                self.cookies[cookie.domain].append(cookie)
            except KeyError:
                self.cookies[cookie.domain] = [cookie]

        for response in response_obj.history:
            for cookie in response.cookies:
                try:
                    self.cookies[cookie.domain].append(cookie)
                except KeyError:
                    self.cookies[cookie.domain] = [cookie]

    def _bake_cookies(self, cookies):
        hot_cookie_domains = self._check_cookies()
        if hot_cookie_domains:
            gooey_cookies = self._get_cookies_to_send(hot_cookie_domains)
            cookies = {**gooey_cookies, **cookies}
        return cookies

    def _check_cookies(self):
        relevant_domains = []
        cookie_keys = self.cookies.keys()
        if cookie_keys:
            if self.current_url in cookie_keys:
                relevant_domains.append(self.cookies[self.current_url])

            parts = self.current_url.split('/')
            for index, path_chunk in enumerate(parts, start=1):
                check_domain = '/'.join(parts[:index*-1])
                if check_domain in cookie_keys:
                    relevant_domains.append(self.cookies[check_domain])

        return relevant_domains

    def _get_cookies_to_send(self, domain_list):
        cookies_to_go = {}
        for domain in domain_list:
            for cookie in self.cookies[domain]:
                cookies_to_go[self.cookiescookie_obj.name] = cookie_obj.value

        return cookies_to_go
