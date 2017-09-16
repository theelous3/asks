import curio
import pytest_httpbin

import asks
from . import base_tests


def curio_run(func):
    def func_wrapper(*args, **kwargs):
        return curio.run(func(*args, **kwargs))
    return func_wrapper


@pytest_httpbin.use_class_based_httpbin
class TestAsksCurio(metaclass=base_tests.TestAsksMeta):
    run = curio_run

    @classmethod
    def setup_class(cls):
        asks.init('curio')


    @curio_run
    async def test_hsession_smallpool(self):
        from asks.sessions import Session
        s = Session(self.httpbin.url, connections=2)
        async with curio.TaskGroup() as g:
            for _ in range(10):
                await g.spawn(base_tests.hsession_t_smallpool(s))


    @curio_run
    async def test_session_stateful(self):
        from asks.sessions import Session
        s = Session(
            'https://google.ie', persist_cookies=True)
        async with curio.TaskGroup() as g:
            await g.spawn(base_tests.hsession_t_stateful(s))
        assert 'www.google.ie' in s._cookie_tracker_obj.domain_dict.keys()


    @curio_run
    async def test_session_stateful_double(self):
        from asks.sessions import Session
        s = Session('https://google.ie', persist_cookies=True)
        async with curio.TaskGroup() as g:
            for _ in range(4):
                await g.spawn(base_tests.session_t_stateful_double_worker(s))


    # Session Tests
    # ==============

    # Test Session with two pooled connections on four get requests.
    @curio_run
    async def test_Session_smallpool(self):
        from asks.sessions import Session
        s = Session(connections=2)
        for _ in range(10):
            await curio.spawn(base_tests.session_t_smallpool(s, self.httpbin))
