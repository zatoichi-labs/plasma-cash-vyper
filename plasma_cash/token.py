import enum

from typing import List

from web3.contract import Contract


class Transaction:

    def __init__(self, sender, receiver, block_number):
        self.signature = sender.acct
        self.receiver = receiver.acct
        self.block_number = block_number

    @property
    def sender(self):
        return self.signature  # FIXME do ECRecover

    def __eq__(self, other):
        return self.sender == other.sender \
                and self.receiver == other.receiver \
                and self.block_number == other.block_number


class TokenStatus(enum.Enum):
    ROOTCHAIN = 0
    DEPOSIT = 1
    PLASMACHAIN = 2
    WITHDRAWAL = 3


class Token:

    def __init__(self,
                 uid: int,
                 status: TokenStatus=TokenStatus.ROOTCHAIN,
                 history: List[Transaction]=[],
                 deposit_block_number: int=None):

        if status is TokenStatus.ROOTCHAIN:
            assert len(history) == 0
            assert deposit_block_number is None
        elif status is TokenStatus.DEPOSIT or len(history) == 0:
            assert deposit_block_number is not None
        elif len(history) > 0:
            assert status in [TokenStatus.PLASMACHAIN, TokenStatus.WITHDRAWAL]
            assert deposit_block_number <= history[0].block_number
            # FIXME Validate full history

        self.uid = uid
        self.status = status
        self.history = history
        self.deposit_block_number = deposit_block_number

    # So item in dict.items() works
    def __hash__(self):
        return self.uid

    def __eq__(self, other):
        return self.uid == other.uid

    @property
    def deposited(self) -> bool:
        return self.status == TokenStatus.DEPOSIT \
                or self.status == TokenStatus.PLASMACHAIN

    def set_deposited(self, deposit_block_number):
        assert self.status == TokenStatus.ROOTCHAIN
        self.deposit_block_number = deposit_block_number
        self.status = TokenStatus.DEPOSIT

    @property
    def transferrable(self) -> bool:
        return self.status == TokenStatus.ROOTCHAIN or \
                self.status == TokenStatus.PLASMACHAIN

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
