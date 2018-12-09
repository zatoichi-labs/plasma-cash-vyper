import pytest

from plasma_cash import (
    Token,
)

# Test 3 challenges in Plasma Cash design
PLASMA_WITHDRAW_PERIOD = 0


def test_challengeAfter(tester, operator, rootchain, users):
    """
    A challenger notices a coin spend occured
    after a withdrawal was initiated
    """
    # Setup
    u1, u2, u3 = users[:3]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    while not operator.is_tracking(token):
        tester.mine()
    u1.send(u2, token)

    u2.withdraw(token)
    # u2 creates a token with no history of withdrawal
    fake_token = Token(token.uid, history=list(token.history))
    print(rootchain.exits)  # rootchain.exits is mutated for some reason
    # u2 starts a withdrawal
    # u2 sends the fake token to u3
    u2.purse['withdraw'].remove(token)
    u2.purse['plasma'].append(fake_token)
    u2.send(u3, fake_token)
    print(rootchain.exits)
    assert rootchain.challengeExit(fake_token)  # Challenge was successful!
    

def test_challengeBetween(rootchain, tester, operator, users):
    """
    A challenger notices a coin spend occured
    between the exit and the parent, where
    the exit occurs after the challenge
    (double spend attack)
    """
    # Setup
    u1, u2, u3 = users[:3]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    while not operator.is_tracking(token):
        tester.mine()
    u1.send(u2, token)

    # u2 actually has token, we remove transfer from u1 to u2
    fake_token = Token(token.uid, history=list(token.history[:-1]))
    u1.purse['plasma'].append(fake_token)
    u1.send(u3, fake_token)
    u3.withdraw(fake_token)
    assert rootchain.challengeExit(token)  # Challenge was successful!


def test_challengeBefore_invalidHistory(rootchain, tester, operator, users):
    """
    A challenger notices a coin exit with
    invalid history, so they begin an interactive
    challenge with the exiting user to falsify the exit
    """
    # Setup
    u1, u2, u3 = users[:3]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    while not operator.is_tracking(token):
        tester.mine()
    u1.send(u2, token)

    # u2 actually has token, we remove transfer from u1 to u2
    fake_token = Token(token.uid, history=list(token.history[:-1]))
    # u1 makes an invalid transfer to u3
    u1.purse['plasma'].append(fake_token)
    # u1 sends it to u3 (who is colluding)
    u1.send(u3, fake_token)
    # u3 sends it back
    u3.send(u1, fake_token)
    # u1 exits
    u1.withdraw(fake_token)
    # Someone challenges that
    assert not rootchain.challengeExit(token)  # Challenge can be responded to
    assert not u1.finalize(token)  # Exit failed, challenge succeeded


def test_challengeBefore_validHistory(tester, operator, rootchain, users):
    """
    A malicious challenger notices a coin exit with
    history they have, so they begin an interactive
    challenge with the exiting user to attempt to censor
    """
    # Setup
    u1, u2, u3 = users[:3]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    while not operator.is_tracking(token):
        tester.mine()
    u1.send(u2, token)

    # u2 has token, sends it to u3
    u2.send(u3, token)
    # u3 makes an valid transfer to u1
    u3.send(u1, token)
    u1.withdraw(token)
    # Someone challenges that
    assert not rootchain.challengeExit(token)  # Challenge can be responded to
    # But history is real, so you can respond and remove it
    rootchain.respondChallenge(token)
    assert u1.finalize(token)  # Exit was successful!
