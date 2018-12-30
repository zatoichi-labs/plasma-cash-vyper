from typing import Set

from trie.smt import SparseMerkleTree

from eth_typing import AnyAddress, Hash32
from eth_account import Account
from eth_utils import to_bytes

from web3 import Web3

from .contracts import rootchain_interface
from .token import Transaction


def to_bytes32(val: int) -> bytes:
    assert 0 <= val < 2**256, "Value out of range!"
    return val.to_bytes(32, byteorder='big')


class TokenToTxnHashIdSMT(SparseMerkleTree):

    def __init__(self):
        # Tokens are 32 bytes big
        super().__init__(key_size=32)

    def get(self, token_uid: int) -> Hash32:
        return super().get(to_bytes32(token_uid))

    def branch(self, token_uid: int) -> Set[Hash32]:
        return super().branch(to_bytes32(token_uid))

    def set(self, token_uid: int, txn: Transaction) -> Set[Hash32]:
        return super().set(to_bytes32(token_uid), txn.hash)

    def exists(self, token_uid: int) -> bool:
        return super().exists(to_bytes32(token_uid))


class Operator:

    def __init__(self,
                 w3: Web3,
                 rootchain_address: AnyAddress,
                 acct: Account):
        self._w3 = w3
        self._rootchain = self._w3.eth.contract(rootchain_address, **rootchain_interface)
        self._acct = acct
        self.pending_deposits = {}  # Dict mapping tokenId to deposit txn in Rootchain contract
        self.deposits = {}  # Dict mapping tokenId to last known txn
        self.transactions = [TokenToTxnHashIdSMT()]  # Ordered list of block txn dbs
        self.last_sync_time = self._w3.eth.blockNumber

        # Add listeners (dict of filters: callbacks)
        self.listeners = {}
        # Add listener for deposits
        self.listeners[
                self._rootchain.events.DepositAdded.createFilter(
                    fromBlock=self._w3.eth.blockNumber
                )
            ] = self.addDeposit
        # Add listener for deposit cancellations
        self.listeners[
                self._rootchain.events.DepositCancelled.createFilter(
                    fromBlock=self._w3.eth.blockNumber,
                )
            ] = self.remDeposit

        # Add listener for finalized withdrawals
        self.listeners[
                self._rootchain.events.ExitFinished.createFilter(
                    fromBlock=self._w3.eth.blockNumber,
                )
            ] = self.remDeposit

        # TODO Add listener for challenging withdrawals

    # TODO Make this async loop
    def monitor(self):
        for log_filter, callback_fn in self.listeners.items():
            for log in log_filter.get_new_entries():
                callback_fn(log)
        if self._w3.eth.blockNumber - self.last_sync_time > 2:
            self.publish_block()
            self.last_sync_time = self._w3.eth.blockNumber

    def addDeposit(self, log):
        if not self.is_tracking(log.args['tokenId']):
            self.pending_deposits[log.args['tokenId']] = Transaction(**log.args)

    def remDeposit(self, log):
        if log.args['tokenId'] in self.pending_deposits.keys():
            del self.pending_deposits[log.args['tokenId']]
        if log.args['tokenId'] in self.deposits.keys():
            del self.deposits[log.args['tokenId']]

    def addTransaction(self, transaction: Transaction):
        """
        Sender asked for a transaction through us
        Validate with the receiver that they want it
        If valid, tracking in the transaction queue until publishing
        Don't forget to reply to the sender's request
        """
        # Can't transfer a token we aren't tracking in our db
        if not self.is_tracking(transaction.tokenId):
            print("Not Tracking!")
            return False
        # Holder of token didn't sign
        if self.deposits[transaction.tokenId].newOwner != transaction.sender:
            print("Not signed by current holder!")
            return False
        # NOTE This allows multiple transactions in a single block
        self.transactions[-1].set(transaction.tokenId, transaction)
        # Update last known transaction for deposit
        self.deposits[transaction.tokenId] = transaction
        return True

    def publish_block(self):
        # Process all the pending deposits we have
        for token_id, txn in self.pending_deposits.items():
            assert not self.is_tracking(token_id)
            self.deposits[token_id] = txn
            self.transactions[-1].set(token_id, txn)
        self.pending_deposits = {}

        # Submit the roothash for transactions
        self._rootchain.functions.\
                submitBlock(self.transactions[-1].root_hash).\
                transact({'from':self._acct, 'gas':1000000})
        # Reset transactions db
        self.transactions.append(TokenToTxnHashIdSMT())

    def is_tracking(self, token_uid):
        # Respond to user's request of whether we are tracking this token yet
        return token_uid in self.deposits.keys()

    def get_branch(self, token_uid, block_num):
        return self.transactions[block_num].branch(token_uid)
