from functools import partial

from asks.sessions import DSession


__all__ = ['get', 'head', 'post', 'put', 'delete', 'options', 'request']


async def request(method, uri, **kwargs):
    c_interact = kwargs.pop('cookie_interactions', None)
    s = DSession(cookie_interactions=c_interact)
    r = await s.request(method, url=uri, **kwargs)
    return r


get = partial(request, 'GET')
head = partial(request, 'HEAD')
post = partial(request, 'POST')
put = partial(request, 'PUT')
delete = partial(request, 'DELETE')
options = partial(request, 'OPTIONS')
