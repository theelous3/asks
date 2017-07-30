# pylint: disable=wildcard-import



_async_lib_name = None

# this is kind of awful but not exposed as a part of the public API
# we need this because anything in asks might be imported before init()
# is called


class _AsyncLib:

    # when _async_lib.something is requested, _async_lib.__dict__['something']
    # is checked before _async_lib.__getattr__('something')
    def __getattr__(self, attr):
        # the __dict__ is empty when a new instance has just been created
        if not self.__dict__:
            raise RuntimeError("asks.init() wasn't called")

_async_lib = _AsyncLib()


def init(lib_name):
    # TODO: add more error handling and checks
    if lib_name == 'curio':
        from curio import (aopen,
                           open_connection,
                           spawn,
                           sleep,
                           BoundedSemaphore,
                           TaskTimeout,
                           timeout_after)
        _async_lib.aopen = aopen
        _async_lib.open_connection = open_connection
        _async_lib.spawn = spawn
        _async_lib.sleep = sleep
        _async_lib.BoundedSemaphore = BoundedSemaphore
        _async_lib.TaskTimeout = TaskTimeout
        _async_lib.timeout_after = timeout_after
    elif lib_name == 'trio':
        pass


from .base_funcs import *
from .sessions import *
from .auth import *
