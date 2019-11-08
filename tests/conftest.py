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
    return code.replace("""
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)
""", f"""
CHALLENGE_PERIOD: constant(timedelta) = {new_param}  # secs (NOTE monkeypatched!)
""")

# Hack until Istanbul and Vyper support chainId opcode
def set_chain_id(code, new_param):
    return code.replace("""
CHAIN_ID: constant(uint256) = 1337  # Must set dynamically for chain being deployed to
""", f"""
CHAIN_ID: constant(uint256) = {new_param}  # Must set dynamically for chain being deployed to
""")

with open('contracts/RootChain.vy', 'r') as f:
    code = f.read()
    code = set_challenge_period(code, 1)  # Very short challenge period of 1 sec
    code = set_chain_id(code, 61)  # web3/eth-tester default
    rootchain_interface = vyper.compile_code(
            code,
            output_formats=['abi', 'bytecode', 'bytecode_runtime']
        )


# Skip Hypothesis tests by default
def pytest_addoption(parser):
    parser.addoption('--hypothesis', action='store_true', dest="hypothesis",
                 default=False, help="enable `hypothesis` tests")


# Skip Hypothesis tests by default
def pytest_configure(config):
    if not config.option.hypothesis:
        setattr(config.option, 'markexpr', 'not hypothesis')


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
    # NOTE Operator "deploys" this contract (for testing)
    txn_hash = w3.eth.contract(**token_interface).constructor().transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **token_interface)


@pytest.fixture
def rootchain_contract(w3, token_contract):
    # NOTE Operator "deploys" this contract (for testing)
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
