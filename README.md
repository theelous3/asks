# asks
asks is an async requests-like http lib, currently for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) async lib. The poject's long term goal is to be event loop agnostic, meaning it could be used in any async "framework", be it asyncio, curio<sup>*</sup> or others.

asks aims to have a mostly familiar API, using simple functions like `get()` for getting, `post()` for posting.

<sup>Not a framework :)</sup>

## Contents

1. [Making requests.](https://github.com/theelous3/asks#making-requests)
2. [Using a Session.](https://github.com/theelous3/asks#using-a-session)

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
from asks import Session
import curio

param_dict = {'Dict': 'full of params'}

s = Session('www.some-web-api.com', endpoint='/api')

async def worker(param):
    r = await s.get(params=param)
    print(r.text)

async def main(things_to_get):
    for k, v in things_to_get.items():
        await curio.spawn(worker({k: v}))

curio.run(main(param_dict))
```

```python
# With cookies. Setting endpoint using attribute and supplying a path
# to the method with the path argument.
import asks
from asks import Session
import curio

cookies_to_set = {'cookie1': 'value1',
                  'cookie2': 'value2',
                  'cookie3': 'value3'}

s = Session('http://httpbin.org', store_cookies=True)

async def worker(cookie):
    r = await s.get(path='/set', params=cookie)
    print(r.text)

async def main(cookie_stuff):
    s.endpoint = '/cookies'
    for k, v in cookie_stuff.items():
        await curio.spawn(worker({k: v}))

curio.run(main(cookies_to_set))
```

That's pretty much all there is to it. Cookie storage must be set explicitly on instanciation, setting the master endpoint can be done on the fly, additional paths can
be supplied in the same fashion and all of the methods remain the same as the basic usage seen above.

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
- Path to json for async .json file opens
- Auth
- Resend recvd cookies
- ???
- Non-profit

### Holla holla to ##lp, and 8banana