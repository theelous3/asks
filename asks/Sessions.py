'''
Experimental! Probably borked.
Initial testing shows this is working a-ok, but no guarantees!

TO DO:
    * Write tests
    * Connection pooling
'''

import asks as asks_
from .cookie_utils import CookieTracker


__all__ = ['Session']


class Session:

    def __init__(self,
                 host,
                 port=443,
                 endpoint=None,
                 encoding='utf-8',
                 store_cookies=None):

        self.encoding = encoding
        self.endpoint = endpoint
        self.host = host
        self.port = port
        self.netloc = ''

        if store_cookies is True:
            self.cookie_tracker_obj = CookieTracker()
        else:
            self.cookie_tracker_obj = store_cookies

    def _make_url(self):
        return self.host + (self.endpoint or '')

    async def get(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def head(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def post(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def put(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def delete(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r

    async def options(self, path='', *args, **kwargs):
        url = self._make_url() + path

        r = await asks_.get(url,
                            encoding=self.encoding,
                            persist_cookies=self.cookie_tracker_obj,
                            **kwargs)
        return r
