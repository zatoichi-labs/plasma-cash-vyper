import pytest

from plasma_cash import (
    token_interface,
    rootchain_interface,
    Operator,
    RootChain,
    Token,
    User,
)


@pytest.fixture
def tester(w3):
    class Tester:
        def __init__(self, w3):
            self.w3 = w3

        @property
        def time(self):
            return self.w3.eth.blockNumber

        def mine(self, numBlocks=1):
            self.w3.providers[0].ethereum_tester.mine_blocks(numBlocks)

    return Tester(w3)


@pytest.fixture
def token(w3):
    owners = []
    for a in w3.eth.accounts[1:9]:
        for _ in range(8):
            owners.append(a)
    tokens = list(range(64))
    args = (owners, tokens)
    txn_hash = w3.eth.contract(**token_interface).constructor(*args).transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **token_interface)


@pytest.fixture
def rootchain(w3, token):
    txn_hash = w3.eth.contract(**rootchain_interface).constructor(token.address).transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return RootChain(w3, address)


@pytest.fixture
def operator(w3, rootchain):
    return Operator(w3, rootchain)


@pytest.fixture
def users(w3, rootchain, operator):
    return [
        User(w3, rootchain, operator, 1, {'eth': [Token(1)]}),
        User(w3, rootchain, operator, 2),
        User(w3, rootchain, operator, 3)
    ]
