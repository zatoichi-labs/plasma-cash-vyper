class Operator:

    def __init__(self, tester, rootchain):
        self.tester = tester
        self.rootchain = rootchain
        self.last_sync_time = 0
        self.token_uid_tracking = []
        self.txn_queue = []

    def transfer(self, sender, receiver, token):
        """
        Sender asked for a transaction through us
        Validate with the receiver that they want it
        If valid, tracking in the transaction queue until publishing
        Don't forget to reply to the sender's request
        """
        # NOTE can't transfer a token we aren't tracking
        if token.uid not in self.token_uid_tracking:
            return False
        approved = receiver.receive(sender, token)
        if approved:
            self.txn_queue.append((sender, receiver, token))
        return approved

    def sync(self):
        for t in self.rootchain.pending_deposits:
            assert t.uid not in self.token_uid_tracking
            # TODO Add the entry transactions to the transaction queue
            self.token_uid_tracking.append(t.uid)
        # TODO Do something with the transaction queue
        self.rootchain.publish()
        self.last_sync_time = self.tester.time

    def is_tracking(self, token):
        # NOTE This is temporary until async behavior is implemented
        if self.tester.time - self.last_sync_time > 1:
            self.sync()
        # Respond to user's request of whether we are tracking this token yet
        return token.uid in self.token_uid_tracking
