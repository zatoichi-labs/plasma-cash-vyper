from eth_typing import Address
from web3 import Web3

from .contracts import (
    token_interface,
    rootchain_interface,
)

from .token import Token
from .user import User  # FIXME remove all references of User


class RootChain:
    """
    Utility class to provide API for contracts/RootChain.vy
    """

    def __init__(self, w3: Web3, token_address: Address, rootchain_address: Address):
        self._w3 = w3
        self._token = w3.eth.contract(token_address, **token_interface)
        self._contract = w3.eth.contract(rootchain_address, **rootchain_interface)
        self.depositors = {}
        self.pending_deposits = []
        self.deposits = []
        self.exits = []
        self.challenges = []

    def deposit(self, user: User, token: Token):
        self.pending_deposits.append(token)
        self.depositors[token.uid] = user

    def publish(self):
        for token in self.pending_deposits:
            self.depositors[token.uid].depositAccepted(token)
            self.deposits.append(token)
        self.pending_deposits = []

    def withdraw(self, token: Token):
        self.pending_deposits.remove(token)

    def startExit(self, user: User, token: Token):
        # Assert user is receiver of exit transaction
        assert token.history[-1].receiver == user.acct
        if len(token.history) > 1:
            # Assert parent receiver is sender of exit transaction
            assert token.history[-2].receiver == token.history[-1].sender
        else:
            # Check that sender was depositor
            assert self.depositors[token.uid].acct == token.history[-1].sender
        self.exits.append(token)

    def challengeExit(self, token: Token):
        t = self.exits[self.exits.index(token)]

        if len(t.history) >= 1 and len(token.history) >= 2:
            challengeAfter = t.history[-1] == token.history[-2]
        elif len(token.history) >= 1:
            challengeAfter = self.depositors[token.uid].acct == token.history[0].sender and \
                    self.depositors[token.uid].acct != token.history[-1].receiver
        else:
            challengeAfter = False  # Has to be at least one transaction deep

        if len(t.history) >= 2 and len(token.history) >= 2:
            challengeBetween = t.history[-2] == token.history[-2] and \
                    t.history[-1] != token.history[-1]
        elif len(t.history) >= 1 and len(token.history) >= 1:
            challengeBetween = self.depositors[token.uid].acct == t.history[-1].sender and \
                    t.history[-1] != token.history[-1] and \
                    t.history[-1].block_number > token.history[-1].block_number
        else:
            challengeBetween = False  # Has to be at least one transaction deep

        challengeBefore = True
        if challengeAfter or challengeBetween:
            self.exits.remove(token)
            return True
        elif challengeBefore:
            self.challenges.append(token)
            return False
        else:
            raise ValueError("Challenge not accepted!")

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
