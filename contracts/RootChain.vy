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
childChain_len: uint256 # Simulates stack data structure

exits: { # struct Exit
    time: timestamp,
    txnBlkNum: uint256,
    txn: { # struct Transaction
        blkNum: uint256,
        txn: { # struct Transfer
            prevBlkNum: uint256,
            tokenId: uint256,
            newOwner: address,
            sigV: uint256,
            sigR: bytes32,
            sigS: bytes32
        }
    },
    prevTxn: { # struct Transaction
        prevBlkNum: uint256,
        tokenId: uint256,
        newOwner: address,
        sigV: uint256,
        sigR: bytes32,
        sigS: bytes32
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
        sigR: bytes32,
        sigS: bytes32
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
                    convert(txn_tokenId, bytes32),
                    convert(txn_newOwner, bytes32)
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
        data: bytes[1024]
    ) -> bytes32:

    # Sanity check that the token contract is depositing
    assert self.token.ownerOf(_tokenId) == self

    # Plasmachain transaction is provided through custom data
    self.deposit(
            _from,
            _tokenId,
            convert(slice(data, start=0,   len=32), uint256),
            convert(slice(data, start=32,  len=32), uint256),
            convert(slice(data, start=64,  len=20), address),
            convert(slice(data, start=84,  len=2),  uint256),
            convert(slice(data, start=86,  len=32), bytes32),
            convert(slice(data, start=118, len=32), bytes32)
        )

    # We must return the method_id of this function so that safeTransferFrom works
    return method_id("onERC721Received(address,address,uint256,bytes)", bytes32)


