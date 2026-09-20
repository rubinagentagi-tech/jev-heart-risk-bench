#!/usr/bin/env bash
# Fetch the raw CDC BRFSS 2015 survey file and unpack it.
# Public domain US federal government data (17 U.S.C. 105).
set -euo pipefail
mkdir -p data && cd data
curl -sSL -o LLCP2015XPT.zip "https://www.cdc.gov/brfss/annual_data/2015/files/LLCP2015XPT.zip"
unzip -o LLCP2015XPT.zip
chmod u+rw LLCP2015.XPT
echo "done: $(ls -lh LLCP2015.XPT)"
