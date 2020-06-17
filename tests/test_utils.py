# pylint: disable=no-member

from urllib.parse import urlparse

from asks.utils import get_netloc_port


def test_netloc_port():
    assert ("example.com", "80") == get_netloc_port(urlparse("http://example.com"))
    assert ("example.com", "443") == get_netloc_port(urlparse("http://example.com:443"))
    assert ("example.com", "443") == get_netloc_port(urlparse("https://example.com"))
    assert ("example.com", "1234") == get_netloc_port(
        urlparse("https://example.com:1234")
    )

    ipv4addr = "10.0.0.1"
    assert (ipv4addr, "80") == get_netloc_port(urlparse("http://{}".format(ipv4addr)))
    assert (ipv4addr, "443") == get_netloc_port(urlparse("https://{}".format(ipv4addr)))
    assert (ipv4addr, "1234") == get_netloc_port(
        urlparse("http://{}:1234".format(ipv4addr))
    )
    assert (ipv4addr, "1234") == get_netloc_port(
        urlparse("https://{}:1234".format(ipv4addr))
    )

    ipv6addr = "aaaa:bbbb:cccc:dddd:eeee:ffff:1111:2222"
    assert (ipv6addr, "80") == get_netloc_port(urlparse("http://[{}]".format(ipv6addr)))
    assert (ipv6addr, "443") == get_netloc_port(
        urlparse("https://[{}]".format(ipv6addr))
    )
    assert (ipv6addr, "1234") == get_netloc_port(
        urlparse("http://[{}]:1234".format(ipv6addr))
    )
    assert (ipv6addr, "1234") == get_netloc_port(
        urlparse("https://[{}]:1234".format(ipv6addr))
    )
