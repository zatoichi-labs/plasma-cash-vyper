# Test 3 challenge types in Plasma Cash design
import pytest

from plasma_cash import (
    Token,
    Transaction,
    TokenStatus,
)

PLASMA_SYNC_PERIOD = 7
PLASMA_WITHDRAW_PERIOD = 7


def test_challengeAfter(w3, mine, operator, rootchain_contract, users):
    """
    A challenger notices a coin spend occured
    after a withdrawal was initiated
    """
    # Setup (u1 has tokens, u2, u3 does not)
    u1, u2, u3 = users[:3]
    token = u1.purse[0]
    # u1 deposits their token
    u1.deposit(token.uid)
    while not token.transferrable:
        mine()
        operator.monitor()  # FIXME Remove when async
        u1.monitor()  # FIXME Remove when async

    # u1 gives token to u2
    u1.transfer(u2.address, token.uid)
    u2.purse.append(token)  # FIXME Remove when messaging implementated
    logger = rootchain_contract.events.BlockPublished.createFilter(fromBlock=w3.eth.blockNumber)
    while len(logger.get_all_entries()) < 2:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u2 starts a withdrawal
    u2.withdraw(token.uid)
    u2.purse.remove(token)

    # u2 creates a token with no history of the withdrawal
    fake_token = Token(token.uid, status=TokenStatus.PLASMACHAIN, history=token.history)
    u2.purse.append(fake_token)

    # u2 sends the token to u3 (which is a withdrawal/spend conflict!)
    u2.transfer(u3.address, fake_token.uid)
    u3.purse.append(fake_token)  # FIXME Remove when messaging implementated
    while len(logger.get_all_entries()) < 3:
        mine()
        operator.monitor()  # FIXME Remove when async

    # We can submit last transaction as a challenge to withdrawal
    logger = rootchain_contract.events.ExitCancelled.createFilter(fromBlock=w3.eth.blockNumber)
    rootchain_contract.functions.challengeExit(
            fake_token.history[-1].to_tuple,
            operator.get_branch(fake_token.uid, fake_token.history[-1].prevBlkNum),
            fake_token.history[-1].prevBlkNum,
        ).transact()

    # Challenge was successful!
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid
    

def test_challengeBetween(w3, mine, operator, rootchain_contract, users):
    """
    A challenger notices a coin spend occured
    between the exit and the parent, where
    the exit occurs after the challenge
    (double spend attack)
    """
    # Setup (u1 has tokens, u2, u3 does not)
    u1, u2, u3 = users[:3]
    token = u1.purse[0]
    # u1 deposits their token
    u1.deposit(token.uid)
    while not token.transferrable:
        mine()
        operator.monitor()  # FIXME Remove when async
        u1.monitor()  # FIXME Remove when async

    # u1 gives token to u2
    u1.transfer(u2.address, token.uid)
    u2.purse.append(token)  # FIXME Remove when messaging implementated
    logger = rootchain_contract.events.BlockPublished.createFilter(fromBlock=w3.eth.blockNumber)
    while len(logger.get_all_entries()) < 2:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u2 actually has token, but u1/operator pretend transfer from u1 to u2 didn't happen
    operator.deposits[token.uid] = token.history[-2]  # operator colludes
    fake_token = Token(token.uid, status=token.status, history=token.history[:-1])
    u1.purse.append(fake_token)

    # u1 sends u3 a double-spent coin
    u1.transfer(u3.address, fake_token.uid)
    u3.purse.append(fake_token)  # FIXME Remove when messaging implementated
    while len(logger.get_all_entries()) < 3:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u3 withdraws it
    u3.withdraw(fake_token.uid)

    # We can submit the transaction before the doublespend as a challenge
    logger = rootchain_contract.events.ExitCancelled.createFilter(fromBlock=w3.eth.blockNumber)
    rootchain_contract.functions.challengeExit(
            token.history[-1].to_tuple,
            operator.get_branch(token.uid, token.history[-1].prevBlkNum),
            token.history[-1].prevBlkNum,
        ).transact()

    # Challenge was successful!
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid


def test_challengeBefore_invalidHistory(w3, mine, operator, rootchain_contract, users):
    """
    A challenger notices a coin exit with
    invalid history, so they begin an interactive
    challenge with the exiting user to falsify the exit
    """
    # Setup (u1 has tokens, u2, u3 does not)
    u1, u2, u3 = users[:3]
    token = u1.purse[0]
    # u1 deposits their token
    u1.deposit(token.uid)
    while not token.transferrable:
        mine()
        operator.monitor()  # FIXME Remove when async
        u1.monitor()  # FIXME Remove when async

    # u1 never sends the token to anyone

    # u2 makes a fake copy of u1's token deposited to themselves
    prevBlkNum = token.history[-1].prevBlkNum
    invalid_transaction = Transaction(
                w3.eth.chainId,
                rootchain_contract.address,
                prevBlkNum,
                token.uid,
                u2.address,
            )
    signature = u2._acct.sign_message(invalid_transaction.msg)
    invalid_transaction.add_signature((signature.v, signature.r, signature.s))

    operator.deposits[token.uid] = invalid_transaction  # operator colludes

    fake_token = Token(token.uid, status=token.status, history=[invalid_transaction])
    u2.purse.append(fake_token)

    # u2 sends it to u3 (who is colluding)
    u2.transfer(u3.address, fake_token.uid)
    u3.purse.append(fake_token)  # FIXME Remove when messaging implementated
    logger = rootchain_contract.events.BlockPublished.createFilter(fromBlock=w3.eth.blockNumber)
    while len(logger.get_all_entries()) < 2:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u3 sends it back
    u3.transfer(u2.address, fake_token.uid)
    u2.purse.append(fake_token)  # FIXME Remove when messaging implementated
    while len(logger.get_all_entries()) < 3:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u2 starts an exit
    u2.withdraw(fake_token.uid)

    # Someone challenges that with the correct history
    logger = rootchain_contract.events.ChallengeStarted.createFilter(fromBlock=w3.eth.blockNumber)
    rootchain_contract.functions.challengeExit(
            token.history[-1].to_tuple,
            operator.get_branch(token.uid, token.history[-1].prevBlkNum),
            token.history[-1].prevBlkNum,
        ).transact()

    # Interactive challenge started
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid

    # u2 can't respond to the challenge

    # after challenge period expires, token is no longer in withdrawal
    while w3.eth.blockNumber < 20:
        mine()
    logger = rootchain_contract.events.ExitCancelled.createFilter(fromBlock=w3.eth.blockNumber)
    u1.finalize(token.uid)

    # Challenge was successful!
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid


def test_challengeBefore_validHistory(w3, mine, operator, rootchain_contract, users):
    """
    A malicious challenger notices a coin exit with
    history they have, so they begin an interactive
    challenge with the exiting user to attempt to censor
    """
    # Setup (u1 has tokens, u2, u3 does not)
    u1, u2, u3 = users[:3]
    token = u1.purse[0]
    # u1 deposits their token
    u1.deposit(token.uid)
    while not token.transferrable:
        mine()
        operator.monitor()  # FIXME Remove when async
        u1.monitor()  # FIXME Remove when async

    # u1 gives token to u2
    u1.transfer(u2.address, token.uid)
    u2.purse.append(token)  # FIXME Remove when messaging implementated
    logger = rootchain_contract.events.BlockPublished.createFilter(fromBlock=w3.eth.blockNumber)
    while len(logger.get_all_entries()) < 2:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u2 has token, sends it to u3
    u2.transfer(u3.address, token.uid)
    u3.purse.append(token)  # FIXME Remove when messaging implementated
    while len(logger.get_all_entries()) < 3:
        mine()
        operator.monitor()  # FIXME Remove when async

    # u3 makes an valid transfer to u1
    u3.transfer(u1.address, token.uid)
    u1.purse.append(token)  # FIXME Remove when messaging implementated
    while len(logger.get_all_entries()) < 4:
        mine()
        operator.monitor()  # FIXME Remove when async

    u1.withdraw(token.uid)

    # Someone challenges that with older history
    logger = rootchain_contract.events.ChallengeStarted.createFilter(fromBlock=w3.eth.blockNumber)
    rootchain_contract.functions.challengeExit(
            token.history[0].to_tuple,
            operator.get_branch(token.uid, token.history[0].prevBlkNum),
            token.history[0].prevBlkNum,
        ).transact()

    # Interactive challenge started
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid

    # But history is real, so you respond and remove the challenge
    logger = rootchain_contract.events.ChallengeCancelled.createFilter(fromBlock=w3.eth.blockNumber)
    rootchain_contract.functions.respondChallenge(
            token.history[1].to_tuple,
            operator.get_branch(token.uid, token.history[1].prevBlkNum),
            token.history[0].prevBlkNum,
        ).transact()

    # Interactive challenge was responded!
    log = logger.get_all_entries()[0]
    assert log.args.tokenId == token.uid

    # We can withdraw our token (after the challenge period is over)!
    while w3.eth.blockNumber < 20:
        mine()
    u1.finalize(token.uid)
    assert not token.deposited
