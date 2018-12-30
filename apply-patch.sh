#!/usr/bin/bash

location=`pip show eth-tester | grep Location | sed 's/.*: //g'`

# Gas deployment costs are higher than 3.14mgas
patch -i <(echo "
81c81
< GENESIS_GAS_LIMIT = 3141592
---
> GENESIS_GAS_LIMIT = 6283184 # FIXME 2x'd this from 3141592
") $location/eth_tester/backends/pyevm/main.py
