import pytest


class Token:
    exit_started = None

    def __init__(self, uid):
        self.uid = uid
        self.history = []

    def __repr__(self):
        return "Token({})".format(self.uid)

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
def rootchain(tester):

    class RootChain:
        deposits = []
        exits = []
        challenges = []

        def deposit(self, token):
            token.exit_started = tester.time

        def startExit(self, user, token):
            self.exits.append(token)

        def challengeExit(self, token):
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
def operator(tester, rootchain):

    class Operator:
        last_sync_time = 0
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
            if tester.time - self.last_sync_time > 1:
                self.sync()
            return token in rootchain.deposits

    return Operator()


@pytest.fixture
def users(tester, rootchain, operator):
    class User:

        def __init__(self, uid, purse={}):
            token_purse = purse
            if 'eth' not in token_purse.keys():
                token_purse['eth'] = []
            if 'plasma' not in token_purse.keys():
                token_purse['plasma'] = []
            if 'deposit' not in token_purse.keys():
                token_purse['deposit'] = []
            if 'withdraw' not in token_purse.keys():
                token_purse['withdraw'] = []
            self.uid = uid
            self.purse = token_purse

        def __eq__(self, other):
            return self.uid == other.uid

        def __repr__(self):
            return "User({}, {})".format(self.uid, \
                    dict([(k, v) for k, v in self.purse.items() if len(v) > 0]))

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
            if token in self.purse['deposit']:
                self.purse['deposit'].remove(token)
                self.purse['eth'].append(token)
            else:
                self.purse['plasma'].remove(token)
                rootchain.startExit(self, token)
                self.purse['withdraw'].append(token)

        def finalize(self, token):
            success = rootchain.finalizeExit(token)
            token.history = []
            return success

    return [User(1, {'eth': [Token(1)]}), User(2), User(3)]
