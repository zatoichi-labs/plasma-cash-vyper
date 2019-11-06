import pytest

from web3 import Web3, EthereumTesterProvider
import vyper

from hypothesis import given, strategies as st
from trie.smt import calc_root


@pytest.fixture(scope="module")
def merkle_root_contract():
    w3 = Web3(EthereumTesterProvider())
    with open("contracts/MerkleRoot.vy", "r") as f:
        interface = vyper.compile_code(f.read(), output_formats=["abi", "bytecode"])
    txn_hash = w3.eth.contract(**interface).constructor().transact()
    address = w3.eth.waitForTransactionReceipt(txn_hash)['contractAddress']
    return w3.eth.contract(address, **interface)


def to_bytes32(val: int) -> bytes:
    assert 0 <= val < 2**256, "Value out of range!"
    return val.to_bytes(32, byteorder='big')


@given(
    tokenId=st.integers(min_value=0, max_value=2**256-1),
    txnHash=st.binary(min_size=32, max_size=32),
    # NOTE: For some reason, this fails to pass the health check
    #proof=st.lists(elements=st.binary(min_size=32, max_size=32), min_size=256, max_size=256),
    proof=st.lists(elements=st.just(b'\x00' * 32), min_size=256, max_size=256),
)
def test_calc_root(merkle_root_contract, tokenId, txnHash, proof):
    a = merkle_root_contract.functions.getMerkleRoot(tokenId, txnHash, proof).call()
    b = calc_root(to_bytes32(tokenId), txnHash, proof)
    assert a == b, "Mismatch\nl: {}\nr: {}".format("0x"+a.hex(), "0x"+b.hex())
