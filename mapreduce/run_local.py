"""
Runs both MapReduce jobs LOCALLY, simulating what Hadoop does:
  1. split input into blocks (like HDFS 128 MB blocks, here smaller)
  2. run a mapper on each block           (map phase)
  3. run the combiner on each mapper output (local aggregation)
  4. shuffle & sort by key                  (shuffle phase)
  5. run the reducer                        (reduce phase)
Then builds data/bloom.bin from Job 1 output and data/scam_stats.json from Job 2.

On a real cluster use the commands in README.md instead - the mapper/reducer files are the same.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.bloom_filter import BloomFilter, optimal_params  # noqa: E402

MR = os.path.join(ROOT, "mapreduce")
DATA = os.path.join(ROOT, "data")
BLOCK_LINES = 10_000          # lines per "HDFS block" in this simulation
TARGET_FP = 0.01


def run(script, text, env=None):
    p = subprocess.run([sys.executable, os.path.join(MR, script)], input=text,
                       capture_output=True, text=True, env=env)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout


def mapreduce_job(name, lines, mapper, combiner, reducer, env=None):
    t0 = time.time()
    blocks = [lines[i:i + BLOCK_LINES] for i in range(0, len(lines), BLOCK_LINES)]
    print(f"\n[{name}]  input: {len(lines):,} lines -> {len(blocks)} blocks/splits")
    combined, map_records, comb_records = [], 0, 0
    for i, block in enumerate(blocks, 1):
        mapped = run(mapper, "".join(block), env)
        map_records += mapped.count("\n")
        local = run(combiner, "".join(sorted(mapped.splitlines(keepends=True))), env)
        comb_records += local.count("\n")
        combined.extend(local.splitlines(keepends=True))
    print(f"  map     : {map_records:,} records emitted by {len(blocks)} mappers")
    print(f"  combine : {comb_records:,} records after combiner "
          f"({100 - comb_records / max(map_records, 1) * 100:.1f}% less network traffic)")
    shuffled = sorted(combined, key=lambda l: l.split("\t")[0])
    print(f"  shuffle : {len(shuffled):,} records sorted by key")
    out = run(reducer, "".join(shuffled), env)
    print(f"  reduce  : {out.count(chr(10)):,} output records  ({time.time() - t0:.1f}s)")
    return out


def main(input_path=os.path.join(DATA, "blacklist.txt")):
    with open(input_path) as f:
        lines = [l if l.endswith("\n") else l + "\n" for l in f if l.strip()]
    n = len(lines)
    m, k = optimal_params(n, TARGET_FP)
    print(f"Blacklist size n = {n:,}  ->  Bloom m = {m:,} bits ({m / 8 / 1024:.1f} KB), k = {k}")
    env = dict(os.environ, BLOOM_M=str(m), BLOOM_K=str(k))

    # ---- Job 1: Bloom filter ----
    out1 = mapreduce_job("JOB 1: build Bloom filter", lines,
                         "bloom_mapper.py", "bloom_reducer.py", "bloom_reducer.py", env)
    build_bloom_from_output(out1, m, k)

    # ---- Job 2: analytics ----
    out2 = mapreduce_job("JOB 2: scam-link analytics", lines,
                         "stats_mapper.py", "stats_reducer.py", "stats_reducer.py")
    stats = {"tld": {}, "brand": {}, "lure": {}}
    for line in out2.splitlines():
        key, val = line.split("\t")
        kind, name = key.split(":", 1)
        stats[kind][name] = int(val)
    for kind in stats:
        stats[kind] = dict(sorted(stats[kind].items(), key=lambda x: -x[1])[:10])
    stats["total_urls"] = n
    with open(os.path.join(DATA, "scam_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print("\nTop impersonated brands:", ", ".join(list(stats["brand"])[:5]))
    print("Saved data/scam_stats.json")


def build_bloom_from_output(out, m, k):
    bf = BloomFilter(m, k)
    for line in out.splitlines():
        key, val = line.split("\t")
        if key == "__count__":
            bf.count = int(val)
        else:
            bf.set_bit(int(key))
    bf.save(os.path.join(DATA, "bloom.bin"), os.path.join(DATA, "bloom_meta.json"))
    print(f"  -> Bloom filter saved: data/bloom.bin ({bf.memory_bytes() / 1024:.1f} KB), "
          f"{bf.fill_ratio() * 100:.1f}% bits set, expected FP {bf.expected_fp_rate() * 100:.2f}%")
    return bf


if __name__ == "__main__":
    main(*sys.argv[1:])
