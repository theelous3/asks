asks - A Look at Sessions
=========================

While something like requests makes grabbing a single request very simple (and asks does too!); the sessions in asks aim to make getting a great many things simple as well.

asks' sessions' methods are the same as the base asks functions, supporting ``.get()``, ``.head()``, ``.post()``, ``.put()``, ``.delete()``, ``.options()`` and ``.request()``.

For more info on how to use these methods, take a `look-see <https://asks.readthedocs.io/en/latest/overview-of-funcs-and-args.html>`_.

**There are two kinds of session in asks.** The disparate session (``DSession``) and the homogeneous session(``HSession``).

The ``DSession`` class is aimed at working with many requests, to many hosts! Webscraping and such is an excellent use for this. This is like requests' ``Session`` and should be familiar to use.

The ``HSession`` class is aimed at working with many requests to a single host. Dealing with an API is a great example of this and you'll see more on that below.


HSession
________


The only required argument to HSession's ``__init__`` is a top level host name, like ``https://example.org`` . ::

    from asks import HSession

    async def main():
        s = HSession('https://example.org')
        r = await s.get()

As you can see, unlike requests' ``Session`` and asks ``DSession`` , we don't *need* to give any arguments at all to a ``HSession`` 's' ``get()`` method. Pretty weird right?

This means we can do things like set an endpoint, and just feed querys in to our ``.get()`` though the ``params`` arg without rebuilding the path for the request each time.

In the next example, we'll make ten thousand calls over fifty connections to http://echo.jsontest.com. We'll do much of the same as above, except we'll set an endpoint of ``/asks/test`` and in each request pass a number as a path, like ``/1``.

The result will be a bunch of calls that look like

* ``http://echo.jsontest.com/asks/test/1``
* ``http://echo.jsontest.com/asks/test/2``
* ``http://echo.jsontest.com/asks/test/etc.``

Please don't actually do this or the jsontest.com website will be very unhappy. ::

    from asks import HSession
    import curio

    async def worker(num):
        r = await s.get(path='/' + str(num))
        print(r.text)

    async def main():
        s.endpoint = '/asks/test'
        for i in range(1, 10001):
            await curio.spawn(worker(i))

    s = HSession('http://echo.jsontest.com', connections=50)
    curio.run(main())


**The default number of connections in the pool for a HSession is a measly ONE.** If I arbitrarily picked a number greater than one it would be too high for 49% of people and too low for the other 49%.

The ``connections`` argument dictates the maximum number of concurrent connections asks will be allowed to make at any point of the ``HSessions`` lifespan. You *will* want to change the number of connections to a value that suits your needs and the server's limitations. If no data is publicly available to guide you here, air of the low side.

Now whilst we have all of this sweet sweet async speed, we must talk about our great great responsibility. asks is fast, and hammering the bejaysus out of a webservice shared by many people is **selfish**. Don't be that guy / gal. Rate limit yourself by placing ``curio.sleep(n)``'s in appropriate the place(s), or utilising curio's semaphores / taskgroups / queues etc.

DSession
________

The main difference between the ``DSession`` and the ``HSession`` is that you must supply a url to the ``DSession`` methods much like you would to a requests' ``Session``. Aside from that, the same stuff applies. You can add ``params`` , ``persist_cookies=True`` and do all of that other good stuff that you can do with the ``HSession`` class and methods. ::

    from asks import Session
    import curio

    url_list = ['a', 'bunch', 'of', 'random', 'urls']

    async def worker(url):
        r = await s.get(url)
        print(r.text)

    async def main():
        for url in url_list:
            await curio.spawn(worker(url))

    s = Session(connections=20)
    curio.run(main())

The default number of connections in the ``Session`` pool is ``20``.


Stateful Sessions
_________________

HTTP is stateless, and by default asks is too. You can turn stateful cookie returning on by supplying the ``persist_cookies=True`` kwarg on session instanciation. ::

    from asks import HSession

    async def main():
        s = HSession('https://example.com', persist_cookies=True)
        r = await s.get()


