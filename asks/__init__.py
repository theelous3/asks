# pylint: disable=wildcard-import


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
        raise RuntimeError(f'{lib_name} is not a supported library.')


from .base_funcs import *
from .sessions import *
from .auth import *
