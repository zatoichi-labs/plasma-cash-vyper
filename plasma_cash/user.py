from .operator import Operator
from .token import Token


class User:
    
    def __init__(self,
        address,
        token,
        rootchain,
        operator: Operator,
        purse
    ):
        self.address = address
        self.rootchain = rootchain
        self.token = token
        self.operator = operator
        # Initialize starting purse
        self.eth_purse = [Token(t) for t in purse]
        self.plasma_purse = []

    def constructTransaction(self, token, recipient):
        transaction = Transaction(
                self.rootchain.functions.childChain_len().call(),
                token.uid,
                recipient.address
            )
        messageHash = transaction.hash()
        signature = self.signHash(messageHash)
        signed_transaction = SignedTransaction(
                self.prevBlockNum,
                self.tokenId,
                self.newOwner,
                *signature
            )
        return signed_transaction.sign(self)

    def deposit(self):
        token = self.eth_purse[-1]
        transaction = self.constructTransaction(token, self) 
        self.token.safeTransferFrom(
                self.address,
                self.rootchain.address,
                token.uid,
                transaction.serialize()
            )
        token.addHistory(transaction)
        self.plasma_purse.append(token)

    def send(self, recipient):
        token = self.plasma_purse.pop()
        transaction = self.constructTransaction(token, recipient) 
        self.operator.commitTransaction(transaction)
        token.addHistory(transaction)
        recipient.receive(token)

    def receive(self, token):
        self.plasma_purse.append(token)

    def withdraw(self):
        token = self.plasma_purse.pop()
        self.eth_purse.append(token)
        self.rootchain.startExit()
