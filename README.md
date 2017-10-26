[![Build Status](https://travis-ci.org/theelous3/asks.svg?branch=master)](https://travis-ci.org/theelous3/asks) [![Docs Status](https://readthedocs.org/projects/asks/badge/?version=latest)](http://asks.readthedocs.io/en/latest/)


# asks
asks is an async requests-like http lib, for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) and [trio](https://github.com/python-trio/trio) async libs.

asks aims to have a mostly familiar API, using simple functions/methods like `get()` for getting, `post()` for posting. At the heart of asks is a session class which makes interacting with the web in a sustained and fluid way fast, efficient, and simple. Check out the examples!


## Check the docs!

http://asks.readthedocs.io/

Above you'll find detailed docs with a large number of simple examples to help you get off the ground in no time.

## Installation

*Requires: Python 3.5.2 or newer.*

`pip install asks`

Note: Currently supports trio's development branch. You can install this by doing `pip install git+https://github.com/python-trio/trio.git`


## Examples

```python
# one request
# A little silly to async one request, but not without its use!
import asks
import curio
asks.init('curio')

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
asks.init('trio')

path_list = ['a', 'list', 'of', '1000', 'paths']

results = []

async def grabber(path):
    r = await s.get(path)
    results.append(r)

async def main(path_list):
    async with trio.open_nursery() as n:
        for path in path_list:
            n.spawn(grabber(path))

s = asks.Session()
trio.run(main, path_list)
```


### Shoutout to ##lp, and the fine peeps of 8banana
