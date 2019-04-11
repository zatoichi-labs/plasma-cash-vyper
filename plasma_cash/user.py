from typing import Set

from eth_typing import AnyAddress, ChecksumAddress
from eth_account import Account
from eth_utils import to_int

from trie.smt import calc_root

from web3 import Web3
from web3.middleware.signing import construct_sign_and_send_raw_middleware

from .contracts import (
    token_interface,
    rootchain_interface,
)
from .operator import Operator
from .token import (
    Token,
    TokenStatus,
)

from .transaction import Transaction


class User:

    def __init__(self,
                 w3: Web3,
                 token_address: AnyAddress,
                 rootchain_address: AnyAddress,
                 operator: Operator,
                 private_key: bytes,
                 purse: Set[Token]=None):
        self._w3 = w3
        self._token = self._w3.eth.contract(token_address, **token_interface)
        self._rootchain = self._w3.eth.contract(rootchain_address, **rootchain_interface)
        self._operator = operator
        self._acct = Account.privateKeyToAccount(private_key)
        # Allow web3 to autosign with account
        middleware = construct_sign_and_send_raw_middleware(private_key)
        self._w3.middleware_onion.add(middleware)
        # Load Tokens
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

    @property
    def address(self) -> ChecksumAddress:
        return self._acct.address

    # TODO Make this async loop
    def monitor(self):
        for log_filter, callback_fn in self.listeners.items():
            for log in log_filter.get_new_entries():
                callback_fn(log)

    def deposit(self, token_uid):
        # Get the actual token in our purse
        token = next((t for t in self.purse if t.uid == token_uid), None)

        # Allow the rootchain to pull all our deposits using safeTransferFrom
        if not self._token.functions.isApprovedForAll(
            self.address,
            self._rootchain.address,
        ).call():
            txn_hash = self._token.functions.setApprovalForAll(
                self._rootchain.address,
                True,
            ).transact({'from': self.address})
            self._w3.eth.waitForTransactionReceipt(txn_hash)  # FIXME Shouldn't have to wait

        # Create the deposit transaction for it (from user to user in current block)
        prevBlkNum = self._rootchain.functions.childChain_len().call()
        transaction = Transaction(
                self._w3.eth.chainId,
                self._rootchain.address,
                prevBlkNum,
                token_uid,
                self.address
            )
        signed = self._acct.signHash(transaction.msg_hash)
        transaction.add_signature(signed.signature)

        # Deposit on the rootchain
        txn_hash = self._rootchain.functions.deposit(
            transaction.to_tuple
        ).transact({'from': self.address})
        self._w3.eth.waitForTransactionReceipt(txn_hash)  # FIXME Shouldn't have to wait

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

    def transfer(self, user_address, token_uid):
        # NOTE Use user's address instead of object with messaging
        token = next((t for t in self.purse if t.uid == token_uid), None)
        # TODO Handle ETH transfer
        prevBlkNum = self._rootchain.functions.childChain_len().call()
        transaction = Transaction(
                self._w3.eth.chainId,
                self._rootchain.address,
                prevBlkNum,
                token_uid,
                user_address
            )
        signed = self._acct.signHash(transaction.msg_hash)
        transaction.add_signature(signed.signature)
        token.addTransaction(transaction)  # Not needed with messaging
        # Block until user approces our transfer
        # TODO Make this async
        #assert user.receive(self, token), "Receive Rejected!"
        # Block until operator processes our transaction
        # TODO Make this async
        assert self._operator.addTransaction(transaction), "Transaction Failed!"
        # TODO Do this with messaging
        #assert self._messaging.sendmessage(user_address, token), "Receive Rejected!"
        # Block until operator processes our transaction
        #assert self._messaging.sendmessage(self._operator, transaction), "Transaction Failed!"
        self.purse.remove(token)

    def receive(self, user_address, token):
        # NOTE This is big no-no for messaging
        # TODO Validate history
        self.purse.append(token)
        # TODO Listen for transaction success from operator
        # TODO Add listener to challenge withdraws for this token
        return True  # Return acceptance status to sender

    def withdraw(self, token_uid):
        token = next((t for t in self.purse if t.uid == token_uid), None)
        if token.status is TokenStatus.DEPOSIT:
            txn_hash = self._rootchain.functions.withdraw(token_uid).transact({'from': self.address})
            self._w3.eth.waitForTransactionReceipt(txn_hash)  # FIXME Shouldn't have to wait

            self.tokens_in_deposit.remove(token_uid)
            token.finalize_withdrawal()
            # TODO Cancel listener to challenge withdraws for this token
        else:
            assert len(token.history) >= 2, \
                    "History must have at least two items, including deposit"
            parent, exit = token.history[-2:]

            # Get the proofs of inclusion of each transaction in their respective blocks
            parentProof = self._operator.get_branch(parent.tokenId, parent.prevBlkNum)
            exitProof = self._operator.get_branch(exit.tokenId, exit.prevBlkNum)

            # We can start the exit now
            txn_hash = self._rootchain.functions.startExit(
                parent.to_tuple,
                parentProof,
                exit.to_tuple,
                exitProof,
            ).transact({'from': self.address})
            self._w3.eth.waitForTransactionReceipt(txn_hash)  # FIXME Shouldn't have to wait

            token.set_in_withdrawal()
            # TODO Add listener for challenges to withdraw
            # TODO Add listener to alert for successful, non-interactive challenges
            # TODO Add callback to finalize after challenge period is over

    def finalize(self, token_uid):
        token = next((t for t in self.purse if t.uid == token_uid), None)
        txn_hash = self._rootchain.functions.finalizeExit(token_uid).transact({'from': self.address})
        receipt = self._w3.eth.waitForTransactionReceipt(txn_hash)
        if self._rootchain.events.ExitFinished(receipt).event_name == 'ExitFinished':
            token.finalize_withdrawal()
        else:
            token.cancel_withdrawal()
        # TODO Cancel listener to challenge withdraws for this token
