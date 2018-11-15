from eth_utils import keccak, to_int


class ValidationError(Exception):
    pass


TREE_HEIGHT=160
EMPTY_VALUE=b'\x00' * 32
# keccak(EMPTY_VALUE)
EMPTY_LEAF_NODE_HASH = b')\r\xec\xd9T\x8bb\xa8\xd6\x03E\xa9\x888o\xc8K\xa6\xbc\x95H@\x08\xf66/\x93\x16\x0e\xf3\xe5c'


# sanity check
assert EMPTY_LEAF_NODE_HASH == keccak(EMPTY_VALUE)
EMPTY_NODE_HASHES = [EMPTY_LEAF_NODE_HASH]


hash_duplicate = lambda h: keccak(h + h)
# Branch for any value in an empty tree in root->leaf order
for _ in range(TREE_HEIGHT-1):
    EMPTY_NODE_HASHES.insert(0, hash_duplicate(EMPTY_NODE_HASHES[0]))


def validate_is_bytes(value):
    if not isinstance(value, bytes):
        raise ValidationError("Value is not of type `bytes`: got '{0}'".format(type(value)))


def validate_length(value, length):
    if len(value) != length:
        raise ValidationError("Value is of length {0}.  Must be {1}".format(len(value), length))


class SparseMerkleTree:
    def __init__(self, db={}):
        self.db = db
        # Initialize an empty tree with one branch
        self.root_hash = hash_duplicate(EMPTY_NODE_HASHES[0])
        self.db[self.root_hash] = EMPTY_NODE_HASHES[0] + EMPTY_NODE_HASHES[0]
        for i in range(TREE_HEIGHT - 1):
            self.db[EMPTY_NODE_HASHES[i]] = EMPTY_NODE_HASHES[i+1] + EMPTY_NODE_HASHES[i+1]
        self.db[EMPTY_LEAF_NODE_HASH] = EMPTY_VALUE

    def get(self, key):
        value, _ = self._get(key)
        return value
    
    def branch(self, key):
        _, branch = self._get(key)
        return branch

    def _get(self, key):
        """
        Returns db value and branch in root->leaf order
        """
        validate_is_bytes(key)
        validate_length(key, 20)
        branch = []

        target_bit = 1 << (TREE_HEIGHT - 1)
        path = to_int(key)
        node_hash = self.root_hash
        # Append the sibling to the branch
        # Iterate on the parent
        for i in range(TREE_HEIGHT):
            if path & target_bit:
                branch.append(self.db[node_hash][:32])
                node_hash = self.db[node_hash][32:]
            else:
                branch.append(self.db[node_hash][32:])
                node_hash = self.db[node_hash][:32]
            target_bit >>= 1

        return self.db[node_hash], branch

    def set(self, key, value):
        """
        Returns all updated hashes in root->leaf order
        """
        validate_is_bytes(key)
        validate_length(key, 20)
        validate_is_bytes(value)

        path = to_int(key)
        branch = self.branch(key)
        node = value
        proof_update = []

        target_bit = 1
        # branch is in root->leaf order, so flip
        for sibling in reversed(branch):
            # Set
            node_hash = keccak(node)
            proof_update.append(node_hash)
            self.db[node_hash] = node

            # Update
            if (path & target_bit):
                node = sibling + node_hash
            else:
                node = node_hash + sibling

            target_bit <<= 1

        self.root_hash = keccak(node)
        self.db[self.root_hash] = node
        # updates need to be in root->leaf order, so flip back
        return list(reversed(proof_update))

    def exists(self, key):
        validate_is_bytes(key)
        validate_length(key, 20)
        return (self.get(key) != EMPTY_VALUE)

    def delete(self, key):
        """
        Equals to setting the value to None
        """
        validate_is_bytes(key)
        validate_length(key, 20)

        self.set(key, EMPTY_VALUE)

    #
    # Dictionary API
    #
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __contains__(self, key):
        return self.exists(key)
