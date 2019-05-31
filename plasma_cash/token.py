import enum

from typing import List

from .transaction import Transaction


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

        self.uid = uid
        self.status = status

        if self.status in [TokenStatus.ROOTCHAIN, TokenStatus.DEPOSIT]:
            # Make history and empty list
            assert history is None
            history = []

        self.history = history  # Ordered list of transactions
        self.history_depth_checked = 0  # How much of the history has been checked (cache)

        if self.status in [TokenStatus.PLASMACHAIN, TokenStatus.WITHDRAWAL]:
            # Validate full history
            assert len(self.history) > 0
            assert self.valid

    @property
    def valid(self) -> bool:
        # If token has no history, nothing to check
        if not self.history:
            return True
        # Check if we've fully validated token before
        # (everything validates up to the last txn)
        if self.history_depth_checked == len(self.history) - 1:
            return True
        # Perform check on unchecked chain of history (cached)
        prior_txn = self.history[self.history_depth_checked]
        for txn in self.history[self.history_depth_checked+1:]:
            if txn.tokenId != prior_txn.tokenId:
                return False
            if txn.signer != prior_txn.newOwner:
                return False
            if txn.prevBlkNum < prior_txn.prevBlkNum:
                return False
        # Cache this for later (last entry starts the check)
        self.history_depth_checked = len(self.history) - 1
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
