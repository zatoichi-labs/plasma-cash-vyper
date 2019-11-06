from eth_abi import encode_single
from eth_account import Account
from eth_account.messages import encode_structured_data, _hash_eip191_message
from eth_utils import keccak, to_checksum_address, to_int


def is_signature(val):
    if not isinstance(val, tuple):
        return False
    if len(val) != 3:
        return False
    if not isinstance(val[0], int):
        return False
    if not isinstance(val[1], int):
        return False
    if not isinstance(val[2], int):
        return False
    return True


class Transaction:

    def __init__(self,
            chain_id,
            rootchain_address,
            prevBlkNum,
            tokenId,
            newOwner,
            sigV=None,
            sigR=None,
            sigS=None):
        self.chain_id = chain_id
        self.rootchain_address = rootchain_address
        self.newOwner = newOwner
        self.tokenId = tokenId
        self.prevBlkNum = prevBlkNum
        sig = (sigV, sigR, sigS)
        if is_signature(sig):
            self._signature = sig
        self._signature = None

    @property
    def signature(self):
        assert self._signature is not None, "Message is not signed!"
        return self._signature

    def add_signature(self, signature):
        assert is_signature(signature), "Not a valid signature!"
        assert self._signature is None, "Message has already been signed!"
        self._signature = signature

    @property
    def struct(self):
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Transaction": [
                    {"name":"newOwner", "type":"address"},
                    {"name":"tokenId", "type":"uint256"},
                    {"name":"prevBlkNum", "type":"uint256"},
                ]
            },
            "primaryType": "Transaction",
            "domain": {
                "name": "Plasma Cash",
                "version": "1",
                "chainId": self.chain_id,
                "verifyingContract": self.rootchain_address,
            },
            "message": {
                "newOwner": self.newOwner,
                "tokenId": self.tokenId,
                "prevBlkNum": self.prevBlkNum
            }
        }

    @property
    def msg(self):
        """ This is the message hash we sign for L2 transfers """
        return encode_structured_data(self.struct)

    @property
    def msg_hash(self):
        return _hash_eip191_message(self.msg)

    @property
    def signer(self):
        """ Get the signing account for this transaction """
        return Account.recover_message(self.msg, vrs=self.signature)

    @property
    def to_tuple(self):
        """ This is how we pass a struct through eth-abi for interacting with L1 """
        return (self.newOwner, self.tokenId, self.prevBlkNum, *self.signature)

    @property
    def to_bytes(self):
        """ This is how we pass a message through p2p channels """
        # Note we don't encode the domain separator, the receiver
        # must validate that each transaction is signed according
        # to the domain separator they are using.
        return encode_single(
                '(address,uint256,uint256,uint256,uint256,uint256)',
                self.to_tuple
            )
