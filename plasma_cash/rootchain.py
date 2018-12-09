from eth_typing import Address
from web3 import Web3

from .contracts import rootchain_interface
from .token import Token
from .user import User


class RootChain:
    """
    Utility class to provide API for contracts/RootChain.vy
    """

    def __init__(self, w3: Web3, rootchain_address: Address):
        self._contract = w3.eth.contract(rootchain_address, **rootchain_interface)
        self.depositors = {}
        self.pending_deposits = []
        self.deposits = []
        self.exits = []
        self.challenges = []

    def deposit(self, user: User, token: Token):
        self.pending_deposits.append(token)
        self.depositors[token] = user

    def publish(self):
        for token in self.pending_deposits:
            self.depositors[token].depositAccepted(token)
            self.deposits.append(token)
        self.pending_deposits = []

    def withdraw(self, token: Token):
        self.pending_deposits.remove(token)

    def startExit(self, user: User, token: Token):
        # Assert user is receiver of exit transaction
        assert token.history[-1].receiver == user
        # Assert parent receiver is sender of exit transaction
        assert token.history[-2].receiver == token.history[-1].sender
        self.exits.append(token)

    def challengeExit(self, token: Token):
        t = self.exits[self.exits.index(token)]
        challengeAfter = t.history[-1] == token.history[-2]
        challengeBetween = t.history[-2] == token.history[-2] and \
                t.history[-1] != token.history[-1]
        if challengeAfter or challengeBetween:
            self.exits.remove(token)
            return True
        else:
            self.challenges.append(token)
            return False

    def respondChallenge(self, token: Token):
        self.challenges.remove(token)

    def finalizeExit(self, token: Token):
        self.exits.remove(token)
        if token not in self.challenges:
            self.deposits.remove(token)
            return True
        else:
            self.challenges.remove(token)
            return False