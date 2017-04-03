asks - An overview of the functions and kw/argumetns.
=====================================================

asks is *heavily* influenced by requests, and as such pretty much everything that works in requests works in asks. So, if you're familiar with the format you can pretty much skip to the distinctions regarding `sessions <https://asks.readthedocs.io/en/latest/a-look-at-sessions.html>`_

The examples here use the base one-request-functions for verbosities sake, but all of these functions are completely transferrable to the ``Session`` class as methods.


General HTTP methods
____________________

asks supports ``get()``, ``head()``, ``post()``, ``put()``, ``delete()``, ``options()`` and ``request()``.

``request`` takes a http method as a string for its first argument.

When using the basic functions they each require a uri::

    import asks

    async def blah():
        a = await asks.get('https://example.com')
        s = await asks.head('http://httpbin.org')
        k = await asks.post('https://webservice.net:25000')
        s = await asks.put('www.your-coat-on.net') # <- no scheme! Will fail!
        # etc.
        r = await asks.request('GET', 'http://httpbin.org/get')

A scheme *must* be supplied. Port can be set by providing it in the uri.

All functions / methods share the same set of args / keyword args, though not all are appropriate for every http method.


Passing Queries
_______________

The ``params`` and ``data`` args take a dictionary and convert it in to a valid query string to be appended to to url, or sent in the request body, respectively. ::

    async def example():
        r = await asks.get('www.example.com', params={'Elmo': 'wants data'}))

    # sends as request path:
    b'/?Elmo=wants+data'

You may also pass strings and asks will attempt to format them correctly. ::

    async def example():
        r = await asks.get('www.example.com', data='Elmo wants data'))

    # sends in request body:
    b'/?Elmo+wants+data'


Custom Headers
______________

Add your own custom headers or overwrite the default headers by supplying your own dict to the ``headers`` argument. Note that user headers set in this way will, if conflicting, take precedence. ::

    async def example():
        r = await asks.get('www.example.com',
                           headers={'Custom-Header': 'My value'}))


Sending JSON
____________

Pass python dict objects to the ``json`` argument to send them as json in your request.
Note that if your workflow here involves opening a json file, you should use curio's ``aopen()`` to avoid stalling the program on disk reads. ::

    dict_to_send = {'Data_1': 'Important thing',
                    'Data_2': 'Really important thing'}

    async def example():
        r = await asks.post('www.example.com', json=dict_to_send))


Sending Cookies
_______________

Pass a dict of cookie name(key) / value pairs to the ``cookies`` arg to ship 'em off. ::

    async def example():
        r = await asks.get('www.example.com',
                           cookies={'Cookie Monster': 'Yum'}))


Cookie Interactions
___________________

By default asks does not return sent cookies. To enable two way cookie interactions, just pass ``persist_cookies=True``. ::

    async def example():
        r = await asks.get('www.example.com', persist_cookies=True)


Set Encoding
____________

The default encoding is ``utf-8``. You may override this by supplying a different encoding, be it a standard encoding or a custom one you've registered locally. ::

    async def example():
        r = await asks.get('www.example.com', encoding='Latin-1'))

Handy list of builtin encodings: https://gist.github.com/theelous3/7d6a3fe20a21966b809468fa336195e3


Limiting Redirects
__________________

You can limit the number of redirects by setting ``max_redirects``. By default, the number of redirects is unlimited. asks will not redirect on HEAD requests. ::

    async def example():
        r = await asks.get('www.httpbin.org/redirect/3', max_redirects=2))



Set Timeout
___________

Don't want to wait forever? Me neither. You may set a timeout with the timeout arg. This limits the total time alotted for the request. ::

    async def example():
        r = await asks.get('www.httpbin.org/redirect/3', timeout=1))


Authing
_______

Available off the bat, we have http basic auth and http digest auth. These are both crappy and next on the agenda is adding support for good auth.

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

**Note**: asks will not pass auth along to connections that switch from http to https, or off domain locations, unless you pass ``auth_off_domain=True`` to the call.


Callbacks
_________

The ``callback`` argument lets you pass a function as a callback that will be run on each byte chunk of response body. A simple use case for this is downloading a file.

For some examples of how to use this, `look here <https://asks.readthedocs.io/en/latest/idioms.html#callbacks-handling-response-body-content-downloads-etc>`_
