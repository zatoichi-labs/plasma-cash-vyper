# External Contract Interface
contract ERC721:
    def safeTransferFrom(_from: address, _to: address, _tokenId: uint256): modifying
    def ownerOf(_tokenId: uint256) -> address: constant


# Deposit/Exit Events
Deposit: event({tokenId: uint256, owner: address, txnHash: bytes32})
ExitStarted: event({tokenId: uint256, owner: address})
ExitFinished: event({tokenId: uint256, owner: address})

# Challenge Events
ExitCancelled: event({tokenId: uint256, challenger: address})
ChallengeStarted: event({tokenId: uint256, blkNum: uint256})
ChallengeCancelled: event({tokenId: uint256, blkNum: uint256})


# Storage
authority: address
token: public(ERC721)
childChain: bytes32[uint256]
childChain_len: public(uint256) # Simulates stack data structure

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

empty_merkle_branch: bytes32[256]


# Constants
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)

# Constructor
@public
def __init__(_token: address):
    self.authority = msg.sender
    self.token = _token

    last_node: bytes32 = keccak256(convert(0, bytes32))
    self.empty_merkle_branch[255] = last_node
    
    for i in range(255):
        last_node = keccak256(concat(last_node, last_node))
        self.empty_merkle_branch[254-i] = last_node
        

## UTILITY FUNCTIONS
@constant
@private
def _getMerkleRoot(
    leaf: bytes32,
    path: uint256,
    proof: bytes32[256] # kwarg in a built-in function
) -> bytes32:
    index: uint256 = path
    computedHash: bytes32 = leaf
    for proofElement in proof:
        if (index % 2 == 0):
            computedHash = keccak256(concat(computedHash, proofElement))
        else:
            computedHash = keccak256(concat(proofElement, computedHash))
        index /= 2
    return computedHash

## Plasma functions
@public
def submitBlock(blkRoot: bytes32):
    assert msg.sender == self.authority
    self.childChain[self.childChain_len] = blkRoot
    self.childChain_len += 1

@private
def deposit(
    _from: address,
    _tokenId: uint256,
    # Expansion of transaction struct
    txn_prevBlkNum: uint256,
    txn_tokenId: uint256,
    txn_newOwner: address,
    txn_sigV: uint256,
    txn_sigR: bytes32,
    txn_sigS: bytes32
):
    # First validate that the transaction is consistent with the deposit
    assert txn_prevBlkNum == self.childChain_len
    assert txn_tokenId == _tokenId
    assert txn_newOwner == _from

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = keccak256(
            concat(
                    convert(txn_prevBlkNum, bytes32),
                    convert(txn_tokenId,    bytes32),
                    convert(txn_newOwner,   bytes32)
                )
            )
    # Allow depositor to withdraw their current token (No other spends happen)
    blkRoot: bytes32 = self._getMerkleRoot(txnHash, _tokenId, self.empty_merkle_branch)
    self.childChain[self.childChain_len] = blkRoot
    self.childChain_len += 1

    # Note: This will signal to the Plasma Operator to accept the deposit into the Child Chain
    log.Deposit(_tokenId, _from, txnHash)

# Used in lieu of `deposit()` function for ERC721
@public
def onERC721Received(
    operator: address,
    _from: address,
    _tokenId: uint256,
    data: bytes[150]
) -> bytes32:

    # Sanity check that the token contract is depositing
    assert self.token.ownerOf(_tokenId) == self

    # Plasmachain transaction is provided through custom data
    self.deposit(
            _from,
            _tokenId,
            # Double convert is workaround for #1072
            convert(convert(slice(data, start=  0, len=32), bytes32), uint256),
            # Double convert is workaround for #1072
            convert(convert(slice(data, start= 32, len=32), bytes32), uint256),
            # Convert to address doesn't work, #1074
            convert(slice(data, start= 64, len=20), address),
            # Double convert is workaround for #1072
            convert(convert(slice(data, start= 84, len= 2), bytes32), uint256),
            convert(slice(data, start= 86, len=32), bytes32),
            convert(slice(data, start=118, len=32), bytes32)
        )

    # We must return the method_id of this function so that safeTransferFrom works
    return method_id("onERC721Received(address,address,uint256,bytes)", bytes32)

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
    txnProof: bytes32[256],
    txnBlkNum: uint256
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
                    convert(txn_newOwner,   bytes32)
                )
            )

    # Validate inclusion of txn in merkle root prior to exit
    assert self.childChain[txnBlkNum] == \
            self._getMerkleRoot(txnHash, txn_tokenId, txnProof)

    # Validate signer of txn was the receiver of prevTxn
    txn_signer: address = ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)
    assert prevTxn_newOwner == txn_signer

    # Compute transaction hash (leaf of Merkle tree)
    prevTxnHash: bytes32 = keccak256(
            concat(
                    convert(prevTxn_prevBlkNum, bytes32),
                    convert(prevTxn_tokenId,    bytes32),
                    convert(prevTxn_newOwner,   bytes32)
                )
            )

    # Validate inclusion of prevTxn in merkle root prior to txn
    assert self.childChain[txn_prevBlkNum] == \
            self._getMerkleRoot(prevTxnHash, prevTxn_tokenId, prevTxnProof)

    # Validate the exit hasn't already been started
    assert self.exits[txn_tokenId].time == 0

    # Start the exit!
    #   struct Exit
    self.exits[txn_tokenId].time = block.timestamp
    self.exits[txn_tokenId].txnBlkNum = txnBlkNum
    #       struct Transaction
    self.exits[txn_tokenId].txn.prevBlkNum = txn_prevBlkNum
    self.exits[txn_tokenId].txn.tokenId = txn_tokenId
    self.exits[txn_tokenId].txn.newOwner = txn_newOwner
    self.exits[txn_tokenId].txn.sigV = txn_sigV
    self.exits[txn_tokenId].txn.sigR = txn_sigR
    self.exits[txn_tokenId].txn.sigS = txn_sigS
    #       struct Transaction
    self.exits[prevTxn_tokenId].prevTxn.prevBlkNum = prevTxn_prevBlkNum
    self.exits[prevTxn_tokenId].prevTxn.tokenId = prevTxn_tokenId
    self.exits[prevTxn_tokenId].prevTxn.newOwner = prevTxn_newOwner
    self.exits[prevTxn_tokenId].prevTxn.sigV = prevTxn_sigV
    self.exits[prevTxn_tokenId].prevTxn.sigR = prevTxn_sigR
    self.exits[prevTxn_tokenId].prevTxn.sigS = prevTxn_sigS
    self.exits[prevTxn_tokenId].numChallenges = 0
    self.exits[prevTxn_tokenId].owner = msg.sender

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
                    convert(txn_newOwner,   bytes32)
                )
            )

    # Validate inclusion of txn in merkle root at challenge
    assert self.childChain[txnBlkNum] == \
            self._getMerkleRoot(txnHash, txn_tokenId, txnProof)

    # Get signer of challenge txn
    txn_signer: address = ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)

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
        #   struct Exit
        self.exits[txn_tokenId].time = 0
        self.exits[txn_tokenId].txnBlkNum = 0
        #       struct Transaction
        self.exits[txn_tokenId].txn.prevBlkNum = 0
        self.exits[txn_tokenId].txn.tokenId = 0
        self.exits[txn_tokenId].txn.newOwner = ZERO_ADDRESS
        self.exits[txn_tokenId].txn.sigV = 0
        self.exits[txn_tokenId].txn.sigR = 0
        self.exits[txn_tokenId].txn.sigS = 0
        #       struct Transaction
        self.exits[txn_tokenId].prevTxn.prevBlkNum = 0
        self.exits[txn_tokenId].prevTxn.tokenId = 0
        self.exits[txn_tokenId].prevTxn.newOwner = ZERO_ADDRESS
        self.exits[txn_tokenId].prevTxn.sigV = 0
        self.exits[txn_tokenId].prevTxn.sigR = 0
        self.exits[txn_tokenId].prevTxn.sigS = 0
        self.exits[txn_tokenId].numChallenges = 0
        self.exits[txn_tokenId].owner = ZERO_ADDRESS

        # Announce the exit was cancelled
        log.ExitCancelled(txn_tokenId, msg.sender)
    elif challengeBefore:
        # Log a new challenge!
        #   struct Challenge
        #       struct Transaction
        self.challenges[txn_tokenId][txnBlkNum].txn.prevBlkNum = txn_prevBlkNum
        self.challenges[txn_tokenId][txnBlkNum].txn.tokenId = txn_tokenId
        self.challenges[txn_tokenId][txnBlkNum].txn.newOwner = txn_newOwner
        self.challenges[txn_tokenId][txnBlkNum].txn.sigV = txn_sigV
        self.challenges[txn_tokenId][txnBlkNum].txn.sigR = txn_sigR
        self.challenges[txn_tokenId][txnBlkNum].txn.sigS = txn_sigS
        self.challenges[txn_tokenId][txnBlkNum].challenger = msg.sender
        
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
                    convert(txn_newOwner,   bytes32)
                )
            )

    # Validate inclusion of txn in merkle root at response
    assert self.childChain[txnBlkNum] == \
            self._getMerkleRoot(txnHash, txn_tokenId, txnProof)

    # Get signer of response txn
    txn_signer: address = ecrecover(txnHash, txn_sigV, txn_sigR, txn_sigS)

    # Validate signer of response txn is the recipient of the challenge txn
    assert self.challenges[txn_tokenId][txn_prevBlkNum].txn.newOwner == txn_signer

    # Remove the challenge
    #   struct Challenge
    #       struct Transaction
    self.challenges[txn_tokenId][txnBlkNum].txn.prevBlkNum = 0
    self.challenges[txn_tokenId][txnBlkNum].txn.tokenId = 0
    self.challenges[txn_tokenId][txnBlkNum].txn.newOwner = ZERO_ADDRESS
    self.challenges[txn_tokenId][txnBlkNum].txn.sigV = 0
    self.challenges[txn_tokenId][txnBlkNum].txn.sigR = 0
    self.challenges[txn_tokenId][txnBlkNum].txn.sigS = 0
    self.challenges[txn_tokenId][txnBlkNum].challenger = ZERO_ADDRESS
    
    # Don't forget to increment the challenge counter!
    self.exits[txn_tokenId].numChallenges -= 1

    # Announce the challenge!
    log.ChallengeCancelled(txn_tokenId, txnBlkNum)

@public
def finalizeExit(tokenId: uint256):
    # Validate the exit has already been started
    assert self.exits[tokenId].time != 0

    # Validate the challenge period is over
    assert block.timestamp > self.exits[tokenId].time + CHALLENGE_PERIOD

    if self.exits[tokenId].numChallenges > 0:
        # Cancel the exit!
        #   struct Exit
        self.exits[tokenId].time = 0
        self.exits[tokenId].txnBlkNum = 0
        #       struct Transaction
        self.exits[tokenId].txn.prevBlkNum = 0
        self.exits[tokenId].txn.tokenId = 0
        self.exits[tokenId].txn.newOwner = ZERO_ADDRESS
        self.exits[tokenId].txn.sigV = 0
        self.exits[tokenId].txn.sigR = 0
        self.exits[tokenId].txn.sigS = 0
        #       struct Transaction
        self.exits[tokenId].prevTxn.prevBlkNum = 0
        self.exits[tokenId].prevTxn.tokenId = 0
        self.exits[tokenId].prevTxn.newOwner = ZERO_ADDRESS
        self.exits[tokenId].prevTxn.sigV = 0
        self.exits[tokenId].prevTxn.sigR = 0
        self.exits[tokenId].prevTxn.sigS = 0
        self.exits[tokenId].numChallenges = 0
        self.exits[tokenId].owner = ZERO_ADDRESS

        # Announce the exit was cancelled
        log.ExitCancelled(tokenId, msg.sender)
    else:
        # Validate the caller is the owner
        assert self.exits[tokenId].owner == msg.sender

        # Withdraw the token!
        self.token.safeTransferFrom(self, msg.sender, tokenId)

        # Announce the exit was cancelled
        log.ExitFinished(tokenId, msg.sender)
