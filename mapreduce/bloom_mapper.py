#!/usr/bin/env python3
"""
MapReduce Job 1 - MAPPER : build Bloom filter in parallel
Input  : one blacklisted URL per line (from HDFS)
Output : <bit_position> \t 1     for each of the k hash positions
         __count__      \t 1     one per URL (to know n)
m and k come from env vars BLOOM_M and BLOOM_K (Hadoop: -cmdenv BLOOM_M=... -cmdenv BLOOM_K=...)
Self-contained on purpose: Hadoop Streaming ships only this file to each node.
"""
import hashlib
import os
import sys
from urllib.parse import urlsplit

M = int(os.environ["BLOOM_M"])
K = int(os.environ["BLOOM_K"])


def normalize(raw):                       # must match core/url_utils.normalize_url
    raw = raw.strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    p = urlsplit(raw)
    host = (p.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    full = host + p.path.rstrip("/")
    if p.query:
        full += "?" + p.query
    return full


def positions(item):                      # must match core/bloom_filter.bit_positions
    d = hashlib.md5(item.encode("utf-8")).digest()
    h1 = int.from_bytes(d[:8], "big")
    h2 = int.from_bytes(d[8:], "big") | 1
    return [(h1 + i * h2) % M for i in range(K)]


for line in sys.stdin:
    url = normalize(line)
    if not url:
        continue
    print("__count__\t1")
    for pos in positions(url):
        print(f"{pos}\t1")
