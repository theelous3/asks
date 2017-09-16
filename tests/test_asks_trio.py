import pytest_httpbin
import trio

import asks
from . import base_tests


def trio_run(func):
    def func_wrapper(*args, **kwargs):
        return trio.run(func, *args, **kwargs)
    return func_wrapper


@pytest_httpbin.use_class_based_httpbin
class TestAsksTrio(metaclass=base_tests.TestAsksMeta):
    run = trio_run

    @classmethod
    def setup_class(cls):
        asks.init('trio')


    @trio_run
    async def test_hsession_smallpool(self):
        from asks.sessions import Session
        s = Session(self.httpbin.url, connections=2)
        async with trio.open_nursery() as n:
            for _ in range(10):
                n.spawn(base_tests.hsession_t_smallpool, s)


    @trio_run
    async def test_session_stateful(self):
        from asks.sessions import Session
        s = Session(
            'https://google.ie', persist_cookies=True)
        async with trio.open_nursery() as n:
            n.spawn(base_tests.hsession_t_stateful, s)
        assert 'www.google.ie' in s._cookie_tracker_obj.domain_dict.keys()


    @trio_run
    async def test_session_stateful_double(self):
        from asks.sessions import Session
        s = Session('https://google.ie', persist_cookies=True)
        async with trio.open_nursery() as n:
            for _ in range(4):
                n.spawn(base_tests.session_t_stateful_double_worker, s)


    # Session Tests
    # ==============

    # Test Session with two pooled connections on four get requests.
    @trio_run
    async def test_Session_smallpool(self):
        from asks.sessions import Session
        s = Session(connections=2)
        async with trio.open_nursery() as n:
            for _ in range(10):
                n.spawn(base_tests.session_t_smallpool, s, self.httpbin)
