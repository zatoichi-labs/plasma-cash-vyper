"""
Keep this test until _getMerkleRoot macro is merged into Vyper
"""
from hypothesis import given, strategies as st
from trie.smt import calc_root


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
def test_calc_root(rootchain_contract, tokenId, txnHash, proof):
    a = rootchain_contract.functions._getMerkleRoot(tokenId, txnHash, proof).call()
    b = calc_root(to_bytes32(tokenId), txnHash, proof)
    assert a == b, "Mismatch\nl: {}\nr: {}".format("0x"+a.hex(), "0x"+b.hex())
