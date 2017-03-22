asks - A Look at Sessions
=========================

While something like requests makes grabbing a single request very simple (and asks does too!); the sessions in asks aim to make getting a great many things simple as well.

asks' sessions' methods are the same as the base asks functions, supporting ``get()``, ``head()``, ``post()``, ``put()``, ``delete()`` and ``options()``.

For more info on how to use these methods, take a `look-see <https://asks.readthedocs.io/en/latest/overview-of-funcs-and-args.html>`_.

**There are two kinds of session in asks. The** ``Session`` **and the disparate session(** ``DSession`` **).**

The ``Session`` class is aimed at working with many requests to a single host. Dealing with an API is a great example of this.

The ``DSession`` class is aimed at working with many requests, to many hosts! Webscraping and such is an excellent use for this.

The reason for two classes, is that they each have their own streamlined connection pooling, and the ``Session`` methods do not require a url or path to facilitate many similar / slightly different calls.


Creating a Session
__________________

(Specifically a ``Session`` and not a ``DSession``)

The asks ``Session`` class builds a connection pool on instanciation. This means it must be ``await`` ed, and as with all ``awaits`` it must be in an ``async def``.

The only required argument to the session's ``__init__`` is a top level host name, like ``https://example.org`` .::

    from asks import Session

    async def main():
        s = await Session('https://jsontest.com')
        r = await s.get()

As you can see, unlike requests' session, we don't need to give any arguments at all to a sessions ``get()`` method. Pretty weird right? But, very convenient.


Many Connections and Connection Pooling
_______________________________________

In the next example, we'll make ten thousand calls over fifty connections to http://echo.jsontest.com. We'll do much of the same as above, except we'll define an endpoint of ``/asks/test`` and in each request pass a number as a path, like ``/1``.

The result will be a bunch of calls that look like

* ``http://echo.jsontest.com/asks/test/1``
* ``http://echo.jsontest.com/asks/test/2``
* ``http://echo.jsontest.com/asks/test/etc.``

Note that actually doing this will probably get you timed out or banned by that website.::

    from asks import Session
    import curio

    async def worker(session, num):
        r = await session.get(path='/' + str(num))
        print(r.text)

    async def main():
        s = await Session('http://echo.jsontest.com', connections=50)
        s.endpoint = '/asks/test'
        for i in range(1, 10001):
            await curio.spawn(worker(s, i))

    curio.run(main())

**The default number of connections in the pool is a measly ONE.** If I arbitrarily picked a number greater than one it would be too high for 49% of people and too low for the other 49%.
You *will* want to change the number of connections to a value that suits you and your target server.

Now whilst we have all of this sweet sweet async speed, we must talk about our great great responsibility. asks is fast, and hammering the bejaysus out of a webservice shared by many people is **selfish**. Don't be that guy / gal. Rate limit yourself by placing ``curio.sleep(n)``'s in appropriate the place(s).


Stateful Sessions
_________________

HTTP is stateless, and by default asks is too. You can turn stateful cookie returning and storage on by supplying the ``store_cookies=True`` kwarg on session instanciation.::

    from asks import Session

    async def main():
        s = await Session('https://jsontest.com', store_cookies=True)
        r = await s.get()

Creating a DSession
___________________

The ``DSession`` does not have to be ``await`` ed, as it unfortunately cannot see in to the future...yet. (we can't prepare the connection pool right away as we don't know where we're connecting yet!)::

    from asks import DSession
    import curio

    url_list = ['a', 'bunch', 'of', 'random', 'urls']

    async def worker(url):
        r = await s.get(url)
        print(r.text)

    async def main():
        for url in url_list:
            await curio.spawn(worker(url))

    s = DSession(connections=20)
    curio.run(main())

The main difference between the ``DSession`` and the ``Session`` is that you must supply a url to the ``DSession`` methods. Aside from that, the usual stuff applies. You can add ``params`` , ``store_cookies=True`` and do all of that other good stuff that you can do with the ``Session`` class and base functions.
