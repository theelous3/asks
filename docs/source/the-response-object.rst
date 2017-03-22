asks - The Response Object
==========================

A plain ol' response object, ``Response`` is returned from every request.

It has some attribs/properties to access the response content from, and it works some minor magic when it can. Nothing too voodoo though.

Encoding
________

By default the ``Response`` object tries to use ``utf-8``.

The response object will try to guess its own encoding before it's returned, given the appropriate headers in the response.

You can override the guessed or default encoding with either a builtin encoding or one you've registered locally with your codecs module by accessing ``Response.encoding``. ::

    async def main():
        r = asks.get('http://example.com')

        r.encoding = 'latin-1'

Status Line
___________

The three parts of the status line, are the HTTP-Version, Status-Code and Reason-Phrase. They can be accessed as attributes of the response object like so::

    async def main():
        r = asks.get('http://example.com')

        r.http_version  # -> 'HTTP/1.1'
        r.status_code   # -> 200
        r.reason_phrase # -> 'OK'

Headers
_______

The headers are available as a dict through ``Response.headers`` ::

    async def main():
        r = asks.get('http://example.com')
        print(r.headers)

    # Results in:
    # {'Content-Encoding': 'gzip', 'Accept-Ranges': 'bytes', ...


JSON
____

If the response body is valid JSON you can load it as a python dict by calling the response object's ``.json()`` method.

If the response was compressed, it will be decompressed. ::

    async def main():
        r = asks.get('http://httpbin.org/get')
        j = r.json()
        print(j)

    # Results in
    # {'args': {}, 'headers': {'Accept': '*/*', 'Accept-Encoding', ...


View Body (text decoded, content, barebones)
____________________________________________

Generally the way to see the body as it was intended is to use the ``.content`` property. This will return the content as is, after decompression if there was any.

For something slightly more human readable, you may want to try the ``.text`` property. This will attempt to decompress (if needed) and decode the content (with ``.encoding``). This for example, makes html and json etc. quite readable in your shell.

To view the body exactly as it was sent, just use the ``.body`` attribute. Note that this may be compressed madness, so don't worry if you can't read it with your poor wee eyes. ::

    async def main():
            r = asks.get('http://example.com')

            r.content
            r.text
            r.body


Cookies
_______

Each response object will keep a list of any cookies set during the response, acessible by the ``.cookies`` attribute. Each cookie is a ``Cookie`` object. They are pretty basic. Here's a list of attributes:

* ``.name``
* ``.value``
* ``.domain``
* ``.path``
* ``.secure``
* ``.expires``
* ``.comment``
* ``.host``

There may be more values set by the response.

Response History
________________

If any redirects or 401-requiring auth attempts were handled during the request, the response objects for those requests will be stored in the final response object's ``.history`` attribute in a list. Any response objects found in there are exactly like your main response object, and have all of the above methods, properties, and attributes. ::

    async def main():
            r = asks.get('http://httpbin.org/redirect/3')
            print(r.history)
            print(r.history[1].status_code)

        # Results in:
        # [<Response 302 at 0xb6a807cc>, <Response 302 at 0xb...
        # 302

