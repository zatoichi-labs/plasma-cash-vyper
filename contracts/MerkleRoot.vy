# Had to add this file separately for testing purposes

@constant
@public
def getMerkleRoot(
    path: uint256,
    leaf: bytes32,
    proof: bytes32[256]
) -> bytes32:
    targetBit: uint256 = 1  # traverse path in LSB:leaf->MSB:root order
    proofElement: bytes32 = proof[255]
    nodeHash: bytes32 = keccak256(leaf)  # First node is hash of leaf
    for i in range(256):
        # proof is in root->leaf order, so iterate in reverse
        proofElement = proof[255-i]
        if (bitwise_and(path, targetBit) > 0):
            nodeHash = keccak256(concat(proofElement, nodeHash))
        else:
            nodeHash = keccak256(concat(nodeHash, proofElement))
        targetBit = shift(targetBit, 1)
    return nodeHash
