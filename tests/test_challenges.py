# Test 3 challenges in Plasma Cash design

def test_challengeAfter(rootchain, users):
    """
    A challenger notices a coin spend occured
    after a withdrawal was initiated
    """
    pass


def test_challengeBetween(rootchain, users):
    """
    A challenger notices a coin spend occured
    between the exit and the parent, where
    the exit occurs after the challenge
    (double spend attack)
    """
    pass


def test_challengeBefore_invalidHistory(rootchain, users):
    """
    A challenger notices a coin exit with
    invalid history, so they begin an interactive
    challenge with the exiting user to falsify the exit
    """
    pass


def test_challengeBefore_validHistory(rootchain, users):
    """
    A malicious challenger notices a coin exit with
    history they have, so they begin an interactive
    challenge with the exiting user to attempt to censor
    """
    pass
