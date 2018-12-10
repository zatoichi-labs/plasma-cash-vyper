import copy

from typing import Set

from eth_account import Account

from .operator import Operator
#from .rootchain import RootChain - cannot cross-import, but this should be here
from .token import (
    Token,
    TokenStatus,
    Transaction,
)


class User:

    def __init__(self,
                 rootchain,#: RootChain,
                 operator: Operator,
                 acct: Account,
                 purse: Set[Token]=[]):
        self.rootchain = rootchain
        self.operator = operator
        self.acct = acct
        self.purse = copy.deepcopy(purse)

    def deposit(self, token):
        self.rootchain.deposit(self, token)
        token.set_deposited(self.rootchain._w3.eth.blockNumber)

    def depositAccepted(self, token):
        """
        Callback for event when operator publishes block
        """
        token.set_transferrable()

    def send(self, user, token):
        # Block until operator processes our transaction
        token.addTransaction(Transaction(self, user, self.rootchain._w3.eth.blockNumber))
        assert self.operator.transfer(self, user, token)
        self.purse.remove(token)

    def receive(self, user, token):
        # TODO Validate history
        self.purse.append(copy.deepcopy(token))
        return True  # Return acceptance status to operator

    def withdraw(self, token):
        if token.status is TokenStatus.DEPOSIT:
            self.rootchain.withdraw(token)
            token.finalize_withdrawal()
        else:
            self.rootchain.startExit(self, token)

    def finalize(self, token):
        success = self.rootchain.finalizeExit(token)
        if success:
            token.finalize_withdrawal()
        else:
            token.cancel_withdrawal()
        return success
