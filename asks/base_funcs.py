from urllib.parse import urlparse, urlunparse
from functools import partial

from asks.sessions import Session


__all__ = ['get', 'head', 'post', 'put', 'delete', 'options', 'request']


async def request(method, uri, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    scheme, netloc, path, _, query, _ = urlparse(uri)
    s = Session((scheme + '://' + netloc),
                endpoint=urlunparse(('', '', path, '', query, '')),
                cookie_interactions=c_interact)
    r = await s.request(method, path='', **kwargs)
    return r


get = partial(request, 'GET')
head = partial(request, 'HEAD')
post = partial(request, 'POST')
put = partial(request, 'PUT')
delete = partial(request, 'DELETE')
options = partial(request, 'OPTIONS')
