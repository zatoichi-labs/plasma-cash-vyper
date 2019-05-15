from eth_abi import encode_single
from eth_account import Account
from eth_account.messages import encode_structured_data, hash_eip712_message
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
            contract_address,
            prevBlkNum,
            tokenId,
            newOwner):
        self.chain_id = chain_id
        self.contract_address = contract_address
        self.newOwner = newOwner
        self.tokenId = tokenId
        self.prevBlkNum = prevBlkNum
        self.signature = None

    def add_signature(self, signature):
        assert is_signature(signature), "Not a valid signature!"
        assert self.signature is None, "Message has already been signed!"
        self.signature = signature

    @property
    def struct(self):
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
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
                "chainId": to_int(hexstr=self.chain_id),
                "verifyingContract": self.contract_address
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
        return hash_eip712_message(self.struct)

    @property
    def signer(self):
        """ Get the signing account for this transaction """
        assert self.signature is not None, "Transaction is not signed!"
        return Account.recover_message(self.msg, vrs=self.signature)

    @property
    def to_tuple(self):
        """ This is how we pass a struct through eth-abi for interacting with L1 """
        assert self.signature is not None, "Transaction is not signed!"
        return (self.prevBlkNum, self.tokenId, self.newOwner, *self.signature)

    @property
    def to_bytes(self):
        """ This is how we pass a message through p2p channels """
        # Note we don't encode the domain separator, the receiver
        # must validate that each transaction is signed according
        # to the domain separator they are using.
        return encode_single(
                '(uint256,uint256,address,uint256,uint256,uint256)',
                self.to_tuple
            )
