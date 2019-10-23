import pytest
import vyper

from eth_account import Account
from eth_tester.backends.pyevm.main import get_default_account_keys

from plasma_cash import (
    Operator,
    RootChain,
    Token,
    User,
)


DEFAULT_KEYS = get_default_account_keys()
DEFAULT_ACCOUNTS = [Account.privateKeyToAccount(k).address for k in DEFAULT_KEYS]


with open('contracts/Token.vy', 'r') as f:
    token_interface = vyper.compile_code(
            f.read(),
            output_formats=['abi', 'bytecode', 'bytecode_runtime']
        )

# Hack until pytest-ethereum includes a way to change the block timestamp
def set_challenge_period(code, new_param):
    c = code.replace("""
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)
""", """
CHALLENGE_PERIOD: constant(timedelta) = {0}  # secs (NOTE monkeypatched!)
""".format(new_param))
    return c

with open('contracts/RootChain.vy', 'r') as f:
    rootchain_interface = vyper.compile_code(
            set_challenge_period(f.read(), 1),
            output_formats=['abi', 'bytecode', 'bytecode_runtime']
        )


def pytest_addoption(parser):
    parser.addoption('--slow', action='store_true', dest="slow",
                 default=False, help="enable `slow` decorated tests")


def pytest_configure(config):
    if not config.option.slow:
        setattr(config.option, 'markexpr', 'not slow')


# NOTE This should come for free with pytest-ethereum
from web3 import Web3, EthereumTesterProvider
from eth_tester.backends.pyevm import main
@pytest.fixture
def w3():
    # Monkeypatch
    main.GENESIS_GAS_LIMIT = 6283184 # FIXME 2x'd this from 3141592
    return Web3(EthereumTesterProvider())

# NOTE Replace with pytest-ethereum mining API
@pytest.fixture
def mine(w3):
    def _mine(numBlocks=1):
        w3.provider.ethereum_tester.mine_blocks(numBlocks)
    return _mine


@pytest.fixture
def token_contract(w3):
    # NOTE Operator "deploys" this contract
    txn_hash = w3.eth.contract(**token_interface).constructor().transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **token_interface)


@pytest.fixture
def rootchain_contract(w3, token_contract):
    # NOTE Operator "deploys" this contract
    txn_hash = w3.eth.contract(**rootchain_interface).constructor(token_contract.address).transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **rootchain_interface)


@pytest.fixture
def operator(w3, rootchain_contract):
    for i, a in enumerate(w3.eth.accounts):
        assert DEFAULT_ACCOUNTS[i] == a
    return Operator(w3, rootchain_contract.address, DEFAULT_KEYS[0])


@pytest.fixture
def users(w3, token_contract, rootchain_contract, operator):
    # Mint the first user a token
    t = Token(123)
    token_contract.functions.mint(w3.eth.accounts[1], t.uid).transact()

    # Create the users
    users = [User(w3, token_contract.address, rootchain_contract.address, operator, k)
             for k in DEFAULT_KEYS[1:]]  # Skip operator account
    users[0].purse.append(t)
    return users
