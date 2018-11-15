import pytest
from eth_utils import keccak, to_int, to_bytes

from plasma_cash import Operator, User


NUM_TOKENS=64  # Maximum our contract takes for initilizer


@pytest.fixture
def purse(w3):
    uid = lambda i, a: to_int(keccak(to_bytes(hexstr=a) + to_bytes(i)))
    purse = {}
    users = w3.eth.accounts[1:]
    tokens_per_user = NUM_TOKENS//len(users)
    # Psuedo-randomly distribute tokens to users
    for a in users:
        # Give each account 7 tokens with random IDs
        uids = [uid(i, a) for i in range(tokens_per_user)]
        purse[a] = uids
    # Make sure we have exactly NUM_TOKENS distributed
    distributed = (tokens_per_user*len(users))
    for i in range(NUM_TOKENS-distributed):
        a = users[i]
        purse[a].append(uid(tokens_per_user, a))
    return purse


@pytest.fixture
def token(vy_deployer, purse):
    # Starting balances is a list of tokens and users who own them
    tokens = []
    owners = []
    for a, owned in purse.items():
        for t in owned:
            tokens.append(t)
            owners.append(a)
    assert len(tokens) == len(owners) == NUM_TOKENS
    return vy_deployer.deploy("Token", owners, tokens)[0].\
            deployments.get_contract_instance("Token")


@pytest.fixture
def rootchain(vy_deployer, token):
    return vy_deployer.deploy("RootChain", token.address)[0].\
            deployments.get_contract_instance("RootChain")


@pytest.fixture
def operator(w3, rootchain):
    return Operator(w3.eth.accounts[0], rootchain)


@pytest.fixture
def users(w3, token, rootchain, operator, purse):
    return [User(a, token, rootchain, operator, purse[a]) \
            for a in w3.eth.accounts[1:]]
