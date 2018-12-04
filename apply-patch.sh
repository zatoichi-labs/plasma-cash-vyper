#!/usr/bin/bash

location=`pip show eth-tester | grep Location | sed 's/.*: //g'`

# Code size of RootChain is 46370, over the limit of 24576
patch -i <(echo "
13c13
< EIP170_CODE_SIZE_LIMIT = 24577
---
> EIP170_CODE_SIZE_LIMIT = 245770  # FIXME 10x'd this
") $location/evm/vm/forks/spurious_dragon/constants.py

# Gas deployment costs are higher than 3.14mgas
patch -i <(echo "
74c74
< GENESIS_GAS_LIMIT = 3141592
---
> GENESIS_GAS_LIMIT = 31415920 # FIXME 10x'd this
") $location/eth_tester/backends/pyevm/main.py
