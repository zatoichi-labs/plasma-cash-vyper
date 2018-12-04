import pytest


class Token:
    exit_started = None

    def __init__(self, uid):
        self.uid = uid


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

        def deposit(self, token):
            self.deposits.append(token)

        def withdraw(self, token):
            self.deposits.remove(token)

    return RootChain()


@pytest.fixture
def operator(rootchain):

    class Operator:

        def is_tracking(self, token):
            return token in rootchain.deposits

    return Operator()


@pytest.fixture
def users(tester, rootchain, operator):
    class User:

        def __init__(self, tokens):
            self.purse = {}
            self.purse['eth'] = tokens
            self.purse['plasma'] = []

        def deposit(self, token):
            self.purse['eth'].remove(token)
            rootchain.deposit(token)
            self.purse['plasma'].append(token)

        def receive(self, token):
            self.purse['plasma'].append(token)

        def send(self, user, token):
            self.purse['plasma'].remove(token)
            user.receive(token)

        def withdraw(self, token):
            self.purse['plasma'].remove(token)
            rootchain.withdraw(token)
            token.exit_started = tester.time
            self.purse['eth'].append(token)
            
    return [User([Token(1)]), User([])]
