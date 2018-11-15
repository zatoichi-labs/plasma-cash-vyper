# Test normal operation of the Plasma chain (entries and exits)

def test_deposit(rootchain, users):
    u = users[0]
    total_coins = len(u.eth_purse)
    u.deposit()
    assert len(u.eth_purse) == total_coins - 1
    assert len(u.plasma_purse) == 1
    e = rootchain.events.Deposit

def test_immediate_withdraw(rootchain, users):
    u = users[0]
    total_coins = len(u.eth_purse)
    u.deposit()
    u.withdraw()
    assert len(u.eth_purse) == total_coins
    
def test_1trade_withdraw(rootchain, users):
    u1, u2 = users[:2]
    u1.deposit()
    token = u1.plasma_purse[0]
    u1.send(u2)
    assert token in u2.plasma_purse
    u2.withdraw()
    assert token in u2.eth_purse
