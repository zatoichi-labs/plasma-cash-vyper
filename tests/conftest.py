import pytest


class Token:
    exit_started = None

    def __init__(self, uid):
        self.uid = uid
        self.history = []

    def __eq__(self, other):
        return self.uid == other.uid

    def addHistory(self, *args):
        self.history.append(args)


@pytest.fixture
def tester():
    class Tester:
        time = 0
        def mine(self, num_blocks):
            self.time += 1
    return Tester()


@pytest.fixture
def rootchain():

    class RootChain:
        deposits = []
        exits = []
        challenges = []

        def deposit(self, token):
            pass  # Doesn't do anything

        def startExit(self, user, token):
            self.exits.append(token)

        def challengeExit(self, token):
            self.exits.remove(token)
            return True

        def respondChallenge(self, token):
            self.challenges.remove(token)

        def finalizeExit(self, token):
            self.exits.remove(token)
            if token not in self.challenges:
                self.deposits.remove(token)
                return True
            else:
                self.challenges.remove(token)
                return False

    return RootChain()


@pytest.fixture
def operator(rootchain):

    class Operator:

        entry_queue = []
        txn_queue = []

        def process_deposit(self, user, token):
            self.entry_queue.append((user, token))

        def send(self, sender, receiver, token):
            self.txn_queue.append((sender, receiver, token))
            receiver.receive(token)

        def sync(self):
            for u, t in self.entry_queue:
                assert t not in rootchain.deposits
                rootchain.deposits.append(t)
                u.purse['deposit'].remove(t)
                u.purse['plasma'].append(t)
            self.entry_queue = []
            self.txn_queue = []

        def is_tracking(self, token):
            self.sync()
            return token in rootchain.deposits

    return Operator()


@pytest.fixture
def users(tester, rootchain, operator):
    class User:

        def __init__(self, tokens):
            self.purse = {}
            self.purse['eth'] = tokens
            self.purse['plasma'] = []
            self.purse['deposit'] = []
            self.purse['withdraw'] = []

        def deposit(self, token):
            self.purse['eth'].remove(token)
            rootchain.deposit(token)
            token.addHistory(self, self, tester.time)
            operator.process_deposit(self, token)
            self.purse['deposit'].append(token)

        def send(self, user, token):
            self.purse['plasma'].remove(token)
            token.addHistory(self, user, tester.time)
            operator.send(self, user, token)

        def receive(self, token):
            self.purse['plasma'].append(token)

        def withdraw(self, token):
            self.purse['plasma'].remove(token)
            rootchain.startExit(self, token)
            token.exit_started = tester.time
            self.purse['withdraw'].append(token)

        def finalize(self, token):
            rootchain.finalizeExit(token)
            token.history = []
            
    return [User([Token(1)]), User([]), User([])]
