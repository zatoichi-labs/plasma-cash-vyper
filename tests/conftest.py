import pytest
import vyper


from plasma_cash import (
    Operator,
    RootChain,
    Token,
    User,
)


with open('contracts/Token.vy', 'r') as f:
    token_interface = vyper.compile_code(
            f.read(),
            output_formats=['abi', 'bytecode', 'bytecode_runtime']
        )

def set_challenge_period(code, new_param):
    c = code.replace("""
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)
""", """
CHALLENGE_PERIOD: constant(timedelta) = {}  # NOTE monkeypatched!
""".format(new_param))
    return c

with open('contracts/RootChain.vy', 'r') as f:
    rootchain_interface = vyper.compile_code(
            set_challenge_period(f.read(), 7),
            output_formats=['abi', 'bytecode', 'bytecode_runtime']
        )


# NOTE This should come for free with pytest-ethereum
from web3 import Web3, EthereumTesterProvider
@pytest.fixture
def w3():
    return Web3(EthereumTesterProvider())

# NOTE Replace with pytest-ethereum mining API
@pytest.fixture
def mine(w3):
    def _mine(numBlocks=1):
        w3.providers[0].ethereum_tester.mine_blocks(numBlocks)
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
    return Operator(w3, rootchain_contract.address, w3.eth.accounts[0])


@pytest.fixture
def users(w3, token_contract, rootchain_contract, operator):
    # Mint the first user a token
    t = Token(123)
    token_contract.functions.mint(w3.eth.accounts[1], t.uid).transact()
    # Create the users
    users = [User(w3, token_contract.address, rootchain_contract.address, operator, a)
             for a in w3.eth.accounts[1:]]  # Skip operator account
    users[0].purse.append(t)
    return users
