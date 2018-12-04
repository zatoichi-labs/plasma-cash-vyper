class Transaction:

    def __init__(self, sender, receiver, block_number):
        self.sender = sender
        self.receiver = receiver
        self.block_number = block_number

    def __eq__(self, other):
        return self.sender == other.sender \
                and self.receiver == other.receiver \
                and self.block_number == other.block_number

    def __repr__(self):
        return "Transaction(User({}), User({}), {})".\
                format(self.sender.uid, self.receiver.uid, self.block_number)

class Token:

    def __init__(self, uid, history=[], exit_started=None):
        self.uid = uid
        self.history = history
        self.exit_started = exit_started

    def __repr__(self):
        return "Token({}, history={}, exit_started={})".\
                format(self.uid, self.history, self.exit_started)

    def __hash__(self):
        return self.uid

    def __eq__(self, other):
        return self.uid == other.uid

    def addHistory(self, sender, receiver, block_number):
        self.history.append(Transaction(sender, receiver, block_number))

    def clearHistory(self):
        self.history = []
