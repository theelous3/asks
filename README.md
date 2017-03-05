[![Build Status](https://travis-ci.org/theelous3/asks.svg?branch=master)](https://travis-ci.org/theelous3/asks)
# asks
asks is an async requests-like http lib, currently for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) async lib.

asks aims to have a mostly familiar API, using simple functions like `get()` for getting, `post()` for posting. At the heart of asks is the `Session` class, which makes interacting with servers in a sustained and fluid way fast, efficient, and simple. Check out the examples!

The poject's long term goal is to be event loop agnostic, meaning it could be used in any async "framework", be it asyncio, curio<sup>*</sup> or others.

*Requires:* Python 3.6 and [curio](https://github.com/dabeaz/curio).

<sup>Not a framework :)</sup>

## Contents
1. [Installation.](https://github.com/theelous3/asks#installation)
2. [Making requests.](https://github.com/theelous3/asks#making-requests)
3. [Using a Session.](https://github.com/theelous3/asks#using-a-session)
4. [The Response](https://github.com/theelous3/asks#response-content)

## Installation

`pip install git+https://github.com/theelous3/asks.git`

## Making requests

### Example usage

```python
# one request
import asks
import curio

async def example():
    # A little silly to async one request, but not without its use.
    r = await asks.get('http://httpbin.org')
    print(r.content)

curio.run(example())
```
```python
# many requests
from asks import get
import curio

results = []

# For each url, we want to spawn one of these to do do some work.
async def get_tasker(url):
    r = await get(url)
    results.append(r)

async def main(url_list):
    for url in url_list:
        # Spawn a curio task for each url.
        await curio.spawn(get_tasker(url))

curio.run(main(url_list))
```

### General Methods

asks supports `get()`, `post()`, `put()`, `delete()` and `options()` http methods in both http & https.

Every function requires a uri/l. For example:

- `'https://httpbin.org/get'`
- `'http://localhost:25000'`

If a scheme is not supplied, asks will default to https.

All functions share the same set of args and keyword args, though they are not all appropriate for every http method.

### Passing Parameters in a url and / or in the Request Body
```python
async def example():
    r = await asks.get('www.example.com', params={'Elmo': 'wants data'}))

# sends as request path:
b'/?Elmo=wants+data'
```

The `params` and `data` args take a dictionary and convert it in to a valid query string to be appended to to url, or sent in the request body, respectively. You may also pass strings and asks will attempt to format them correctly:

```python
async def example():
    r = await asks.get('www.example.com', params='Elmo wants data'))

# sends as request path:
b'/?Elmo+wants+data'
```

### Custom Headers
```python
async def example():
    r = await asks.get('www.example.com', headers={'Custom-Header': 'My value'}))
```

You may add your own custom headers or overwrite the default headers by supplying your own dict to the `headers` argument. Note that headers set in this way will, if conflicting, take precedence.

### Sending Files (multipart)
```python

files_to_send = {'Some file': 'path/to/file.txt',
                 'Some other file': 'path/to/file_2.txt'}

async def example():
    r = await asks.post('www.example.com', files=files_to_send))
```

Sending files is straight forward. Just pass a dict with file paths as values. asks uses an async wrapper around the files for opening them, so you don't have to worry about your program grinding to a halt on file reads.

### Sending JSON
```python

dict_to_send = {'Data_1': 'Important thing',
                'Data_2': 'Really important thing'}

async def example():
    r = await asks.post('www.example.com', json=dict_to_send))
```

Pass python dict objects to the `json` argument to send them as json in your request.

### Sending Cookies
```python

async def example():
    r = await asks.get('www.example.com', cookies={'Cookie Monster': 'Is huuungry!'}))
```

Pass a dict of cookie name(key) / value pairs to the `cookies` arg to ship 'em off.

### Encoding
```python

async def example():
    r = await asks.get('www.example.com', encoding='Latin-1'))
```

Asks defaults to `utf-8` encoding. You may override this by supplying a different encoding, be it
a standard encoding or a custom one you've registered locally.

### Set Max Redirects
```python

async def example():
    r = await asks.get('www.httpbin.org/redirect/3', max_redirects=2))
```

 You may limit the number of redirects by setting `max_redirects`. By default, the number of redirects is unlimited. asks will not redirect on HEAD requests.

### Set Timeout
```python

async def example():
    r = await asks.get('www.httpbin.org/redirect/3', timeout=1))
```

You may set a timeout with the `timeout` arg. This limits the time asks will wait between when the request is first sent, and the first piece of response data is received.

## Using a Session

By default asks is stateless, in that it's a httplib and it doen't return cookies to the server unless explicitly told to. To solve this, we have sessions!

The primary use of sessions really, is to make life easier by suppling a host and master endpoint when you instance the session, allowing for a convenient way to throw paramaters and such at an API.

## Example usage

```python
# Without cookies, for bashing away at an API
import asks
from asks.sessions import Session
import curio

param_dict = {'Dict': 'full of params'}

async def worker(session, param):
    r = await session.get(params=param)
    print(r.text)

async def main(things_to_get):
    s = await Session('www.some-web-api.com', endpoint='/api')
    for k, v in things_to_get.items():
        await curio.spawn(worker(s, {k: v}))

curio.run(main(param_dict))
```

```python
# With cookies. Setting endpoint using attribute and supplying a path
# to the method with the path argument. Also adding custom max connections.
import asks
from asks.sessions import Session
import curio

params_test = {'A very large dict': 'of params'}

async def worker(session, item):
    r = await session.get(path='/api', params=item)
    print(r.text)

async def main(stuff_to_send):
    s = await Session(
        'https://api-stuff.net', store_cookies=True, connections=10)
    s.endpoint = '/example'

    for k, v in stuff_to_send.items():
        await curio.spawn(worker(s, {k: v}))

curio.run(main(params_test))
```

Cookie storage must be set explicitly on instantiation, setting the master endpoint attrib can be done on the fly, additional paths can be supplied in the same fashion and all of the methods remain the same as the basic usage seen above.

### Connection pooling
asks uses connection pooling to speed up repeat requests to the same location. We default to a very friendly `1` pooled connection, meaning that we limit ourselves for the sake of not being blocked by the server we're interacting with.

You can modify the number of pooled connections with the `connections` keyword arg on `Session` instantiation. The connections are created when you instance the `Session`, requiring that instantiation be `await`ed. Example:

```python
async def example():
    s = await Session('http://some.url', connections=100)
```

asks is capable of dishing out quite a few requests quite rapidly, over many connections. It's good to be polite to the server you're interacting with! Limit your application appropriately :)

#### The Session class

**asks.sessions.Session**(_**host**, **port**=443, **endpoint**=None, **encoding**='utf-8', **store_cookies**=None, **connections**=1_)

#### Session \_\_init\_\_ arguments

* **_host_** must be a top-level address. Either an IP or a url. For example 'https://example.com'.

* **_port_** must be of type int.

* **_endpoint_** must be a url path. Examples: '/api' or '/some_api/endpoint'

* **_encoding_** can be any valid encoding string, builtin or custom. [Builtins](https://gist.github.com/theelous3/7d6a3fe20a21966b809468fa336195e3).

* **_store_cookies_** set to bool value `True` to use stateful cookies.

* **_connections_** must be of type int. The upper limit to this value is OS specific, but suffice to say you can make it very large. A larger value does not necessarily give a direct increase in overall performance. Find the balance! If you're making 100 requests and use 100 connections, you will seriously degrade the up front performance of your program.

#### Session attributes

* **_endpoint_** same as in __init__. Can be set at any time to change where your requests go.

* **_encoding_** same deal here.

* **_host_** same again.

* **_port_** you get the picture.

* **_connection_pool_** can be queried if you want to check the current usage of the connection pool. The pool is a collections.deque object.

## The Response

### Headers, Status Line, and Errors
```python

async def example():
    r = await asks.get('www.httpbin.org/get'))
    print(r.status_code,
          r.reason_phrase,
          r.http_version,
          r.headers,
          r.errors)
```

The response headers, status line parts, and errors can be accessed as attributes of the response object.

### Raw response
```python

async def example():
    r = await asks.get('www.httpbin.org/get'))
    print(r.raw)
```

The response body as received can be accessed with the .raw property.

### Response Content
```python

async def example():
    r = await asks.get('www.httpbin.org/gzip'))
    print(r.content)
```

The decompressed (if any compression) response body can be accessed with the .content property.

### Response Text
```python

async def example():
    r = await asks.get('www.httpbin.org/deflate'))
    print(r.text)
```

The decompressed (if any compression) and decoded response body can be accessed with the .text property.

### Encoding
```python

async def example():
    r = await asks.get('www.httpbin.org/get'))
    print(r.encoding='Latin-1')
```

You may set your own encoding, be it standard or custom, using the response `.encoding()` method.

An attempt to guess the encoding is made by asks if the correct header is supplied in the response. Defaults to `utf-8`.

### JSON
```python

async def example():
    r = await asks.get('www.httpbin.org/get'))
    j = r.json()
```
If the response body is valid JSON, you may grab it using the response `.json()` method.

### History
```python

async def example():
    r = await asks.get('www.httpbin.org/redirect/1'))
    print(r.history,
          r.history[0])
```

If there were redirects, you may access a list of the intermediary response objects through the .history attribute.

### Cookies
```python

async def example():
    r = await asks.get('www.httpbin.org/cookies/set?cookie=jar'))
    print(r.cookies,
          r.history[0].cookies)
```

You may access the cookies from a response object by using the `.cookies` attribute to return a list of cookie objects.

#### Note: You may use any of these methods, properties or attributes on any response object in the response history.

## TO DO:
- Auth
- ???
- Non-profit

### Holla holla to ##lp, and 8banana
