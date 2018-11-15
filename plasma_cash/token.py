from .transaction import Transaction


class Token:
    """
    A token has a UID, represented by an integer at most 256 bits
    A token also has history, which is required to be tracked by plasma cash
    User uses token transaction history to manage exits and challenges
    History should be erased when a successful exit is performed
    """
    def __init__(self, uid: int):
        self._uid = uid
        self._history = []

    @property
    def uid(self):
        return self._uid

    @property
    def history(self):
        return self._history

    def addHistory(self, transaction: Transaction):
        self._history.append(transaction)

    def deleteHistory(self):
        """
        Only should be used when you exit
        """
        self._history = []

    def validateHistory(self):
        # TODO update API to check history is consistent
        return True

    # TODO Add serialization for giving to other users
