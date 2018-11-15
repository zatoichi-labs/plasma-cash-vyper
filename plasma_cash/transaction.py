from eth_utils import keccak

from rlp import encode, Serializable
from rlp.sedes import big_endian_int, text


class Transaction(Serializable):
    fields = (
        ('prevBlockNum', big_endian_int),
        ('tokenId', big_endian_int),
        ('newOwner', text),
    )

    def hash(self):
        return keccak(encode(self))


class SignedTransaction(Serializable):
    fields = (
        ('prevBlockNum', big_endian_int),
        ('tokenId', big_endian_int),
        ('newOwner', text),
        ('sigV', big_endian_int),
        ('sigR', big_endian_int),
        ('sigS', big_endian_int),
    )
