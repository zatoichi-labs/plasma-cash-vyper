class User:

    def __init__(self, tester, rootchain, operator, uid, purse={}):
        self.tester = tester
        self.rootchain = rootchain
        self.operator = operator
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

    def __str__(self):
        return "User({}, {})".format(self.uid, \
                dict([(k, v) for k, v in self.purse.items() if len(v) > 0]))

    def deposit(self, token):
        self.rootchain.deposit(self, token)
        token.exit_started = self.tester.time
        token.addHistory(self, self, self.tester.time)
        self.purse['eth'].remove(token)
        self.purse['deposit'].append(token)

    def depositAccepted(self, token):
        """
        Callback for event when operator publishes block
        """
        self.purse['deposit'].remove(token)
        self.purse['plasma'].append(token)

    def send(self, user, token):
        # Block until operator processes our transaction
        assert self.operator.transfer(self, user, token)
        self.purse['plasma'].remove(token)

    def receive(self, user, token):
        token.addHistory(user, self, self.tester.time)
        # TODO Validate history
        self.purse['plasma'].append(token)
        return True  # Return acceptance status to operator

    def withdraw(self, token):
        if token in self.purse['deposit']:
            self.rootchain.withdraw(token)
            self.purse['deposit'].remove(token)
            self.purse['eth'].append(token)
        else:
            self.rootchain.startExit(self, token)
            self.purse['plasma'].remove(token)
            self.purse['withdraw'].append(token)

    def finalize(self, token):
        success = self.rootchain.finalizeExit(token)
        self.purse['withdraw'].remove(token)
        if success:
            token.clearHistory()
            self.purse['eth'].append(token)
        else:
            self.purse['plasma'].append(token)
        return success
