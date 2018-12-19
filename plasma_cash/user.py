from typing import Set

from eth_typing import AnyAddress
from eth_account import Account
from eth_utils import to_int

from trie.smt import calc_root

from web3 import Web3

from .contracts import (
    token_interface,
    rootchain_interface,
)
from .operator import Operator
from .token import (
    Token,
    TokenStatus,
    Transaction,
)


def to_bytes32(val: int) -> bytes:
    assert 0 <= val < 2**256, "Value out of range!"
    return val.to_bytes(32, byteorder='big')


class User:

    def __init__(self,
                 w3: Web3,
                 token_address: AnyAddress,
                 rootchain_address: AnyAddress,
                 operator: Operator,
                 acct: Account,
                 purse: Set[Token]=None):
        self._w3 = w3
        self._token = self._w3.eth.contract(token_address, **token_interface)
        self._rootchain = self._w3.eth.contract(rootchain_address, **rootchain_interface)
        # Allow the rootchain to pull all our deposits using safeTransferFrom
        if not self._token.functions.isApprovedForAll(acct, rootchain_address).call():
            self._token.functions.setApprovalForAll(rootchain_address, True).transact({'from':acct})
        self._operator = operator
        self._acct = acct
        self.purse = purse if purse else []
        # Add listeners (dict of filters: callbacks)
        self.listeners = {}
        # Add listener to accept list of deposited tokens
        self.tokens_in_deposit = []
        self.listeners[
                self._rootchain.events.BlockPublished.createFilter(
                    fromBlock=self._w3.eth.blockNumber
                )
            ] = self.handleDeposits

    # TODO Make this async loop
    def monitor(self):
        for log_filter, callback_fn in self.listeners.items():
            for log in log_filter.get_new_entries():
                callback_fn(log)

    def deposit(self, token_uid):
        # Get the actual token in our purse
        token = next((t for t in self.purse if t.uid == token_uid), None)
        # Create the deposit transaction for it (from user to user in current block)
        prevBlkNum = self._rootchain.functions.childChain_len().call()
        unsigned_txn_hash = Transaction.unsigned_txn_hash(prevBlkNum, token_uid, self._acct)
        signature = (to_int(hexstr=self._acct), 0, 0)#self._w3.eth.sign(self._acct, unsigned_txn_hash)
        transaction = Transaction(prevBlkNum, token_uid, self._acct, *signature)
        # Deposit on the rootchain
        self._rootchain.functions.deposit(*transaction.to_tuple).transact({'from':self._acct})
        # Also log when we deposited it and add the deposit to our history
        token.set_deposited(transaction)
        # Add token to handleDeposits listener callback
        self.tokens_in_deposit.append(token_uid)

    def handleDeposits(self, log):
        """
        Callback for event when operator publishes block
        """
        for token_uid in self.tokens_in_deposit:
            # Get the actual token in our purse
            token = next((t for t in self.purse if t.uid == token_uid), None)
            # TODO Validate that token in block
            token.set_transferrable()
            # TODO Add listener to challenge withdraws for this token
        self.tokens_in_deposit = []

    def transfer(self, user, token_uid):
        # NOTE Use user's address instead of object with messaging
        token = next((t for t in self.purse if t.uid == token_uid), None)
        # TODO Handle ETH transfer
        prevBlkNum = self._rootchain.functions.childChain_len().call()
        unsigned_txn_hash = Transaction.unsigned_txn_hash(prevBlkNum, token_uid, user._acct)
        signature = (to_int(hexstr=self._acct), 0, 0)#self._w3.eth.sign(self._acct, unsigned_txn_hash)
        transaction = Transaction(prevBlkNum, token_uid, user._acct, *signature)
        token.addTransaction(transaction)  # Not needed with messaging
        # Block until user approces our transfer
        # TODO Make this async
        assert user.receive(self, token), "Receive Rejected!"
        # Block until operator processes our transaction
        # TODO Make this async
        assert self._operator.addTransaction(transaction), "Transaction Failed!"
        # TODO Do this with messaging
        #assert self._messaging.sendmessage(user_address, token), "Receive Rejected!"
        # Block until operator processes our transaction
        #assert self._messaging.sendmessage(self._operator, transaction), "Transaction Failed!"
        self.purse.remove(token)

    def receive(self, user, token):
        # NOTE This is big no-no for messaging
        # TODO Validate history
        self.purse.append(token)
        # TODO Listen for transaction success from operator
        # TODO Add listener to challenge withdraws for this token
        return True  # Return acceptance status to sender

    def withdraw(self, token_uid):
        token = next((t for t in self.purse if t.uid == token_uid), None)
        if token.status is TokenStatus.DEPOSIT:
            self.tokens_in_deposit.remove(token_uid)
            self._rootchain.functions.withdraw(token_uid).transact({'from':self._acct})
            token.finalize_withdrawal()
            # TODO Cancel listener to challenge withdraws for this token
        else:
            parent, exit = token.history[-2:]
            parentProof = self._operator.get_branch(parent.tokenId, parent.prevBlkNum)
            exitProof = self._operator.get_branch(exit.tokenId, exit.prevBlkNum)
            blkNum = exit.prevBlkNum+1
            self._rootchain.functions.\
                    startExit(*parent.to_tuple, parentProof, *exit.to_tuple, exitProof, blkNum).\
                    transact({'from':self._acct})
            token.set_in_withdrawal()
            # TODO Add listener for challenges to withdraw
            # TODO Add listener to alert for successful, non-interactive challenges
            # TODO Add callback to finalize after challenge period is over

    def finalize(self, token_uid):
        token = next((t for t in self.purse if t.uid == token_uid), None)
        txn_hash = self._rootchain.functions.finalizeExit(token_uid).transact({'from':self._acct})
        receipt = self._w3.eth.waitForTransactionReceipt(txn_hash)
        if self._rootchain.events.ExitFinished(receipt).event_name == 'ExitFinished':
            token.finalize_withdrawal()
        else:
            token.cancel_withdrawal()
        # TODO Cancel listener to challenge withdraws for this token
