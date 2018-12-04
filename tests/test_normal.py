# Test normal operation of the Plasma chain (entries and exits)
PLASMA_SYNC_PERIOD = 0
PLASMA_WITHDRAW_PERIOD = 0


def test_deposit(tester, operator, users):
    u = users[0]
    token = u.purse['eth'][0]
    # The operator isn't tracking our token yet
    assert not operator.is_tracking(token)
    
    deposit_time = tester.time
    u.deposit(token)
    assert token not in u.purse['eth']
    # Token is no longer in our eth purse
    # Wait for operator to see it and start tracking
    while not operator.is_tracking(token):
        assert tester.time < deposit_time + PLASMA_SYNC_PERIOD
        tester.mine(0)
    # Trading is now live
    assert token in u.purse['plasma']

def test_immediate_withdraw(tester, operator, users):
    u = users[0]
    token = u.purse['eth'][0]
    u.deposit(token)
    assert operator.is_tracking(token)
    u.withdraw(token)
    # Wait until the challenge period has elapsed
    while token.exit_started + PLASMA_WITHDRAW_PERIOD < tester.time:
        tester.mine(0)
    assert token in u.purse['eth']
    assert not operator.is_tracking(token)
    
def test_1trade_withdraw(tester, operator, users):
    u1, u2 = users[:2]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    # Wait for operator to signal trading is ready
    while not operator.is_tracking(token):
        tester.mine(0)
    # Send it to a different user
    u1.send(u2, token)
    assert token in u2.purse['plasma']
