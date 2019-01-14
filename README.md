# Plasma Cash

*Plasma Cash is Plasma*

## Overview

This is a Vyper implementation of Plasma Cash.
The work is derivative of implementations of Plasma Cash from
[Loom](https://github.com/loomnetwork/plasma-cash),
[OmiseGO](https://github.com/omisego/plasma-cash),
and the Plasma MVP implementation written in Vyper from
[LayerX](https://github.com/LayerXcom/plasma-mvp-vyper).
It only works with ERC721 tokens, and is optimized for that.

It serves as the basis for our
[PlasmaRifle](https://github.com/GunClear/PlasmaRifle) bridge, although significant
modifications are made in that project for the sake of supporting zkSNARKs and
GunClear's specific requirements for that project.

Contributions welcome!

## Actor and Asset Model

Plasma Cash lets users put tokenized assets (represented by NFTs) into a subchain
framework, where the token can be traded cheaper and faster, due to it's reliance
on one or more trusted intermediaries to facilitate the tracking of those assets.

There are two types of actors in Plasma Cash designs:
1. Users, or token holders and traders
2. Operator(s), or Plasma chain transaction consensus managers

There is only one type of asset that is allowed to be traded, which is represented
by an NFT, although any upstream assets can be tokenized and traded in the Plasma
chain. The [Root Chain Manager](contracts/RootChain.vy) contract manages the
upstream assets, as well as how they enter and exit the Plasma subchain network.
NFTs are used because their unique identifiers allow for efficient proofs of
inclusion in subchain transaction Merkle tree roots, which follow the ownership
transitions. More technical information on these design choices is available in
[this](https://github.com/loomnetwork/plasma-paper/raw/master/plasma_cash.pdf)
paper, written by Georgios Konstantopoulos of Loom Network.

## Trust Model

Plasma Cash acheives higher transactional throughput and economic efficiency
through a loosening of it's trust model: namely, that the operator(s) of the
subchain network have full authority to compress all transactions to short,
efficient hashes represented by the root of a Sparse Merkle Tree data structure.
The users trust that the operators upload roots that accurately summarize all
trading information, and do not include fradulent transactions that make invalid
state transitions of the assets they are holding in the Plasmachain network.

There is some mitigation to this trust assertion, in that if another user tries
to exit a token with history that violates the pre-determined rules for valid
transactions, other users may block that exit from occuring (this holds for the
operator as well). This mitigates invalid state transitions and other incorrect
behaviors from occuring as this exit process is bonded during the challenge
period that all exits undergo before ownerships is recovered on the root chain.

## Requirements

### Definitions

Formally, there are two actors and one asset in the Plasma Cash system.
The actors will be represented as the "User" and the "Operator", and the asset
as the "Token".

There are two Networks in the Plasma Cash systme; the Rootchain network, under
which the underlying assets that are tokenized into the system are issued, and
the Plasmachain network, under which the Tokens that were deposited on the
Rootchain are allowed to traded according to the rules in the smart contract
that governs the Plasma system.

There is one parameter in the Plasma Cash system: the "Plasma Exit Period",
which corresponds to the period of time in which challenges to an exit can be
processed before a Token can be withdrawn from the Rootchain contract.

---

"Invalid History" refers to history which is not correctly transferred between
a sender and receiver in the series of transactions since the Token entered the
Plasmachain network; or if any of those transactions is not a member of the data
that the operator uploads.
"Invalid Exits" refer to any Token exit that violates one (or more) of the
following rules:
1. Exit of a spent Token (challenge is a valid transaction after exit)
2. Exit of a double-spent Token (challenge is a valid transaction spending parent
   before exit)
3. Exit of a Token with forged history (challenge is a valid transaction before parent)

Challenges of types 1) and 2) will immediately cancel the exit, however challenges
of type 3) can be disproven by showing a valid transaction spending the challenge.
Only Tokens with no outstanding Challenges can be withdrawn after the Plasma Exit
Period has elapsed.

---

The following is the features each actor relies on to exercise their rights
within the network.

### Users

1. `@req u1`
   A User can deposit a Token into the Rootchain contract, and have it be made
   made available to trade immediately
2. `@req u2`
   A User must be able to trade Tokens within the Plasma chain, and observe that
   trade reflected in the uploaded Merkle Tree root that the operator maintains
3. `@req u3`
   A User should track history of owned Tokens
4. `@req u4`
   A User must validate history of Tokens they receive from other Users
5. `@req u5`
   A User must be able to withdraw Tokens they own, and reclaim them within the
   Plasma exit period
6. `@req u6`
   A User must challenge all exits that violate their current token ownership
7. `@req u7`
   A User should challenge any exits that violate other's token ownership history

### Operators

1. `@req o1`
   The Operator must locally store all transaction information for the Plasmachain
2. `@req o2`
   The Operator must upload a Merkle Tree root summarizing all transactions at most
   once within the Plasma Sync Period
3. `@req o3`
   The Operator should service User requests to obtain information about their Tokens
4. `@req o4`
   The Operator should challenge Token all exits that are invalid
