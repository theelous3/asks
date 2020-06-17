``asks`` - An overview of the functions and kw/arguments.
=========================================================

``asks`` is *heavily* influenced by requests, and as such pretty much everything that works in ``requests`` works in ``asks``.
So, if you're familiar with the format you can pretty much skip to the distinctions regarding `sessions <https://asks.readthedocs.io/en/latest/a-look-at-sessions.html>`_

The examples here use the base one-request-functions for verbosity's sake, but all of these functions are completely transferable to the ``Session`` class as methods.

*Warning!*

If you don't use a ``Session`` you can easily max out your OS's socket resources against highly performant servers (usually local to the machine or LAN). When using the base functions you'll be creating a new connection for every request.

(Calling ``asks.get('https://some-url.io'))`` really makes a temporary ``Session``.)


General HTTP methods
____________________

``asks`` supports ``get()``, ``head()``, ``post()``, ``put()``, ``delete()``, ``options()``, ``patch()`` and ``request()``.

``request`` takes a HTTP method as a string for its first argument.

When using the basic functions they each require a URI::

    import asks

    async def blah():
        a = await asks.get('https://example.com')
        s = await asks.head('http://httpbin.org')
        k = await asks.post('https://webservice.net:25000')
        s = await asks.put('www.your-coat-on.net') # <- no scheme! Will fail!
        # etc.
        r = await asks.request('GET', 'http://httpbin.org/get')

A scheme *must* be supplied. Port can be set by providing it in the URI.

All functions / methods share the same set of args / keyword args, though not all are appropriate for every HTTP method.


Passing Queries
_______________

The ``params`` and ``data`` args take a dictionary and convert it in to a query string to be appended to to URL, or sent in the request body, respectively. ::

    async def example():
        r = await asks.get('www.example.com', params={'Elmo': 'wants data'})

    # sends as request path:
    b'?Elmo=wants+data'

    async def example():
        r = await asks.get('www.example.com', data={'Elmo': 'wants data'})

    # sends in request body:
    b'Elmo=wants+data'

You may also pass strings, ``asks`` will attempt to format them correctly. ::

    async def example():
        r = await asks.post('www.example.com', params='Elmo wants data')

    # sends as request path:
    b'?Elmo%20wants%20data'

    async def example():
        r = await asks.post('www.example.com', data='Elmo wants data')

    # sends in request body:
    b'Elmo wants data'

*Note: the* ``data`` *arg is incompatible with the* ``json``, ``multipart`` *and* ``files`` *args.*


Custom Headers
______________

Add your own custom headers or overwrite the default headers by supplying your own dict to the ``headers`` argument. Note that user headers set in this way will, if conflicting, take precedence. ::

    async def example():
        r = await asks.get('www.example.com',
                           headers={'Custom-Header': 'My value'})


Sending JSON
____________

Pass Python ``dict`` objects to the ``json`` argument to send them as JSON in your request.
Note that if your workflow here involves opening a JSON file, you should use ``curio``'s ``aopen()`` or ``trio``'s ``open_file()`` to avoid stalling the program on disk reads. ::

    dict_to_send = {'Data_1': 'Important thing',
                    'Data_2': 'Really important thing'}

    async def example():
        r = await asks.post('www.example.com', json=dict_to_send)

*Note: the* ``json`` *arg is incompatible with the* ``data``, ``multipart`` *and* ``files`` *args.*


Sending Files (multipart/form-data)
___________________________________

Pass a ``dict`` in the form ``{field: value}`` (as many as you like) to the ``multipart`` argument to
send a ``multipart/form-data`` request.

To send files, send one of the following as ``value``:

    - A ``pathlib.Path`` object: ``asks`` will asyncronously open and read the file.
    - An already open binary file-like object. The ``read()`` method can be a normal function or a coroutine (remember a normal file may block!). You can use ``anyio.aopen`` to get an async file object.
    - An ``asks.multipart.MultipartData`` object, which can be used to override the filename or the mime-type of the sent file.

Other values are converted to strings and sent directly. ::

    async def send_file():
        r = await asks.post('http://httpbin.org/post',
                            multipart={'file_1': Path('my_file.txt')})
        pprint(r.json())

    # if we wanted to send both an already open file and some random data:
    from anyio import aopen

    async def send_file_and_data():
        async with await aopen('my_file.txt', 'rb') as my_file:
            r = await asks.post('http://httpbin.org/post',
                                multipart={'file_1': my_file,
                                           'some_data': 'I am multipart hear me roar',
                                           'some_integer': 3})

    # if we wanted to send some bytes as a file:
    from asks.multipart import MultipartData

    async def send_bytes():
        r = await asks.post('http://httpbin.org/post',
                            multipart={'file_1':
                                MultipartData(b'some text',
                                              mime_type='text/plain',
                                              basename='my_file.txt')})
        pprint(r.json())

    # if we wanted to override metadata:

    async def send_customized_file():
        r = await asks.post('http://httpbin.org/post',
                            multipart={'file_1':
                                MultipartData(Path('my_file.txt'),
                                              mime_type='text/plain',
                                              basename='some_other_name.txt')})
        pprint(r.json())

*Note: the* ``multipart`` *arg is incompatible with the* ``data``, ``json`` *and* ``files`` *args.*

There is also the older ``files`` API, but ``multipart`` should be preferred over it. To use it, pass a ``dict`` in the form ``{filename: filepath}`` (as many as you like) and ``asks`` will asyncronously get the file data, building a multipart-formatted HTTP body. You can also pass non-file paths if you wish to send arbitrary multipart body data sections. ::

    async def send_file():
        r = await asks.post('http://httpbin.org/post',
                            files={'file_1': 'my_file.txt'})

    # if we wanted to send both a file and some random data:
    async def send_file_and_data():
        r = await asks.post('http://httpbin.org/post',
                            files={'file_1': 'my_file.txt',
                                   'some_data': 'I am multipart hear me roar'})

*Note: the* ``files`` *arg is incompatible with the* ``data``, ``json`` *and* ``multipart`` *args.*


Sending Cookies
_______________

Pass a ``dict`` of cookie name(key) / value pairs to the ``cookies`` arg to ship 'em off. ::

    async def example():
        r = await asks.get('www.example.com',
                           cookies={'Cookie Monster': 'Yum'})


Cookie Interactions
___________________

By default ``asks`` does not return sent cookies. To enable two-way cookie interactions, just pass ``persist_cookies=True``. ::

    async def example():
        r = await asks.get('www.example.com', persist_cookies=True)


Set Encoding
____________

The default encoding is ``utf-8``. You may override this by supplying a different encoding, be it a standard encoding or a custom one you've registered locally. ::

    async def example():
        r = await asks.get('www.example.com', encoding='Latin-1')

Handy list of builtin encodings: https://gist.github.com/theelous3/7d6a3fe20a21966b809468fa336195e3


Limiting Redirects
__________________

You can limit the number of redirects by setting ``max_redirects``. By default, the number of redirects is ``20``. ``asks`` will not redirect on HEAD requests. ::

    async def example():
        r = await asks.get('www.httpbin.org/redirect/3', max_redirects=2)


Preventing Redirects
____________________

You can prevent ``asks`` from automatically following redirects by setting ``follow_redirects`` to ``False``. By default, ``asks`` will automatically follow redirects until a non-redirect response or ``max_redirects`` are encountered. ::

    async def example():
        r = await asks.get('www.httpbin.org/redirect/3', follow_redirects=False)

Set Timeout(s)
______________

Don't want to wait forever? Me neither. You may set a timeout with the ``timeout`` arg. This limits the time allotted for the request. ::

    async def example():
        r = await asks.get('www.httpbin.org/redirect/3', timeout=1)

Note that the ``timeout`` arg does not account for the time required to actually establish the connection. That is controlled by a second timeout, the ``connection_timeout``, which defaults to 60 seconds. It's used in the exact same way as ``timeout``. For reasoning, read `this <https://github.com/theelous3/asks/issues/64#issuecomment-392378388>`_.

There is a third timeout available for ``StreamResponse.body`` iteration. See `The Response Object <https://asks.readthedocs.io/en/latest/the-response-object.html>`_


Retry limiting
_______________

You can set a maximum number of retries with ``retries``. This defaults to ``1``, to catch sockets that die in the connection pool, or generally misbehave. There is no upper limit. Be careful :D ::

    async def example():
        r = await asks.get('www.beat_dead_horses.org/neverworks', retries=9999999)


Authing
_______

Available off the bat, we have HTTP basic auth and HTTP digest auth.

To add auth in asks, you pass a tuple of ``('username', 'password')`` to the ``__init__`` of an auth class. For example::

    import asks
    from asks import BasicAuth, DigestAuth

    usr_pw = ('AzureDiamond', 'hunter2')

    async def main():
        r = await asks.get('https://some_protected.resource',
                           auth=BasicAuth(usr_pw))
        r2 = await asks.get('https://other_protected.thingy',
                           auth=DigestAuth(usr_pw),
                           auth_off_domain=True)

**Note**: ``asks`` will not pass auth along to connections that switch from HTTP to HTTPS, or off domain locations, unless you pass ``auth_off_domain=True`` to the call.


Streaming response data
_______________________

You can stream the body of a response by setting ``stream=True`` , and iterating the response object's ``.body`` . An example of downloading a file: ::

    import asks
    import curio
    asks.init('curio')

    async def main():
        r = await asks.get('http://httpbin.org/image/png', stream=True)
        async with curio.aopen('our_image.png', 'ab') as out_file:
            async for bytechunk in r.body:
                out_file.write(bytechunk)

    curio.run(main())


It is important to note that if you do not iterate the ``.body`` to completion, bad things may happen as the connection sits there and isn't returned to the connection pool.
You can get around this by context-managering the ``.body`` if there is a chance you might not iterate fully. ::

    import asks
    import curio
    asks.init('curio')

    async def main():
        r = await asks.get('http://httpbin.com/image/png', stream=True)
        async with curio.aopen('our_image.png', 'wb') as out_file:
            async with r.body: # Bam! Safe!
                async for bytechunk in r.body:
                    await out_file.write(bytechunk)

    curio.run(main())

This way, once you leave the ``async with`` block, ``asks`` will automatically ensure the underlying socket is handled properly. You may also call ``.body.close()`` to manually close the stream.

The streaming body can also be used for streaming feeds and stuff of twitter and the like.

For some examples of how to use this, `look here <https://asks.readthedocs.io/en/latest/idioms.html#handling-response-body-content-downloads-etc>`_


Callbacks
_________

Similar enough to streaming as seen above, but happens during the processing of the response body, before the response object is returned. Overall probably worse to use than streaming in every case but I'm sure someone will find a use for it.

The ``callback`` argument lets you pass a function as a callback that will be run on each bytechunk of response body *as the request is being processed*.

For some examples of how to use this, `look here <https://asks.readthedocs.io/en/latest/idioms.html#handling-response-body-content-downloads-etc>`_
