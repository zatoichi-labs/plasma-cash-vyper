from eth_abi import encode_single
from eth_utils import keccak, to_checksum_address


class Transaction:

    def __init__(self,
            prevBlkNum,
            tokenId,
            newOwner,
            sigV,
            sigR,
            sigS):
        self.newOwner = newOwner
        self.tokenId = tokenId
        self.prevBlkNum = prevBlkNum
        self.signature = (sigV, sigR, sigS)

    @staticmethod
    def unsigned_txn_hash(
            prevBlkNum,
            tokenId,
            newOwner):
        data = encode_single('(uint256,uint256,address)', (prevBlkNum, tokenId, newOwner))
        return keccak(data)

    @property
    def sender(self):
        # FIXME do ECRecover on signature instead of this hack
        return to_checksum_address(self.signature[0])

    @property
    def to_tuple(self):
        return (self.prevBlkNum, self.tokenId, self.newOwner, *self.signature)

    @property
    def to_bytes(self):
        return encode_single('(uint256,uint256,address,uint256,uint256,uint256)', self.to_tuple)

    @property
    def hash(self):
        # Encode struct as ordered tuple of members
        return keccak(self.to_bytes)
