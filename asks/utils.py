__all__ = ["get_netloc_port", "requote_uri", "timeout_manager"]


from urllib.parse import quote
from functools import wraps

from anyio import fail_after

from .errors import RequestTimeout


async def timeout_manager(timeout, coro, *args):
    try:
        with fail_after(timeout):
            return await coro(*args)
    except TimeoutError as e:
        raise RequestTimeout from e


def get_netloc_port(parsed_url):
    port = parsed_url.port
    if not port:
        if parsed_url.scheme == "https":
            port = "443"
        else:
            port = "80"
    return parsed_url.hostname, str(port)


# The unreserved URI characters (RFC 3986)
UNRESERVED_SET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" + "0123456789-._~"
)


def unquote_unreserved(uri):
    """Un-escape any percent-escape sequences in a URI that are unreserved
    characters. This leaves all reserved, illegal and non-ASCII bytes encoded.
    :rtype: str
    """
    parts = uri.split("%")
    for i in range(1, len(parts)):
        h = parts[i][0:2]
        if len(h) == 2 and h.isalnum():
            try:
                c = chr(int(h, 16))
            except ValueError:
                raise ValueError("Invalid percent-escape sequence: '%s'" % h)

            if c in UNRESERVED_SET:
                parts[i] = c + parts[i][2:]
            else:
                parts[i] = "%" + parts[i]
        else:
            parts[i] = "%" + parts[i]
    return "".join(parts)


def requote_uri(uri):
    """Re-quote the given URI.
    This function passes the given URI through an unquote/quote cycle to
    ensure that it is fully and consistently quoted.
    :rtype: str
    """
    safe_with_percent = "!#$%&'()*+,/:;=?@[]~"
    safe_without_percent = "!#$&'()*+,/:;=?@[]~"
    try:
        # Unquote only the unreserved characters
        # Then quote only illegal characters (do not quote reserved,
        # unreserved, or '%')
        return quote(unquote_unreserved(uri), safe=safe_with_percent)
    except ValueError:
        # We couldn't unquote the given URI, so let's try quoting it, but
        # there may be unquoted '%'s in the URI. We need to make sure they're
        # properly quoted so they do not cause issues elsewhere.
        return quote(uri, safe=safe_without_percent)


def processor(gen):
    @wraps(gen)
    def wrapper(*args, **kwargs):
        g = gen(*args, **kwargs)
        next(g)
        return g

    return wrapper
