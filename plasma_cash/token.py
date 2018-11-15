from .transaction import Transaction


class Token:
    def __init__(self, uid: int):
        self.uid = uid
        self.history = []

    def addHistory(self, transaction: Transaction):
        self.history.append(transaction)
