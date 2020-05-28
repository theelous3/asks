``asks`` - The Response Object
==============================

A plain ol' response object, ``Response`` is returned by default.

It has some attribs/properties to access the response content. Nothing too voodoo.

If you set ``stream=True`` a ``StreamResponse`` object is returned.

Both response types are subclasses of ``BaseResponse``, for all of your typing needs.

Encoding
________

By default the ``Response`` object uses ``utf-8``.

The response object will try to glean encoding from the response headers if available, before it's returned.

You can override the response-set or default encoding with either a built-in encoding or one you've registered locally with your ``codecs`` module by accessing the response's ``.encoding`` attribute. ::

    async def main():
        r = await asks.get('http://example.com')
        r.encoding = 'latin-1'

Status Line
___________

The three parts of the status line are the HTTP-Version, Status-Code and Reason-Phrase.
They can be accessed as attributes of the response object like so::

    async def main():
        r = await asks.get('http://example.com')

        r.http_version  # -> '1.1'
        r.status_code   # -> 200
        r.reason_phrase # -> 'OK'

Headers
_______

The headers are available as a ``dict`` through ``Response.headers`` ::

    async def main():
        r = await asks.get('http://example.com')
        print(r.headers)

    # Results in:
    # {'Content-Encoding': 'gzip', 'Accept-Ranges': 'bytes', ...


JSON
____
Only available on ``Response`` objects.

If the response body is valid JSON you can load it as a Python ``dict`` by calling the response object's ``.json()`` method.

If the response was compressed, it will be decompressed. ::

    async def main():
        r = await asks.get('http://httpbin.org/get')
        j = r.json()
        print(j)

    # Results in
    # {'args': {}, 'headers': {'Accept': '*/*', 'Accept-Encoding', ...


View Body (text decoded, content, raw)
______________________________________

These are only available on the ``Response`` object; returned when ``stream=False``, which is the default behaviour.

Generally the way to see the body as it was intended is to use the ``.content`` property.
This will return the content as is, after decompression if there was any.

For something slightly more human-readable, you may want to try the ``.text`` property.
This will attempt to decompress (if needed) and decode the content (with ``.encoding``).
This for example, makes HTML and JSON etc. quite readable in your shell.

To view the body exactly as it was sent, just use the ``.body`` attribute.
Note that this may be compressed madness, so don't worry if you can't read it with your poor wee eyes. ::

    async def main():
        r = await asks.get('http://example.com')

        r.content
        r.text
        r.body


Streaming
_________

If the request was made with ``stream=True``, the object returned will be a ``StreamResponse`` whose ``.body`` attribute will point to an iterable ``StreamBody`` object from which you can stream data.

You may add a timeout to each poll for data by including ``timeout`` in the creation of the context manager.
Example below alongside disabling data decompression.

To disable automatic decompression on the stream, set the ``StreamBody.decompress_data`` to ``False``. ::

    async def main():
        r = await asks.get('http://example.com')
        r.decompress_data = False
        async for chunk in r.body(timeout=5):
            print(r)


Cookies
_______

Each response object will keep a list of any cookies set during the response, accessible by the ``.cookies`` attribute.
Each cookie is a ``Cookie`` object. They are pretty basic. Here's a list of attributes:

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

If any redirects or 401-requiring auth attempts were handled during the request, the response objects for those requests will be stored in the final response object's ``.history`` attribute in a list.
Any response objects found in there are exactly like your main response object, and have all of the above methods, properties, and attributes. ::

    async def main():
        r = await asks.get('http://httpbin.org/redirect/3')
        print(r.history)
        print(r.history[1].status_code)

    # Results in:
    # [<Response 302 at 0xb6a807cc>, <Response 302 at 0xb...
    # 302


URL
___

Find the URL that the request was made to.::

    async def main():
        r = await asks.get('http://example.com')
        print(r.url)

    # Results in:
    # 'http://example.com'
