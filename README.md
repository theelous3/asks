[![Build Status](https://travis-ci.org/theelous3/asks.svg?branch=master)](https://travis-ci.org/theelous3/asks) [![Docs Status](https://readthedocs.org/projects/asks/badge/?version=latest)](http://asks.readthedocs.io/en/latest/)


# asks
asks is an async requests-like http lib, for use in conjunction with the wonderful [curio](https://github.com/dabeaz/curio) async lib.

asks aims to have a mostly familiar API, using simple functions like `get()` for getting, `post()` for posting. At the heart of asks is the `Session` class, which makes interacting with servers in a sustained and fluid way fast, efficient, and simple. Check out the examples!


*Requires:* Python 3.6 and [curio](https://github.com/dabeaz/curio).


## Check the docs!

http://asks.readthedocs.io/

Above you'll find detailed docs with a large number of simple examples to help you get off the ground in no time.

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
# many_get.py
# make 1k api calls and store their response objects
# in a list.

from asks import Session
import curio

path_list = ['a', 'list', 'of', '1000', 'paths']

retrieved_responses = []

async def grabber(a_path):
    r = s.get(path=a_path)
    retrieved_responses.append(r)

async def main(path_list):
    for path in path_list:
        curio.spawn(grabber(path))

s = Session('https://some-web-service.com', connections=20)
curio.run(main(path_list))
```


### Shoutout to ##lp, and the fine peeps of 8banana

# TODO

* A million things, probably.
