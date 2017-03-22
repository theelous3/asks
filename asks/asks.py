from urllib.parse import urlparse, urlunparse
from asks.sessions import Session


__all__ = ['get', 'head', 'post', 'put', 'delete', 'options']


async def get(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = await s.get(**kwargs)
    return r


async def head(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = s.head(**kwargs)
    return r


async def post(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = await s.post(**kwargs)
    return r


async def put(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = await s.put(**kwargs)
    return r


async def delete(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = await s.delete(**kwargs)
    return r


async def options(uri, port=443, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = await Session((scheme + '://' + netloc),
                      port=port,
                      endpoint=urlunparse(('', '', path, '', query, '')),
                      cookie_interactions=c_interact)
    r = await s.options(**kwargs)
    return r
