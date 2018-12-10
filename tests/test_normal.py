# Test normal operation of the Plasma chain (entries and exits)

PLASMA_SYNC_PERIOD = 7
PLASMA_WITHDRAW_PERIOD = 7


def test_deposit(tester, operator, users):
    u = users[0]
    token = u.purse[0]
    assert token.transferrable
    assert not token.deposited
    
    deposit_block_number = tester.time
    u.deposit(token)
    # Token is no longer in our eth purse
    assert token.deposited
    assert not token.transferrable
    # Wait for operator to see it and start tracking
    while not operator.is_tracking(token):
        assert tester.time < deposit_block_number + PLASMA_SYNC_PERIOD
        tester.mine()
    # Trading is now live
    assert token.deposited
    assert token.transferrable

def test_immediate_withdraw(tester, operator, users):
    u = users[0]
    token = u.purse[0]
    deposit_block_number = tester.time
    u.deposit(token)
    u.withdraw(token)
    # Validate there operator sees and ignores this deposit
    while deposit_block_number + PLASMA_SYNC_PERIOD < tester.time:
        tester.mine()
    assert not token.deposited
    assert token.transferrable
    
def test_1trade_withdraw(tester, operator, users):
    u1, u2 = users[:2]
    token = u1.purse[0]
    u1.deposit(token)
    # Wait for operator to signal trading is ready
    while not operator.is_tracking(token):
        tester.mine()
    assert token.transferrable
    # Send it to a different user
    u1.send(u2, token)
    assert token not in u1.purse
    assert token in u2.purse
    withdrawal_block_number = tester.time
    u2.withdraw(token)
    while withdrawal_block_number + PLASMA_WITHDRAW_PERIOD < tester.time:
        tester.mine()
    u2.finalize(token)
    assert not token.deposited
    assert token.transferrable
