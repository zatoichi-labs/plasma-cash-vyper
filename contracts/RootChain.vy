# Custom Types
types = {
    # NOTE: Transaction should be modified to match plasma-chain needs
    Transaction: {
        prevBlock: uint256,
        tokenId: uint256,
        newOwner: address
        __sig__: RSV_SECP256K1  # signature field,
        # struct can be ecrecovered to obtain signer's address
    },
    Exit: {
        time: timestamp,
        txnBlkNum: uint256,
        txn: types.Transaction,
        prevTxn: types.Transaction,
        owner: address
    },
    Challenge: {
        txn: types.Transaction,
        challenger: address
    }
}


# Events
Deposit: event({
        depositor: address,
        amount: uint256,
        uid: uint256
    })

ExitStarted: event({
        tokenId: uint256,
        owner: address
    })

ExitFinished: event({
        tokenId: uint256,
        owner: address
    })

ExitCancelled: event({
        tokenId: uint256,
        challenger: address
    })

ChallengeStarted: event({
        tokenId: uint256,
        challengeBlkNum: address
    })

ChallengeRemoved: event({
        tokenId: uint256,
        challengeBlkNum: uint256
    })


# Storage vars
authority: public(address)
token: public(ERC721)
blkNum: public(uint256)
childChain: Stack(bytes32)
exits: types.Exit[uint256]
challenges: types.Challenge[uint256][uint256]

# Constants
CHALLENGE_PERIOD: constant(timedelta) = 7 days


@public
def __init__():
    self.authority = msg.sender


@public
def submitBlock(txnRoot: bytes32):
    assert msg.sender == self.authority
    self.childChain.push(txnRoot)
    self.blkNum += 1


@private
def deposit(from: address, tokenId: uint256, txn: types.Transaction):

    # First validate that the transaction is consistent with the deposit
    assert txn.prevBlock == self.blkNum
    assert txn.tokenId == tokenId
    assert txn.newOwner == from

    # Allow depositor to withdraw their current token (No other spends)
    txnRoot: bytes32 = getMerkleRoot(txn, tokenId, emptyMerkleBranch(256)))
    self.childChain.push(txnRoot)
    self.blkNum += 1

    # Note: This signals Plasma Operator to create UTXO in child chain
    log.Deposit(from, tokenId)


# Used in lieu of a `deposit()` function
@public
def onERC721Received(
        operator: address,
        from: address,
        tokenId: uint256,
        data: bytes[1024]
    ) -> bytes32:

    # Sanity check that only token contract can deposit
    assert msg.sender == self.token

    # NOTE: Plasmachain Transaction is added through extra data here
    txn: types.Transaction = convert(data, types.Transaction)
    self.deposit(from, tokenId, txn)

    # Must return the method_id of this function so the safeTokenTransfer function knows it worked
    return method_id("onERC721Received(address,address,uint256,bytes)", bytes32)


#FIXME: Exitor must place a bond
@public
def startExit(
        prevTxn: types.Transaction,
        prevTxnProof: MerkleProof[256],
        txn: types.Transaction,
        txnProof: MerkleProof[256],
        txnBlkNum: uint256
    ):
    # The exit transaction block number is after the one before it, but before the current
    assert self.blkNum > txnBlkNum > txn.prevBlock

    # The exit transaction and the one before it deal with the same token
    assert prevTxn.tokenId == txn.tokenId

    # The transaction recipient before the last transaction signed the exit transaction
    assert prevTxn.newOwner == get_signer(txn)

    # The submitter of this exit owns the token currently
    assert msg.sender == txn.newOwner

    # Validate the transaction prior to the exit transaction is included in the merkle
    # root for that block using getMerkleRoot(value, key, path)
    # hash the (key: value) pair together, traverse the proof, return the last hash
    assert self.childChain[txn.prevBlock] == \
            getMerkleRoot(keccak256(prevTxn), prevTxn.tokenId, prevTxnProof)

    # Validate the exit transaction is included in the merkle root for the provided block
    assert self.childChain[txnBlkNum] == getMerkleRoot(keccak256(txn), txn.tokenId, txnProof)

    # Validate no exit has already been started for tokenId
    assert self.exits[txn.tokenId].owner == ZERO_ADDRESS

    # Allow token to start the exit process (zero pending challenges
    exit = types.Exit(block.timestamp, txnBlkNum, txn, prevTxn, msg.sender)
    self.exits[txn.tokenId] = exit
    log.ExitStarted(txn.tokenId, msg.sender)


# 3 types of Plasma Cash Challenges
# 1) Provide a proof of a transaction spending (cancels the exit)
#FIXME: Slash exiter's bond
@public
def challengeAfter(
        txn: types.Transaction,
        txnProof: MerkleProof[256],
        txnBlkNum: uint256
    ):
    # Get the exit we are talking about (could be empty)
    parent: types.Exit = self.exits[txn.tokenId]

    # The challenge transaction block number is after the exit
    assert txnBlkNum > exit.txn.prevBlkNum

    # The exit transaction and the challenge transaction deal with the same token
    assert exit.txn.tokenId == txn.tokenId

    # The exit transaction recipient signed the challenge transaction
    assert exit.txn.newOwner == get_signer(txn)

    # Validate the challenge transaction is included in the merkle root for the provided block
    assert self.childChain[txnBlkNum] == getMerkleRoot(keccak256(txn), txn.tokenId, txnProof)

    # Log the cancelled exit
    del self.exits[txn.tokenId]
    log.ExitCancelled(txn.tokenId, msg.sender)


# 2) Provide a proof of a transaction spending P(C) that appears before C (cancels the exit)
#FIXME: Slash exiter's bond
@public
def challengeBetween(
        txn: types.Transaction,
        txnProof: MerkleProof[256],
        txnBlkNum: uint256
    ):
    # Get the exit we are talking about (could be empty)
    parent: types.Exit = self.exits[txn.tokenId]

    # The challenge transaction block number is before the exit, but after the parent of the spend
    assert exit.txn.prevBlock >= txnBlkNum > exit.prevTxn.prevBlock

    # The parent transaction and the challenge deal with the same token
    assert exit.prevTxn.tokenId == txn.tokenId

    # The exit transaction recipient signed the challenge transaction
    # NOTE: Double-spend!
    assert exit.prevTxn.newOwner == get_signer(txn)

    # Validate the challenge transaction is included in the merkle root for the provided block
    assert self.childChain[txnBlkNum] == getMerkleRoot(keccak256(txn), txn.tokenId, txnProof)

    # Log the cancelled exit
    del self.exits[txn.tokenId]
    log.ExitCancelled(txn.tokenId, msg.sender)


# 3) Provide a proof of a transaction C* in the coin's history before P(C) (Does not cancel)
#FIXME: Challenger must place bond
@public
def challengeBefore(
        txn: types.Transaction,
        txnProof: MerkleProof[256],
        txnBlkNum: uint256
    ):
    # Get the exit we are talking about (could be empty)
    exit: types.Exit = self.exits[txn.tokenId]

    # The challenge transaction block number is before the parent of the exit transaction
    assert exit.prevTxn.prevBlkNum >= txnBlkNum

    # The challenge transaction block number is before the exit transaction
    assert exit.txnBlkNum > txnBlkNum > exit.txn.prevBlock

    # The exit transaction and the challenge transaction deal with the same token
    assert exit.prevTxn.tokenId == txn.tokenId

    # The exit transaction recipient signed the challenge transaction
    assert exit.prevTxn.newOwner == get_signer(txn)

    # Validate the challenge transaction is included in the merkle root for the provided block
    assert self.childChain[txnBlkNum] == getMerkleRoot(keccak256(txn), txn.tokenId, txnProof)

    # Reset the challenge timer
    self.exits[txn.tokenId].time = block.timestamp

    # Add the challenge to the exit
    self.challenges[txn.tokenId][txnBlkNum] = types.Challenge(txn, msg.sender)
    log.ChallengeStarted(txn.tokenId, txnBlkNum)

# Only challengeBefore can be disputed
#FIXME: Slash challenger's bond
@public
def respondChallengeBefore(
        txn: types.Transaction,
        txnProof: MerkleProof[256],
        txnBlkNum: uint256,
        challengeBlkNum: uint256
    ):
    # Get the exit we are talking about (could be empty)
    parent: types.Exit = self.exits[txn.tokenId]

    # Get the challenge we are talking about (could also be empty)
    challenge: types.Challenge = self.challenges[txn.tokenId][challengeBlkNum]

    # The challenge response block number is before the parent of the exit
    # transaction, but after the challenge
    assert exit.prevTxn.prevBlkNum >= txnBlkNum > challengeBlkNum

    # The exit transaction and the challenge transaction deal with the same token
    assert challenge.txn.tokenId == txn.tokenId

    # The recipient of the challenge transaction signed the response transaction
    assert challenge.txn.newOwner == get_signer(txn)

    # Validate the challenge transaction is included in the merkle root for the provided block
    assert self.childChain[txnBlkNum] == getMerkleRoot(keccak256(txn), txn.tokenId, txnProof)

    # Reset the challenge timer
    self.exits[txn.tokenId].time = block.timestamp

    # Declare the challenge invalidated
    log.ChallengeRemoved(txn.tokenId, challenge.challenger)


#FIXME: Slash or return exiter's bond (depending on challenge state)
@public
def finishExit(tokenId: uint256):
    # Get the exit we are talking about
    exit: types.Transaction = self.exits[tokenId]

    # Validate that exit time has elapsed
    assert block.timestamp >= exit.time + CHALLENGE_PERIOD

    # Remove token from list of exits
    del self.exits[tokenId]

    if exit_valid:
        # Validate that caller is the address that opened the exit
        assert exit.owner == msg.sender

        # Send the token to that owner
        self.token.safeTransferFrom(self, exit.owner, tokenId)
        log.ExitFinished(tokenId, msg.sender)
        # Deal with returning bond here
    #else:
    # Deal with slashing bond here
