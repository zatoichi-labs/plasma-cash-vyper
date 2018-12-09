import pytest

from eth_utils import (
    to_int,
    to_bytes,
    keccak,
)

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
def initial_owners(w3):
    return w3.eth.accounts[1:3]  # should be divide into 64


@pytest.fixture
def initial_purse(initial_owners):
    # We need to issue 64 tokens, so allocate 64/N tokens
    issue_per_user = 64//len(initial_owners)
    assert issue_per_user*len(initial_owners) == 64
    purse = {}
    for a in initial_owners:
        purse[a] = [
                # First 4 bytes of the hash of user's address and a "random" num
                to_int(keccak(to_bytes(hexstr=a) + to_bytes(i))[:4])
                for i in range(issue_per_user)
            ]
    return purse


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
    return Operator(w3, rootchain)#, w3.eth.accounts[0])


@pytest.fixture
def users(w3, rootchain, operator, initial_owners, initial_purse):
    users = []
    # Add users with tokens
    for a in initial_owners:
        users.append(
                User(w3,
                     rootchain,
                     operator,
                     a,
                     {'eth': [ Token(uid) for uid in initial_purse[a] ]},
                )
            )
    # Add users without any tokens
    for a in w3.eth.accounts[1+len(initial_owners):]:
        users.append(User(w3, rootchain, operator, a))
    return users
