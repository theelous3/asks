'''
Alright, you're probably having a heart attack looking at this right now.
Just breathe, and it will be ok, I promise!

asks was initially created just to support curio, until trio came along
with its similar design and approach to async in python. Why not support both?
'''

# pylint: disable=wildcard-import
# pylint: disable=wrong-import-position
import threading


class _AsyncLib(threading.local):
    def __init__(self):
        self.aopen = None
        self.open_connection = None
        self.sleep = None
        self.task_manager = None
        self.TaskTimeout = None
        self.timeout_after = None
        self.sendall = None
        self.recv = None
        super().__init__()

    '''
    When _async_lib.something is requested, _async_lib.__dict__['something']
    is checked before _async_lib.__getattr__('something')
    '''
    def __getattr__(self, attr):
        # the __dict__ is empty when a new instance has just been created
        if not self.__dict__:
            raise RuntimeError("asks.init() wasn't called")


# So, the idea here is that asks, after import, must be told explicitly which
# event loop to use. Upon first import, asks has _AsyncLib which is an empty
# shell. Upon asks' initialisation the instance of _AsyncLib asks uses is
# populated either with functions and classes directly from the chosen async
# lib, or with wrappers around those functions and classes such that they share
# the same API to the extent asks requires.

# This results in a meeting point between the two libraries which asks can use
# arbitrarily. (You can even run a trio event loop, and then run the same
# functions with curio! Not recommended, but hey. It's fun.)

# For the sake of simplicity, where possible, the methods of _AsyncLib use the
# curio name. For example, TaskTimeout from curio rather than TooSlowError from
# trio. This is not indicative of any preference to the libraries themselves;
# it just required fewer changes to asks' internals to implement.

# the instance asks uses internally
_async_lib = _AsyncLib()


def init(lib_name):
    '''
    Must be called at some point after asks import and before your event loop
    is run.

    Populates the _async_lib instance of _AsyncLib with methods relevant to the
    async library you are using.

    Args:
        lib_name (str): Either 'curio' or 'trio'.
    '''
    if lib_name == 'curio':
        import curio
        from ._event_loop_wrappers import (curio_sendall,
                                           curio_recv)
        _async_lib.aopen = curio.aopen
        _async_lib.open_connection = curio.open_connection
        _async_lib.sleep = curio.sleep
        _async_lib.task_manager = curio.TaskGroup
        _async_lib.TaskTimeout = curio.TaskTimeout
        _async_lib.timeout_after = curio.timeout_after
        _async_lib.sendall = curio_sendall
        _async_lib.recv = curio_recv

    elif lib_name == 'trio':
        import trio
        from ._event_loop_wrappers import (trio_open_connection,
                                           trio_send_all,
                                           trio_receive_some)
        _async_lib.aopen = trio.open_file
        _async_lib.sleep = trio.sleep
        _async_lib.task_manager = trio.open_nursery
        _async_lib.TaskTimeout = trio.TooSlowError
        _async_lib.timeout_after = trio.fail_after
        _async_lib.open_connection = trio_open_connection
        _async_lib.sendall = trio_send_all
        _async_lib.recv = trio_receive_some

    else:
        raise RuntimeError('{} is not a supported library.'.format(lib_name))


from .base_funcs import *
from .sessions import *
from .auth import *
