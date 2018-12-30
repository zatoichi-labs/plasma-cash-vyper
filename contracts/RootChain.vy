# External Contract Interface
contract ERC721:
    def safeTransferFrom(_from: address, _to: address, _tokenId: uint256): modifying
    def ownerOf(_tokenId: uint256) -> address: constant


# Operator Events
BlockPublished: event({
        blkRoot: bytes32,
    })

# Deposit Events
DepositAdded: event({ # struct Transaction
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
childChain: public(bytes32[uint256])
childChain_len: public(uint256) # Simulates stack data structure

deposits: public({ # struct Deposit
    depositor: address,
    depositBlk: uint256,
}[uint256]) # tokenId => Deposit

exits: { # struct Exit
    time: timestamp,
    txnBlkNum: uint256,
    txn: { # struct Transaction
        prevBlkNum: uint256,
        tokenId: uint256,
        newOwner: address,
        sigV: uint256,
        sigR: uint256,
        sigS: uint256
    },
    prevTxn: { # struct Transaction
        prevBlkNum: uint256,
        tokenId: uint256,
        newOwner: address,
        sigV: uint256,
        sigR: uint256,
        sigS: uint256
    },
    numChallenges: uint256,
    owner: address
}[uint256]  # tokenId => Exit (only one exit per tokenId at a time)

challenges: { # struct Challenge
    txn: { # struct Transaction
        prevBlkNum: uint256,
        tokenId: uint256,
        newOwner: address,
        sigV: uint256,
        sigR: uint256,
        sigS: uint256
    },
    challenger: address
}[uint256][uint256]  # tokenId => txnBlkNum => Challenge


# Constants
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)


# Constructor
@public
def __init__(_token: address):
    self.authority = msg.sender
    self.token = _token


## UTILITY FUNCTIONS
@constant
@public
def _getMerkleRoot(
    path: uint256,
    leaf: bytes32,
    proof: bytes32[256]
) -> bytes32:
    targetBit: uint256 = 1 # traverse path in LSB:leaf->MSB:root order
    proofElement: bytes32
    nodeHash: bytes32 = keccak256(leaf)  # First node is hash of leaf
    for i in range(256):
        proofElement = proof[255-i] # proof is in root->leaf order, so iterate in reverse
        if (bitwise_and(path, targetBit) > 0):
            nodeHash = keccak256(concat(proofElement, nodeHash))
        else:
            nodeHash = keccak256(concat(nodeHash, proofElement))
        targetBit = shift(targetBit, 1)
    return nodeHash


## Plasma functions
@public
def submitBlock(blkRoot: bytes32):
    assert msg.sender == self.authority
    self.childChain[self.childChain_len] = blkRoot
    self.childChain_len += 1
    log.BlockPublished(blkRoot)


@public
def deposit(
    # Expansion of transaction struct
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
):
    # Verify block number is current block
    assert self.childChain_len == txn_prevBlkNum

    # Verify this transaction was signed by message sender
    txn_hash: bytes32 = keccak256(
            concat(
                convert(txn_prevBlkNum, bytes32),
                convert(txn_tokenId, bytes32),
                convert(txn_newOwner, bytes32),
                convert(txn_sigV, bytes32),
                convert(txn_sigR, bytes32),
                convert(txn_sigS, bytes32),
            )
        )
    # FIXME Hack until signatures work
    assert msg.sender == convert(convert(txn_sigV, bytes32), address)#ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)

	# Transfer the token to this contract (also verifies custody)
    self.token.safeTransferFrom(msg.sender, self, txn_tokenId)

    # Allow recipient of deposit to withdraw the token
    # (No other spends can happen until confirmed)
    self.deposits[txn_tokenId] = {
        depositor: txn_newOwner,
        depositBlk: txn_prevBlkNum,
    }

    # Note: This will signal to the Plasma Operator to accept the deposit into the Child Chain
    log.DepositAdded(txn_prevBlkNum, txn_tokenId, txn_newOwner, txn_sigV, txn_sigR, txn_sigS)


# This will be the callback that token.safeTransferFrom() executes
@public
def onERC721Received(
    operator: address,
    _from: address,
    _tokenId: uint256,
    _data: bytes[1024],
) -> bytes32:
    # We must return the method_id of this function so that safeTransferFrom works
    return method_id("onERC721Received(address,address,uint256,bytes)", bytes32)


# Withdraw a deposit before the block is published
# NOTE Don't accept a deposited token until it's in a published block
@public
def withdraw(_tokenId: uint256):
    assert self.deposits[_tokenId].depositor == msg.sender
    assert self.deposits[_tokenId].depositBlk == self.childChain_len
    self.token.safeTransferFrom(self, msg.sender, _tokenId)
    del self.deposits[_tokenId]
    log.DepositCancelled(_tokenId, msg.sender)


@public
def startExit(
    # Expansion of transaction struct
    prevTxn_prevBlkNum: uint256,
    prevTxn_tokenId: uint256,
    prevTxn_newOwner: address,
    prevTxn_sigV: uint256,
    prevTxn_sigR: uint256,
    prevTxn_sigS: uint256,
    prevTxnProof: bytes32[256],
    # Expansion of transaction struct
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256]
):
    # Validate txn and parent are the same token
    assert prevTxn_tokenId == txn_tokenId

    # Validate caller is the owner of the exit txn
    assert txn_newOwner == msg.sender

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn_prevBlkNum, bytes32),
                    convert(txn_tokenId,    bytes32),
                    convert(txn_newOwner,   bytes32),
                    convert(txn_sigV, bytes32),
                    convert(txn_sigR, bytes32),
                    convert(txn_sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root prior to exit
    assert self.childChain[txn_prevBlkNum] == \
            self._getMerkleRoot(txn_tokenId, txnHash, txnProof)

    # Validate signer of txn was the receiver of prevTxn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn_sigV, bytes32), address)#ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)
    assert prevTxn_newOwner == txn_signer

    # Compute transaction hash (leaf of Merkle tree)
    prevTxnHash: bytes32 = keccak256(
            concat(
                    convert(prevTxn_prevBlkNum, bytes32),
                    convert(prevTxn_tokenId,    bytes32),
                    convert(prevTxn_newOwner,   bytes32),
                    convert(prevTxn_sigV, bytes32),
                    convert(prevTxn_sigR, bytes32),
                    convert(prevTxn_sigS, bytes32),
                )
            )

    # Validate inclusion of prevTxn in merkle root prior to txn
    assert self.childChain[prevTxn_prevBlkNum] == \
            self._getMerkleRoot(prevTxn_tokenId, prevTxnHash, prevTxnProof)

    # Validate the exit hasn't already been started
    assert self.exits[txn_tokenId].time == 0

    # Start the exit!
    #   struct Exit
    self.exits[txn_tokenId] = {
        time: block.timestamp,
        txnBlkNum: txnBlkNum,
        txn: {
            prevBlkNum: txn_prevBlkNum,
            tokenId: txn_tokenId,
            newOwner: txn_newOwner,
            sigV: txn_sigV,
            sigR: txn_sigR,
            sigS: txn_sigS
        },
        prevTxn: {
            prevBlkNum: prevTxn_prevBlkNum,
            tokenId: prevTxn_tokenId,
            newOwner: prevTxn_newOwner,
            sigV: prevTxn_sigV,
            sigR: prevTxn_sigR,
            sigS: prevTxn_sigS
        },
        numChallenges: 0,
        owner: msg.sender
    }

    # Announce the exit!
    log.ExitStarted(txn_tokenId, msg.sender)


@public
def challengeExit(
    # Expansion of transaction struct
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    # Validate the exit has already been started
    assert self.exits[txn_tokenId].time != 0

    # Double-check that they are dealing with the same tokenId
    assert self.exits[txn_tokenId].txn.tokenId == txn_tokenId

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn_prevBlkNum, bytes32),
                    convert(txn_tokenId,    bytes32),
                    convert(txn_newOwner,   bytes32),
                    convert(txn_sigV, bytes32),
                    convert(txn_sigR, bytes32),
                    convert(txn_sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root at challenge
    assert self.childChain[txnBlkNum] == \
            self._getMerkleRoot(txn_tokenId, txnHash, txnProof)

    # Get signer of challenge txn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn_sigV, bytes32), address)#ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)

    # Challenge transaction was spent after the exit
    challengeAfter: bool = (txnBlkNum > self.exits[txn_tokenId].txnBlkNum) and \
            (self.exits[txn_tokenId].txn.newOwner == txn_signer)

    # Challenge transaction was double spent between the parent and the exit
    challengeBetween: bool = (txnBlkNum <= self.exits[txn_tokenId].txn.prevBlkNum) and \
            (txnBlkNum > self.exits[txn_tokenId].prevTxn.prevBlkNum)
    # Waiting on #1075 to combine with ^
    challengeBetween = challengeBetween and \
            (self.exits[txn_tokenId].prevTxn.newOwner == txn_signer)

    # Challenge transaction is prior to parent, which is potentially forged history
    challengeBefore: bool = (txnBlkNum <= self.exits[txn_tokenId].prevTxn.prevBlkNum)

    if (challengeAfter or challengeBetween):
        # Cancel the exit!
        del self.exits[txn_tokenId]

        # Announce the exit was cancelled
        log.ExitCancelled(txn_tokenId, msg.sender)
    elif challengeBefore:
        # Log a new challenge!
        self.challenges[txn_tokenId][txnBlkNum] = {
            txn: {
                prevBlkNum: txn_prevBlkNum,
                tokenId: txn_tokenId,
                newOwner: txn_newOwner,
                sigV: txn_sigV,
                sigR: txn_sigR,
                sigS: txn_sigS
            },
            challenger: msg.sender
        }
        
        # Don't forget to increment the challenge counter!
        self.exits[txn_tokenId].numChallenges += 1

        # Announce the challenge!
        log.ChallengeStarted(txn_tokenId, txnBlkNum)


@public
def respondChallengeExit(
    # Expansion of transaction struct
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: uint256,
    txn_sigS: uint256,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    # Double-check that they are dealing with the same tokenId
    assert self.challenges[txn_tokenId][txn_prevBlkNum].txn.tokenId == txn_tokenId

    # Validate that the response is after the challenge
    assert self.challenges[txn_tokenId][txn_prevBlkNum].txn.prevBlkNum < txn_prevBlkNum

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn_prevBlkNum, bytes32),
                    convert(txn_tokenId,    bytes32),
                    convert(txn_newOwner,   bytes32),
                    convert(txn_sigV, bytes32),
                    convert(txn_sigR, bytes32),
                    convert(txn_sigS, bytes32),
                )
            )

    # Validate inclusion of txn in merkle root at response
    assert self.childChain[txnBlkNum] == \
            self._getMerkleRoot(txn_tokenId, txnHash, txnProof)

    # Get signer of response txn
    # FIXME Hack until signatures work
    txn_signer: address = convert(convert(txn_sigV, bytes32), address)#ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)

    # Validate signer of response txn is the recipient of the challenge txn
    assert self.challenges[txn_tokenId][txn_prevBlkNum].txn.newOwner == txn_signer

    # Remove the challenge
    del self.challenges[txn_tokenId][txnBlkNum]
    
    # Don't forget to increment the challenge counter!
    self.exits[txn_tokenId].numChallenges -= 1

    # Announce the challenge!
    log.ChallengeCancelled(txn_tokenId, txnBlkNum)


@public
def finalizeExit(tokenId: uint256):
    # Validate the challenge period is over
    assert self.exits[tokenId].time + CHALLENGE_PERIOD <= block.timestamp

    if self.exits[tokenId].numChallenges > 0:
        # Cancel the exit!
        del self.exits[tokenId]

        # Announce the exit was cancelled
        log.ExitCancelled(tokenId, msg.sender)
    else:
        # Validate the caller is the owner
        assert self.exits[tokenId].owner == msg.sender

        # Withdraw the token!
        self.token.safeTransferFrom(self, msg.sender, tokenId)

        # Announce the exit was cancelled
        log.ExitFinished(tokenId, msg.sender)
