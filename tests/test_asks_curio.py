# pylint: disable=wrong-import-order
import curio
import multio
import pytest_httpbin

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
        multio.init('curio')

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
        s = Session(self.httpbin.url, persist_cookies=True)
        async with curio.TaskGroup() as g:
            await g.spawn(base_tests.hsession_t_stateful(s))
        domain = '{}:{}'.format(self.httpbin.host, self.httpbin.port)
        cookies = s._cookie_tracker_obj.domain_dict[domain]
        assert len(cookies) == 1
        assert cookies[0].name == 'cow'
        assert cookies[0].value == 'moo'

    @curio_run
    async def test_session_stateful_double(self):
        from asks.sessions import Session
        s = Session(self.httpbin.url, persist_cookies=True)
        async with curio.TaskGroup() as g:
            for _ in range(4):
                await g.spawn(base_tests.hsession_t_stateful(s))

    # Session Tests
    # ==============

    # Test Session with two pooled connections on four get requests.
    @curio_run
    async def test_Session_smallpool(self):
        from asks.sessions import Session
        s = Session(connections=2)
        for _ in range(10):
            await curio.spawn(base_tests.session_t_smallpool(s, self.httpbin))
