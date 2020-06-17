"""
These functions are for making small amounts of async requests.
They construct a temporary Session, returning the resulting response object
to the caller.
"""
from functools import partial

from .sessions import Session


__all__ = ["get", "head", "post", "put", "delete", "options", "patch", "request"]


async def request(method, uri, **kwargs):
    """Base function for one time http requests.

    Args:
        method (str): The http method to use. For example 'GET'
        uri (str): The url of the resource.
            Example: 'https://example.com/stuff'
        kwargs: Any number of arguments supported, found here:
            http://asks.rtfd.io/en/latest/overview-of-funcs-and-args.html

    Returns:
        Response (asks.Response): The Response object.
    """
    c_interact = kwargs.pop("persist_cookies", None)
    ssl_context = kwargs.pop("ssl_context", None)
    async with Session(persist_cookies=c_interact, ssl_context=ssl_context) as s:
        r = await s.request(method, url=uri, **kwargs)
        return r


# The functions below are the exact same as the ``request`` function
# above, with the method argument already passed.
get = partial(request, "GET")
head = partial(request, "HEAD")
post = partial(request, "POST")
put = partial(request, "PUT")
delete = partial(request, "DELETE")
options = partial(request, "OPTIONS")
patch = partial(request, "PATCH")
