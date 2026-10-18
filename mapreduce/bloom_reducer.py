#!/usr/bin/env python3
"""
MapReduce Job 1 - REDUCER (also used as COMBINER)
Input  : sorted <bit_position> \t <n>
Output : each unique bit position that must be 1, with how many URLs hit it
         __count__ \t <total URLs>
Safe as a combiner because sum is associative and commutative.
"""
import sys

cur, total = None, 0
for line in sys.stdin:
    key, val = line.rstrip("\n").split("\t")
    if key != cur:
        if cur is not None:
            print(f"{cur}\t{total}")
        cur, total = key, 0
    total += int(val)
if cur is not None:
    print(f"{cur}\t{total}")
