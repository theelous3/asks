[![Build Status](https://travis-ci.org/theelous3/asks.svg?branch=master)](https://travis-ci.org/theelous3/asks) [![Docs Status](https://readthedocs.org/projects/asks/badge/?version=latest)](http://asks.readthedocs.io/en/latest/)

# asks
asks is an async requests-like http lib, currently for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) async lib.

asks aims to have a mostly familiar API, using simple functions like `get()` for getting, `post()` for posting. At the heart of asks is the `Session` class, which makes interacting with servers in a sustained and fluid way fast, efficient, and simple. Check out the examples!

The poject's long term goal is to be event loop agnostic, meaning it could be used in any async "framework", be it asyncio, curio<sup>*</sup> or others.

*Requires:* Python 3.6 and [curio](https://github.com/dabeaz/curio).

<sup>Not a framework :)</sup>

## Check the docs!

http://asks.readthedocs.io/

Above you'll find detailed docs with a large number of simple examples to help you get off the ground in no time.

## Installation

`pip install git+https://github.com/theelous3/asks.git`

`pip install git+https://github.com/dabeaz/curio.git`

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
```


### Shoutout to ##lp, and the fine peeps of 8banana
