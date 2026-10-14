#!/bin/sh
set -eu
mkdir -p /logs/verifier
# Reward, not the shell exit code, is the grading contract.
if python /tests/test_headers.py; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
