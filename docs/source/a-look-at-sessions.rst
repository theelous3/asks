asks - A Look at Sessions
=========================

While something like requests makes grabbing a single request very simple (and asks does too!); the ``Session`` in asks aim to make getting a great many things simple as well.

asks' ``Session`` methods are the same as the base asks functions, supporting ``.get()``, ``.head()``, ``.post()``, ``.put()``, ``.delete()``, ``.options()`` and ``.request()``.

For more info on how to use these methods, take a `look-see <https://asks.readthedocs.io/en/latest/overview-of-funcs-and-args.html>`_.

The asks ``Session`` has all of the features you would expect, and some extra that make working with web APIs a little nicer.


``Session`` creation
____________________

To create a regular old session and start flinging requests down the pipe, do just that: ::

    from asks import Session

    async def main():
        s = Session()
        r = await s.get('https://example.org')

Well. That wasn't very exciting. Next, let's make a whole pile of requests, and modify the ``connections`` parameter.


!Important! Connection (un)limiting
___________________________________

The ``Session``'s ``connections`` argument dictates the maximum number of concurrent connections asks will be allowed to make at any point during the ``Sessions`` lifespan. You *will* want to change the number of connections to a value that suits your needs and the server's limitations. If no data is publicly available to guide you here, air on the low side.

**The default number of connections in the pool for a Session is a measly ONE.** If I arbitrarily picked a number greater than one it would be too high for 49% of people and too low for the other 49%. ::

    import asks
    import curio
    asks.init('curio')

    a_list_of_many_urls = ['wow', 'so', 'many', 'urls']

    async def worker(s, url):
        r = await s.get(url)
        print(r.text)

    async def main(url_list):
        s = asks.Session(connections=20)
        for url in url_list:
            await curio.spawn(worker(s, url))

    curio.run(main(a_list_of_many_urls))


Session Headers
_______________

You can provide session wide headers to your requests with the ``headers`` kwargument on ``Session`` instantiation, or by manually modifying the ``.headers`` attribute of your session. ::

    from asks import Session

    async def main():
        s = Session('https://example.com', headers={'Applies-to': 'all requests'})
        s.headers.update({'also-applies-to': 'all requests'})

If you send headers with a http method's ``headers`` kwargument, it will take precedence. For example, in the above example; doing ``s.get(headers={'Applies-to': 'this request only'})`` will overwrite the session wide header ``'Applies-to'`` for that single request.

Persistent Cookies
__________________

HTTP is stateless, and by default asks is too. You can turn stateful cookie returning on by supplying the ``persist_cookies=True`` kwarg on session instanciation. ::

    from asks import Session

    async def main():
        s = Session('https://example.com', persist_cookies=True)


An alternate approach to web APIs
_________________________________

Often you'll want to programatically make many quite similar calls to a webservice. Worrying about constructing and reconstructing urls can be a pain, so asks has support for a different approach.

``Session`` 's have a ``base_location`` and ``endpoint`` attribute which can be programatically set, and augmented using a http method's ``path`` parameter.

In the next example, we’ll make 1k calls over fifty connections to http://echo.jsontest.com. We’ll do much of the same as above, except we’ll set a base location of ``http://echo.jsontest.com`` an ``endpoint`` of ``/asks/test`` and in each request pass a number as a ``path``, like ``/1``.

The result will be a bunch of calls that look like

* ``http://echo.jsontest.com/asks/test/1``
* ``http://echo.jsontest.com/asks/test/2``
* ``http://echo.jsontest.com/asks/test/etc.``


Please don't actually do this or the jsontest.com website will be very unhappy. ::

    import asks
    import curio
    asks.init('curio')

    async def worker(s, num):
        r = await s.get(path='/' + str(num))
        print(r.text)

    async def main():
        s = asks.Session(connections=50)
        s.base_location = 'http://echo.jsontest.com'
        s.endpoint = '/asks/test'
        for i in range(1, 1001):
            await curio.spawn(worker(s, i))

    curio.run(main())

You may override the ``base_location`` and ``endpoint`` by passing a url normally.
