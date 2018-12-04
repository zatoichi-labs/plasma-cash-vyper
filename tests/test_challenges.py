import copy
import pytest

# Test 3 challenges in Plasma Cash design
PLASMA_WITHDRAW_PERIOD = 0


@pytest.fixture
def setup(operator, users):
    u1, u2, u3 = users[:3]
    token = u1.purse['eth'][0]
    u1.deposit(token)
    while not operator.is_tracking(token):
        tester.mine(0)
    u1.send(u2, token)
    return u1, u2, u3, token


def test_challengeAfter(rootchain, setup):
    """
    A challenger notices a coin spend occured
    after a withdrawal was initiated
    """
    _, u2, u3, token = setup
    fake_token = copy.deepcopy(token)
    u2.send(u3, token)
    u2.purse['plasma'].append(fake_token)
    u2.withdraw(fake_token)
    assert rootchain.challengeExit(token)  # Challenge was successful!
    

def test_challengeBetween(rootchain, setup):
    """
    A challenger notices a coin spend occured
    between the exit and the parent, where
    the exit occurs after the challenge
    (double spend attack)
    """
    u1, u2, u3, token = setup
    fake_token = copy.deepcopy(token)
    fake_token.history.pop()  # Remove transfer from u1 to u2
    u1.purse['plasma'].append(fake_token)
    u1.send(u3, fake_token)
    u3.withdraw(fake_token)
    assert rootchain.challengeExit(token)  # Challenge was successful!


def test_challengeBefore_invalidHistory(rootchain, setup):
    """
    A challenger notices a coin exit with
    invalid history, so they begin an interactive
    challenge with the exiting user to falsify the exit
    """
    u1, u2, u3, token = setup
    fake_token = copy.deepcopy(token)
    # u2 has token
    # u3 makes an invalid transfer to u1
    u3.purse['plasma'].append(fake_token)
    u3.send(u1, fake_token)
    # u1 exits
    u1.withdraw(fake_token)
    # Someone challenges that
    assert not rootchain.challengeExit(token)  # Challenge can be responded to
    assert not u2.finalize(token)  # Exit failed, assume challenge succeeded


def test_challengeBefore_validHistory(rootchain, setup):
    """
    A malicious challenger notices a coin exit with
    history they have, so they begin an interactive
    challenge with the exiting user to attempt to censor
    """
    u1, u2, u3, token = setup
    # u2 has token, sends it to u3
    u2.send(u3, token)
    # u3 makes an valid transfer to u1
    u3.send(u1, token)
    u1.withdraw(token)
    # Someone challenges that
    assert not rootchain.challengeExit(token)  # Challenge can be responded to
    # But history is real, so you can respond and remove it
    rootchain.respondChallenge(token)
    assert u3.finalize(token)  # Exit was successful!
