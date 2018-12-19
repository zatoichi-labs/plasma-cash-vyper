import enum

from typing import List

from web3.contract import Contract

from eth_abi import encode_single
from eth_utils import keccak, to_checksum_address


def to_bytes32(val: int) -> bytes:
    assert 0 <= val < 2**256, "Value out of range!"
    return val.to_bytes(32, byteorder='big')


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
    def hash(self):
        # Encode struct as ordered tuple of members
        data = encode_single('(uint256,uint256,address,uint256,uint256,uint256)', self.to_tuple)
        return keccak(data)


class TokenStatus(enum.Enum):
    ROOTCHAIN = 0
    DEPOSIT = 1
    PLASMACHAIN = 2
    WITHDRAWAL = 3


class Token:

    def __init__(self,
                 uid: int,
                 status: TokenStatus=TokenStatus.ROOTCHAIN,
                 history: List[Transaction]=None):

        if status in [TokenStatus.ROOTCHAIN, TokenStatus.DEPOSIT]:
            assert history is None
            history = []
        else:
            assert status in [TokenStatus.PLASMACHAIN, TokenStatus.WITHDRAWAL]
            # Validate full history
            assert len(history) > 0
            assert self.valid

        self.uid = uid
        self.status = status
        self.history = history
        self.history_depth_checked = 0

    @property
    def valid(self) -> bool:
        # If token has no history, nothing to check
        if not self.history:
            return True
        # Check if we've fully validated token before
        if self.history_depth_checked == len(self.history):
            return True
        # Perform check on entire chain of history
        prior_txn = self.history[0]
        for txn in self.history[1:]:
            if txn.token_uid != prior_txn.token_uid:
                return False
            if txn.sender != prior_txn.receiver:
                return False
            if txn.block_number < prior_txn.block_number:
                return False
        # Cache this for later
        self.history_depth_checked = len(self.history)
        return True

    @property
    def deposited(self) -> bool:
        return self.status == TokenStatus.DEPOSIT \
                or self.status == TokenStatus.PLASMACHAIN

    @property
    def transferrable(self) -> bool:
        return self.status == TokenStatus.ROOTCHAIN or \
                self.status == TokenStatus.PLASMACHAIN

    def set_deposited(self, transaction: Transaction):
        assert self.status == TokenStatus.ROOTCHAIN
        self.status = TokenStatus.DEPOSIT
        self.history.append(transaction)

    def set_transferrable(self):
        self.status = TokenStatus.PLASMACHAIN

    def addTransaction(self, transaction: Transaction):
        self.history.append(transaction)

    @property
    def in_withdrawal(self) -> bool:
        return self.status == TokenStatus.WITHDRAWAL

    def set_in_withdrawal(self):
        self.status = TokenStatus.WITHDRAWAL

    def cancel_withdrawal(self):
        self.status = TokenStatus.PLASMACHAIN

    def finalize_withdrawal(self):
        self.status = TokenStatus.ROOTCHAIN
        self.history = []
        self.deposit_block_number = None
