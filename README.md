# asks
asks is an async requests-like http lib, currently for use in conjunction with the wonderful [cuio](https://github.com/dabeaz/curio) async lib. It's currently in its infancy supporting http only, and tied to curio. 
The poject's next goal is https support, and long term goal is to be event loop agnostic, meaning it could be used in any async 
"framework", be it asyncio, curio<sup>*</sup> or others.

asks aims to have a mostly familiar API, using simple functions like get() for getting, post() for posting.

<sup>Not a framework :)</sup>

## Example usage

```python
# one request
import asks
import curio

def example():
    r = await asks.get('http://httpbin.org')
    print(r.content)

curio.run(blah())
```
```python
# many requests
from asks import get
import curio

results = []

async def get_tasker(url):
    r = await get(url)
    results.append(r)

async def main(url_list):
    for url in url_list:
        await curio.spawn(example(url))

curio.run(main(url_list))
```

## Accessing response info and other stuff

For now, just presume everything works as it does in requests. I'll polish this section off shortly :)