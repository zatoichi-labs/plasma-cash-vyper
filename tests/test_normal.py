# Test normal operation of the Plasma chain (entries and exits)
from plasma_cash import Token

PLASMA_SYNC_PERIOD = 7
PLASMA_WITHDRAW_PERIOD = 7


def test_deposit(w3, mine, operator, users):
    # A user has a coin on the rootchain
    u = users[0]
    t = u.purse[0]
    assert t.transferrable
    assert not t.deposited

    # They deposit it
    u.deposit(t.uid)
    deposit_block_number = w3.eth.blockNumber

    # Token is no longer tradable
    assert t.deposited
    assert not t.transferrable

    # Wait for operator to see it and start tracking
    while not t.transferrable:
        # Operator should publish block and start tracking deposit within sync period
        assert w3.eth.blockNumber - deposit_block_number <= PLASMA_SYNC_PERIOD
        mine()  # TODO Make mining async
        operator.monitor()  # FIXME Remove when async
        u.monitor()  # FIXME Remove when async

    # Trading is now live on plasmachain
    assert t.deposited
    assert t.transferrable
    assert operator.is_tracking(t.uid)

def test_immediate_withdraw(w3, mine, operator, users):
    # A user deposits a coin
    u = users[0]
    t = u.purse[0]
    u.deposit(t.uid)
    deposit_block_number = w3.eth.blockNumber

    # That user initiates an immediate withdrawal
    # (before it has been included in a plasma block)
    u.withdraw(t.uid)

    # Validate the operator ignores this deposit until the next block is published
    while w3.eth.blockNumber - deposit_block_number <= PLASMA_SYNC_PERIOD:
        assert not t.deposited
        assert t.transferrable
        assert not operator.is_tracking(t.uid)
        mine()  # TODO Make mining async
        operator.monitor()  # FIXME Remove when async

def test_1trade_withdraw(w3, mine, operator, users):
    # Two users
    u1, u2 = users[:2]
    # User 1 deposits a coin
    t = u1.purse[0]
    u1.deposit(t.uid)
    deposit_block_number = w3.eth.blockNumber

    # Wait for operator to signal trading is ready
    while not t.transferrable:
        assert w3.eth.blockNumber - deposit_block_number <= PLASMA_SYNC_PERIOD
        mine()  # TODO Make mining async
        operator.monitor()  # FIXME Remove when async
        u1.monitor()  # FIXME Remove when async
    assert operator.is_tracking(t.uid)

    # Send it to the other user
    u1.transfer(u2.address, t.uid)
    assert t not in u1.purse
    u2.purse.append(t)  # FIXME Remove when messaging implementated
    assert t in u2.purse

    # Have to wait for the block to sync again
    while w3.eth.blockNumber - deposit_block_number <= PLASMA_SYNC_PERIOD:
        assert t.deposited
        assert t.transferrable
        mine()  # TODO Make mining async
        operator.monitor()  # FIXME Remove when async

    # The second user can withdraw it
    withdrawal_block_number = w3.eth.blockNumber
    u2.withdraw(t.uid)
    while w3.eth.blockNumber - withdrawal_block_number <= PLASMA_SYNC_PERIOD:
        assert not t.deposited
        assert not t.transferrable
        mine()  # TODO Make mining async
        operator.monitor()  # FIXME Remove when async

    # Coin should be available again on the rootchain
    u2.finalize(t.uid)  # FIXME Remove when async
    assert not t.deposited
    assert t.transferrable
    operator.monitor()  # FIXME Remove when async
    assert not operator.is_tracking(t.uid)
