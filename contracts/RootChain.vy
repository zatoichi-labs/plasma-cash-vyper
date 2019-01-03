# Structs
struct Deposit:
    depositor: address
    depositBlk: uint256

struct Transaction:
    prevBlkNum: uint256
    tokenId: uint256
    newOwner: address
    sigV: uint256
    sigR: uint256
    sigS: uint256

struct Exit:
    time: timestamp
    txnBlkNum: uint256
    txn: Transaction
    prevTxn: Transaction
    numChallenges: uint256
    owner: address

struct Challenge:
    txn: Transaction
    challenger: address


# External Contract Interface
contract ERC721:
    def safeTransferFrom(_from: address,
                         _to: address,
                         _tokenId: uint256): modifying

    def ownerOf(_tokenId: uint256) -> address: constant


# Operator Events
BlockPublished: event({
        blkRoot: bytes32,
    })

# Deposit Events
DepositAdded: event({  # struct Transaction
        prevBlkNum: uint256,
        tokenId: uint256,
        newOwner: address,
        sigV: uint256,
        sigR: uint256,
        sigS: uint256,
    })

# Withdrawal Events
DepositCancelled: event({
        tokenId: uint256,
        owner: address,
    })
ExitStarted: event({
        tokenId: uint256,
        owner: address,
    })
ExitFinished: event({
        tokenId: uint256,
        owner: address,
    })

# Challenge Events
ExitCancelled: event({
        tokenId: uint256,
        challenger: address,
    })
ChallengeStarted: event({
        tokenId: uint256,
        blkNum: uint256,
    })
ChallengeCancelled: event({
        tokenId: uint256,
        blkNum: uint256,
    })


# Storage
authority: address
token: public(ERC721)
# Simulates stack data structure
childChain: public(map(uint256, bytes32))
childChain_len: public(uint256)
# tokenId => Deposit
deposits: public(map(uint256, Deposit))
# tokenId => Exit (only one exit per tokenId allowed)
exits: map(uint256, Exit)
# tokenId => txnBlkNum => Challenge (multiple challenges allowed)
challenges: map(uint256, map(uint256, Challenge))


# Constants
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)


# Constructor
@public
def __init__(_token: address):
    self.authority = msg.sender
    self.token = _token


# UTILITY FUNCTIONS #
@constant
@public
def _getMerkleRoot(
    path: uint256,
    leaf: bytes32,
    proof: bytes32[256]
) -> bytes32:
    targetBit: uint256 = 1  # traverse path in LSB:leaf->MSB:root order
    proofElement: bytes32
    nodeHash: bytes32 = keccak256(leaf)  # First node is hash of leaf
    for i in range(256):
        # proof is in root->leaf order, so iterate in reverse
        proofElement = proof[255-i]
        if (bitwise_and(path, targetBit) > 0):
            nodeHash = keccak256(concat(proofElement, nodeHash))
        else:
            nodeHash = keccak256(concat(nodeHash, proofElement))
        targetBit = shift(targetBit, 1)
    return nodeHash


# Plasma functions #
@public
def submitBlock(blkRoot: bytes32):
    assert msg.sender == self.authority
    self.childChain[self.childChain_len] = blkRoot
    self.childChain_len += 1
    log.BlockPublished(blkRoot)


@public
def deposit(
    # Expansion of transaction struct (await VIP 1019)
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
):
    # Temporary until VIP 1019 is implemented
    txn: Transaction = Transaction({
        prevBlkNum: txn_prevBlkNum,
        tokenId: txn_tokenId,
        newOwner: txn_newOwner,
        sigV: txn_sigV,
        sigR: txn_sigR,
        sigS: txn_sigS,
    })

    # Verify block number is current block
    assert self.childChain_len == txn.prevBlkNum

    # Verify this transaction was signed by message sender
    txn_hash: bytes32 = keccak256(
            concat(
                convert(txn.prevBlkNum, bytes32),
                convert(txn.tokenId, bytes32),
                convert(txn.newOwner, bytes32),
                convert(txn.sigV, bytes32),
                convert(txn.sigR, bytes32),
                convert(txn.sigS, bytes32),
            )
        )
    # FIXME Hack until signatures work
    assert msg.sender == convert(convert(txn.sigV, bytes32), address)#ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)

    # Transfer the token to this contract (also verifies custody)
    self.token.safeTransferFrom(msg.sender, self, txn.tokenId)

    # Allow recipient of deposit to withdraw the token
    # (No other spends can happen until confirmed)
    self.deposits[txn.tokenId] = Deposit({
        depositor: txn.newOwner,
        depositBlk: txn.prevBlkNum,
    })

    # NOTE: This will signal to the Plasma Operator to
    #       accept the deposit into the Child Chain
    log.DepositAdded(txn.prevBlkNum,
                     txn.tokenId,
                     txn.newOwner,
                     txn.sigV,
                     txn.sigR,
                     txn.sigS)


# This will be the callback that token.safeTransferFrom() executes
@public
def onERC721Received(
    operator: address,
    _from: address,
    _tokenId: uint256,
    _data: bytes[1024],
) -> bytes32:
    # We must return the method_id of this function so safeTransferFrom works
    return method_id(
            "onERC721Received(address,address,uint256,bytes)", bytes32
        )


# Withdraw a deposit before the block is published
# NOTE Don't accept a deposited token until it's in a published block
@public
def withdraw(_tokenId: uint256):
    assert self.deposits[_tokenId].depositor == msg.sender
    assert self.deposits[_tokenId].depositBlk == self.childChain_len
    self.token.safeTransferFrom(self, msg.sender, _tokenId)
    clear(self.deposits[_tokenId])
    log.DepositCancelled(_tokenId, msg.sender)


@public
def startExit(
    # Expansion of transaction struct (await VIP 1019)
    prevTxn_prevBlkNum: uint256,
    prevTxn_tokenId: uint256,
    prevTxn_newOwner: address,
    prevTxn_sigV: uint256,
    prevTxn_sigR: uint256,
    prevTxn_sigS: uint256,
    prevTxnProof: bytes32[256],
    # Expansion of transaction struct (await VIP 1019)
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256]
):
    # Temporary until VIP 1019 is implemented
    txn: Transaction = Transaction({
        prevBlkNum: txn_prevBlkNum,
        tokenId: txn_tokenId,
        newOwner: txn_newOwner,
        sigV: txn_sigV,
        sigR: txn_sigR,
        sigS: txn_sigS,
    })

    # Temporary until VIP 1019 is implemented
    prevTxn: Transaction = Transaction({
        prevBlkNum: prevTxn_prevBlkNum,
        tokenId: prevTxn_tokenId,
        newOwner: prevTxn_newOwner,
        sigV: prevTxn_sigV,
        sigR: prevTxn_sigR,
        sigS: prevTxn_sigS,
    })

    # Validate txn and parent are the same token
    assert prevTxn.tokenId == txn.tokenId

    # Validate caller is the owner of the exit txn
    assert txn.newOwner == msg.sender

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn.prevBlkNum, bytes32),
                    convert(txn.tokenId,    bytes32),
                    convert(txn.newOwner,   bytes32),
                    convert(txn.sigV, bytes32),
                    convert(txn.sigR, bytes32),
                    convert(txn.sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root prior to exit
    assert self.childChain[txn.prevBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Validate signer of txn was the receiver of prevTxn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn.sigV, bytes32), address)#ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)
    assert prevTxn.newOwner == txn_signer

    # Compute transaction hash (leaf of Merkle tree)
    prevTxnHash: bytes32 = keccak256(
            concat(
                    convert(prevTxn.prevBlkNum, bytes32),
                    convert(prevTxn.tokenId,    bytes32),
                    convert(prevTxn.newOwner,   bytes32),
                    convert(prevTxn.sigV, bytes32),
                    convert(prevTxn.sigR, bytes32),
                    convert(prevTxn.sigS, bytes32),
                )
            )

    # Validate inclusion of prevTxn in merkle root prior to txn
    assert self.childChain[prevTxn.prevBlkNum] == \
        self._getMerkleRoot(prevTxn.tokenId, prevTxnHash, prevTxnProof)

    # Validate the exit hasn't already been started
    assert self.exits[txn.tokenId].time == 0

    # Start the exit!
    self.exits[txn.tokenId] = Exit({
        time: block.timestamp,
        txnBlkNum: txn.prevBlkNum+1,
        txn: txn,
        prevTxn: prevTxn,
        numChallenges: 0,
        owner: msg.sender
    })

    # Announce the exit!
    log.ExitStarted(txn_tokenId, msg.sender)


@public
def challengeExit(
    # Expansion of transaction struct (await VIP 1019)
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    # Temporary until VIP 1019 is implemented
    txn: Transaction = Transaction({
        prevBlkNum: txn_prevBlkNum,
        tokenId: txn_tokenId,
        newOwner: txn_newOwner,
        sigV: txn_sigV,
        sigR: txn_sigR,
        sigS: txn_sigS,
    })

    # Validate the exit has already been started
    assert self.exits[txn.tokenId].time != 0

    # Double-check that they are dealing with the same tokenId
    assert self.exits[txn.tokenId].txn.tokenId == txn.tokenId

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn.prevBlkNum, bytes32),
                    convert(txn.tokenId,    bytes32),
                    convert(txn.newOwner,   bytes32),
                    convert(txn.sigV, bytes32),
                    convert(txn.sigR, bytes32),
                    convert(txn.sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root at challenge
    assert self.childChain[txnBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Get signer of challenge txn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn.sigV, bytes32), address)#ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)

    # Challenge transaction was spent after the exit
    challengeAfter: bool = \
        (txnBlkNum >= self.exits[txn.tokenId].txnBlkNum) and \
        (self.exits[txn.tokenId].txn.newOwner == txn_signer)

    # Challenge transaction was double spent between the parent and the exit
    challengeBetween: bool = \
        (txnBlkNum < self.exits[txn.tokenId].txn.prevBlkNum) and \
        (txnBlkNum > self.exits[txn.tokenId].prevTxn.prevBlkNum)
    # Waiting on #1075 to combine with ^
    challengeBetween = challengeBetween and \
        (self.exits[txn.tokenId].prevTxn.newOwner == txn_signer)

    # Challenge transaction is prior to parent, which might be forged
    challengeBefore: bool = \
        (txnBlkNum < self.exits[txn.tokenId].prevTxn.prevBlkNum)

    assert challengeAfter or challengeBetween or challengeBefore

    if (challengeAfter or challengeBetween):
        # Cancel the exit!
        clear(self.exits[txn.tokenId])

        # Announce the exit was cancelled
        log.ExitCancelled(txn.tokenId, msg.sender)
    else:  # challengeBefore
        # Log a new challenge!
        self.challenges[txn.tokenId][txnBlkNum] = Challenge({
            txn: txn,
            challenger: msg.sender
        })

        # Don't forget to increment the challenge counter!
        self.exits[txn.tokenId].numChallenges += 1

        # Announce the challenge!
        log.ChallengeStarted(txn.tokenId, txnBlkNum)


@public
def respondChallenge(
    # Expansion of transaction struct (await VIP 1019)
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    # Temporary until VIP 1019 is implemented
    txn: Transaction = Transaction({
        prevBlkNum: txn_prevBlkNum,
        tokenId: txn_tokenId,
        newOwner: txn_newOwner,
        sigV: txn_sigV,
        sigR: txn_sigR,
        sigS: txn_sigS,
    })

    challenge: Challenge = self.challenges[txn.tokenId][txnBlkNum]

    # Double-check that they are dealing with the same tokenId
    # NOTE txnBlkNum may need to be txn_prevBlkNum, not sure yet!
    assert challenge.txn.tokenId == txn.tokenId

    # Validate that the response is after the challenge
    # NOTE txnBlkNum may need to be txn_prevBlkNum, not sure yet!
    assert challenge.txn.prevBlkNum < txn.prevBlkNum

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn.prevBlkNum, bytes32),
                    convert(txn.tokenId,    bytes32),
                    convert(txn.newOwner,   bytes32),
                    convert(txn.sigV, bytes32),
                    convert(txn.sigR, bytes32),
                    convert(txn.sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root at response
    # NOTE txn_prevBlkNum may need to be txnBlkNum, not sure yet!
    assert self.childChain[txn.prevBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Get signer of response txn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn.sigV, bytes32), address)#ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)

    # Validate signer of response txn is the recipient of the challenge txn
    # NOTE txnBlkNum may need to be txn_prevBlkNum, not sure yet!
    #      (this means that respond points to challenge)
    assert challenge.txn.newOwner == txn_signer

    # Remove the challenge
    clear(self.challenges[txn.tokenId][txnBlkNum])

    # Don't forget to increment the challenge counter!
    self.exits[txn.tokenId].numChallenges -= 1

    # Announce the challenge!
    log.ChallengeCancelled(txn.tokenId, txnBlkNum)


@public
def finalizeExit(tokenId: uint256):
    # Validate the challenge period is over
    assert self.exits[tokenId].time + CHALLENGE_PERIOD <= block.timestamp

    if self.exits[tokenId].numChallenges > 0:
        # Cancel the exit!
        clear(self.exits[tokenId])

        # Announce the exit was cancelled
        log.ExitCancelled(tokenId, msg.sender)
    else:
        # Validate the caller is the owner
        assert self.exits[tokenId].owner == msg.sender

        # Clear the exit
        clear(self.exits[tokenId])

        # Withdraw the token!
        self.token.safeTransferFrom(self, msg.sender, tokenId)

        # Announce the exit was cancelled
        log.ExitFinished(tokenId, msg.sender)
