# Structs
struct Deposit:
    depositor: address
    depositBlk: uint256

struct Transaction:
    newOwner: address
    tokenId: uint256
    prevBlkNum: uint256
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
        newOwner: address,
        tokenId: uint256,
        prevBlkNum: uint256,
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

# TxnBlkNum => BlkHash
# (Simulates stack data structure)
childChain: public(map(uint256, bytes32))
childChain_len: public(uint256)

# TokenId => Deposit
deposits: public(map(uint256, Deposit))

# TokenId => Exit (only one exit per tokenId allowed)
exits: map(uint256, Exit)

# TokenId => TxnBlkNum => Challenge
# (multiple challenges allowed, but only one per block)
challenges: map(uint256, map(uint256, Challenge))


# Constants
CHALLENGE_PERIOD: constant(timedelta) = 604800  # 7 days (7*24*60*60 secs)
CHAIN_ID: constant(uint256) = 61  # Must set dyanamically for chain being deployed to
# NOTE: CHAIN_ID must be monkeypatched for testing/testnets


# Constructor
@public
def __init__(_token: address):
    self.authority = msg.sender
    self.token = ERC721(_token)


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

@constant
@public
def _getTransactionHash(txn: Transaction) -> bytes32:
    # TODO: Use Vyper API from #1020 for this
    domainSeparator: bytes32 = keccak256(abi.encode(
            keccak256(
                "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
            ),
            keccak256("Plasma Cash"),  # EIP712 Domain: name
            keccak256("1"),            # EIP712 Domain: version
            CHAIN_ID,                  # EIP712 Domain: chainId (TODO: use EIP-1344)
            self                       # EIP712 Domain: verifyingContract
        ))
    messageHash: bytes32 = keccak256(abi.encode(
            keccak256("Transaction(address newOwner,uint256 tokenId,uint256 prevBlkNum)"),
            txn.newOwner,
            txn.tokenId,
            txn.prevBlkNum
        ))
    return keccak256(abi.encode(
            b"\x19\x01",
            domainSeparator,
            messageHash,
        ))


# Plasma functions #
@public
def submitBlock(blkRoot: bytes32):
    assert msg.sender == self.authority
    self.childChain[self.childChain_len] = blkRoot
    self.childChain_len += 1
    log.BlockPublished(blkRoot)


@public
def deposit(
    _from: address,
    _txn: Transaction
):
    # Verify block number is current block
    assert self.childChain_len == _txn.prevBlkNum

    # Verify this transaction was signed by message sender
    txnHash: bytes32 = self._getTransactionHash(_txn)
    assert _from == ecrecover(txnHash, _txn.sigV, _txn.sigR, _txn.sigS)

    # Transfer the token to this contract (also verifies custody)
    self.token.safeTransferFrom(_from, self, _txn.tokenId)

    # Allow recipient of deposit to withdraw the token
    # (No other spends can happen until confirmed)
    self.deposits[_txn.tokenId] = Deposit({
        depositor: _txn.newOwner,
        depositBlk: _txn.prevBlkNum,
    })

    # NOTE: This will signal to the Plasma Operator to
    #       accept the deposit into the Child Chain
    log.DepositAdded(_txn.newOwner,
                     _txn.tokenId,
                     _txn.prevBlkNum,
                     _txn.sigV,
                     _txn.sigR,
                     _txn.sigS)


# This will be the callback that token.safeTransferFrom() executes
@public
def onERC721Received(
    operator: address,
    _from: address,
    _tokenId: uint256,
    _data: bytes[161],  # Transaction struct is 161 bytes in size
) -> bytes32:
    # TODO: Add once #1406 implemented
    #assert operator == self.authority or operator == _from
    #txn: Transaction = abi.decode(_data, [Transaction])
    #assert _tokenId == txn.tokenId
    #self.deposit(_from, txn)
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
    prevTxn: Transaction,
    prevTxnProof: bytes32[256],
    txn: Transaction,
    txnProof: bytes32[256]
):
    # Validate txn and parent are the same token
    assert prevTxn.tokenId == txn.tokenId

    # Validate caller is the owner of the exit txn
    assert txn.newOwner == msg.sender

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = self._getTransactionHash(txn)

    # Validate inclusion of txn in merkle root prior to exit
    assert self.childChain[txn.prevBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Validate signer of txn was the receiver of prevTxn
    txn_signer: address = ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)
    assert prevTxn.newOwner == txn_signer

    # Compute transaction hash (leaf of Merkle tree)
    prevTxnHash: bytes32 = self._getTransactionHash(prevTxn)

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
    log.ExitStarted(txn.tokenId, msg.sender)


@public
def challengeExit(
    txn: Transaction,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    # Validate the exit has already been started
    assert self.exits[txn.tokenId].time != 0

    # Double-check that they are dealing with the same tokenId
    assert self.exits[txn.tokenId].txn.tokenId == txn.tokenId

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = self._getTransactionHash(txn)

    # Validate inclusion of txn in merkle root at challenge
    assert self.childChain[txnBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Get signer of challenge txn
    txn_signer: address = ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)

    # Challenge transaction was spent after the exit
    challengeAfter: bool = \
        (txnBlkNum >= self.exits[txn.tokenId].txnBlkNum) and \
        (self.exits[txn.tokenId].txn.newOwner == txn_signer)

    # Challenge transaction was double spent between the parent and the exit
    challengeBetween: bool = \
        (txnBlkNum < self.exits[txn.tokenId].txn.prevBlkNum) and \
        (txnBlkNum > self.exits[txn.tokenId].prevTxn.prevBlkNum) and \
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
    txn: Transaction,
    txnProof: bytes32[256],
    txnBlkNum: uint256
):
    challenge: Challenge = self.challenges[txn.tokenId][txnBlkNum]

    # Double-check that they are dealing with the same tokenId
    # NOTE txnBlkNum may need to be txn_prevBlkNum, not sure yet!
    assert challenge.txn.tokenId == txn.tokenId

    # Validate that the response is after the challenge
    # NOTE txnBlkNum may need to be txn_prevBlkNum, not sure yet!
    assert challenge.txn.prevBlkNum < txn.prevBlkNum

    # Compute transaction hash (leaf of Merkle tree)
    txnHash: bytes32 = self._getTransactionHash(txn)

    # Validate inclusion of txn in merkle root at response
    # NOTE txn_prevBlkNum may need to be txnBlkNum, not sure yet!
    assert self.childChain[txn.prevBlkNum] == \
        self._getMerkleRoot(txn.tokenId, txnHash, txnProof)

    # Get signer of response txn
    txn_signer: address = ecrecover(txnHash, txn.sigV, txn.sigR, txn.sigS)

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
