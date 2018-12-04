import pytest

from plasma_cash import (
    Operator,
    RootChain,
    Token,
    User,
)


@pytest.fixture
def tester():
    class Tester:
        time = 0
        def mine(self, num_blocks):
            self.time += 1
    return Tester()


@pytest.fixture
def rootchain(tester):
    return RootChain(tester)


@pytest.fixture
def operator(tester, rootchain):
    return Operator(tester, rootchain)


@pytest.fixture
def users(tester, rootchain, operator):
    return [
        User(tester, rootchain, operator, 1, {'eth': [Token(1)]}),
        User(tester, rootchain, operator, 2),
        User(tester, rootchain, operator, 3)
    ]
