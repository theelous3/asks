asks - Useful idioms and tricks.
================================


Maintaining Order
_________________

Due to the nature of async, if you feed a list of urls to asks in some fashion, and store the responses in a list, there is no gaurantee the responses will be in the same order as the list of urls.

A handy way of dealing with this on an example ``url_list`` is to pass the enumerated list as a dict ``dict(enumerate(url_list))`` and then create a sorted list from a response dict. This sounds more confusing in writing than it is in code. Take a look: ::

    import asks
    import curio

    results = {}

    url_list = ['a', 'big', 'list', 'of', 'urls']

    async def worker(key, url):
        r = await s.get(url)
        results[key] = r

    async def main(url_list):
        url_dict = dict(enumerate(url_list))
        for key, url in url_dict.items():
            await curio.spawn(worker(key, url))

    sorted_results = [response for _, response in sorted(results.items()]

    s = asks.DSession(connections=10)
    curio.run(main(url_list))

In the above example, ``sorted_results`` is a list of response objects in the same order as ``url_list``.


Handling response body content (downloads etc.)
___________________________________________________________

The recommended way to handle this sort of thing, is by streaming, like so: ::


    import asks
    import curio

    async def main():
        r = await asks.get('http://httpbin.org/image/png', stream=True)
        with open('our_image.png', 'ab') as out_file:
            async for bytechunk in r.body:
                out_file.write(bytechunk)

    curio.run(main())

An example of multiple downloads with streaming: ::

    import asks
    import curio
    from functools import partial

    async def downloader(filename, url):
        r = await asks.get(url, stream=True)
        with open(filename, 'ab') as out_file:
            async for bytechunk in r.body:
                out_file.write(bytechunk)

    async def main():
        for indx, url in enumerate(['http://placehold.it/1000x1000',
                                    'http://httpbin.org/image/png']):
            func = partial(downloader, str(indx) + '.png')
            await curio.spawn(func(url))

    curio.run(main())


The ``callback`` argument lets you pass a function as a callback that will be run on each byte chunk of response body *as the request is being processed* . A simple use case for this is downloading a file.

Below you'll find an example of a single download of an image with a given filename, and multiple downloads with sequential numeric filenames. They are very similar to the streaming examples above.

We define a callback function ``downloader`` that takes bytes and saves 'em, and pass it in. ::

    import asks
    import curio

    async def downloader(bytechunk):
        async with curio.aopen('our_image.png', 'ab') as out_file:
            await out_file.write(bytechunk)

    async def main():
        r = await asks.get('http://httpbin.org/image/png', callback=downloader)

    curio.run(main())

What about downloading a whole bunch of images, and naming them sequentially? ::

    import asks
    import curio
    from functools import partial

    async def downloader(filename, bytechunk):
        async with curio.aopen(filename, 'ab') as out_file:
            await out_file.write(bytechunk)

    async def main():
        for indx, url in enumerate(['http://placehold.it/1000x1000',
                                 'http://httpbin.org/image/png']):
            func = partial(downloader, str(indx) + '.png')
            await curio.spawn(asks.get(url, callback=func))

    curio.run(main())


Resending an asks.Cookie
________________________

Simply refrence the ``Cookie`` 's ``.name`` and ``.value`` attributes as you pass them in to the ``cookies`` argument. ::

    import asks
    import curio

    a_cookie = previous_response_object.cookies[0]

    async def example():
        cookies_to_go = {a_cookie.name: a_cookie.value, 'another': 'cookie'}
        r = await asks.get('http://example.com', cookies=cookies_to_go)

    curio.run(example())
