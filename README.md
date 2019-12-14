[![Build Status](https://travis-ci.org/theelous3/asks.svg?branch=master)](https://travis-ci.org/theelous3/asks) [![Docs Status](https://readthedocs.org/projects/asks/badge/?version=latest)](http://asks.readthedocs.io/en/latest/)


# asks
`asks` is an async `requests`-like HTTP lib, for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) and [trio](https://github.com/python-trio/trio) async libs.

`asks` aims to have a mostly familiar API, using simple functions/methods like `get()` for getting and `post()` for posting.
At the heart of `asks` is a session class which makes interacting with the web in a sustained and fluid way fast, efficient, and simple. Check out the examples!


## Check the docs!

http://asks.readthedocs.io/

Above you'll find detailed docs with a large number of simple examples to help you get off the ground in no time.

## Installation

*Requires: Python 3.5.2 or newer.*

`pip install asks`


## Examples

```python
# one request
# A little silly to async one request, but not without its use!
import asks
import curio

async def example():
    r = await asks.get('https://example.org')
    print(r.content)

curio.run(example())
```

```python
# many requests
# make 1k api calls and store their response objects
# in a list.

import asks
import trio

path_list = ['http://fakeurl.org/get','http://example123.org']

results = []


async def grabber(s, path):
    r = await s.get(path)
    results.append(r)


async def main(path_list):
    from asks.sessions import Session
    s = Session('https://example.org', connections=2)
    async with trio.open_nursery() as n:
        for path in path_list:
            n.start_soon(grabber, s, path)

trio.run(main, path_list)

```

#### Changelog

*2.0.0* - Setting `stream=True` means that the response returned will be a `StreamResponse` object rather than the default `Response` object.

##### Shoutout to ##lp, and the fine peeps of 8banana
