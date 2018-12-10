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
def accounts(w3):
    return w3.eth.accounts[1:9]


@pytest.fixture
def initial_purses(accounts):
    initial_owners = accounts[1:3]  # should be divide into 64
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
    # Empty purse for those who don't have tokens
    for a in list(set(accounts) - set(initial_owners)):
        purse[a] = []
    assert len(purse.keys()) == len(accounts)
    return purse


@pytest.fixture
def token(w3, accounts, initial_purses):
    owners = []
    tokens = []
    for a in accounts:
        for t in initial_purses[a]:
            owners.append(a)
            tokens.append(t)
    args = (owners, tokens)
    # NOTE Operator "deploys" this contract
    txn_hash = w3.eth.contract(**token_interface).constructor(*args).transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **token_interface)


@pytest.fixture
def rootchain(w3, token):
    # NOTE Operator "deploys" this contract
    txn_hash = w3.eth.contract(**rootchain_interface).constructor(token.address).transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return RootChain(w3, token.address, address)


@pytest.fixture
def operator(rootchain, accounts):
    return Operator(rootchain, accounts[0])


@pytest.fixture
def users(rootchain, operator, accounts, initial_purses):
    users = []
    for a in accounts[1:]:  # Skip operator
        tokens = []
        for uid in initial_purses[a]:
            t = Token(uid)
            tokens.append(t)
        u = User(rootchain, operator, a, tokens)
        users.append(u)
    return users
