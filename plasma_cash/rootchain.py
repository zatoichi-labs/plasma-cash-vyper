class RootChain:

    def __init__(self, tester):
        self.tester = tester
        self.depositors = {}
        self.pending_deposits = []
        self.deposits = []
        self.exits = []
        self.challenges = []

    def deposit(self, user, token):
        token.exit_started = self.tester.time
        self.pending_deposits.append(token)
        self.depositors[token] = user

    def publish(self):
        for token in self.pending_deposits:
            self.depositors[token].depositAccepted(token)
            self.deposits.append(token)
        self.pending_deposits = []

    def withdraw(self, token):
        self.pending_deposits.remove(token)

    def startExit(self, user, token):
        # Assert user is receiver of exit transaction
        assert token.history[-1].receiver == user
        # Assert parent receiver is sender of exit transaction
        assert token.history[-2].receiver == token.history[-1].sender
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
