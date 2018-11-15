from .sparse_merkle_tree import SparseMerkleTree as SMT


class Operator:
    
    def __init__(self, address, rootchain):
        self.address = address
        self.rootchain = rootchain
        self.block_smt = SMT()

    def commitTransaction(self, transaction):
        self.block_smt.set(transaction.tokenId, transaction.hash())

    def submitBlock(self):
        # Upload current block!
        self.rootchain.functions.submitBlock(self.block_smt.root_hash).transact()
        # Reset smt
        self.block_smt = SMT()

    def getBranch(self, key):
        return self.block_smt.get(key)
