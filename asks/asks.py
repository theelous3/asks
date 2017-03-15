from urllib.parse import urlparse, urlunparse
from asks.sessions import Session


__all__ = ['get', 'head', 'post', 'put', 'delete', 'options']


def _get_schema(uri):
    '''
    Figures out the appropriate http type.
    '''
    if not uri.startswith('http'):
        uri = 'https://' + uri
    return uri


async def get(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = await s.get(**kwargs)
    return r


async def head(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = s.head(**kwargs)
    return r


async def post(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = await s.post(**kwargs)
    return r


async def put(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = await s.put(**kwargs)
    return r


async def delete(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = await s.delete(**kwargs)
    return r


async def options(uri, port=443, **kwargs):
    s_cookie = kwargs.pop('store_cookies', None)
    scheme, netloc, path, _, query, _ = urlparse(_get_schema(uri))
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      store_cookies=s_cookie)
    r = await s.options(**kwargs)
    return r
