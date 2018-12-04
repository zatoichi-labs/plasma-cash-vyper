#!/usr/bin/bash

location=`pip show eth-tester | grep Location | sed 's/.*: //g'`
patch -i py-evm.patch $location/evm/vm/forks/spurious_dragon/constants.py
patch -i eth-tester.patch $location/eth_tester/backends/pyevm/main.py
