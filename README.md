# SafeLink — Scam Link Checker with Live Scam-Wave Alerts
**Big Data Analytics mini project · Bloom Filter + DGIM + MapReduce (Hadoop)**

## Problem
Fake KYC, bank, electricity-bill and parcel links spread on WhatsApp and SMS every day. Lakhs of known scam
links exist, and a checker has to answer two questions instantly for millions of users:
1. **Is this link a known scam?** → needs a membership test over a huge list, in very little memory → **Bloom Filter**
2. **Is a scam wave happening right now?** → needs a count over a never-ending stream of checks → **DGIM**
Building the filter and analysing the scam list itself is a batch job over big data → **MapReduce on Hadoop**

## What a common user sees
Paste a link → one clear answer:
- **Don't open this link** — it is on the scam list
- **This link looks suspicious** — not on the list, but shows fake-website signs (brand name + bait word, odd domain ending, raw IP, many hyphens). User can report it, which adds it to the Bloom filter.
- **Not on the scam list**
Plus a **Scam activity meter** (Calm / Rising / Scam wave) driven by DGIM.

## Architecture
```
            BATCH LAYER (Hadoop)                              STREAM LAYER (Flask app)
 blacklist.txt ──► HDFS ──► MapReduce Job 1 ──► bloom.bin ──►  user link ─► normalise URL
                         │  (mapper: k hash positions,          │              │
                         │   combiner+reducer: unique bits)      │        Bloom filter check
                         └► MapReduce Job 2 ──► scam_stats.json  │       ┌──────┴───────┐
                            (brands, TLDs, bait words)           │   "definitely no"  "maybe"
                                                                 │       │          exact DB lookup
                                                                 │       │        scam / false alarm
                                                                 │       └─────► bit (1 = scam) ─► DGIM (N = 1000)
                                                                 │                         └─► scams in last 100 ─► wave alert
```
Two-stage check (Bloom first, database only on "maybe") is the same design Google Chrome Safe Browsing used.
In our runs **~87% of checks never touch the database.**

## Project structure
| Path | What it does |
|---|---|
| `core/bloom_filter.py` | Bloom filter: optimal m and k, double hashing, save/load |
| `core/dgim.py` | DGIM buckets, merge rule (max 2 per size), window queries for any k ≤ N |
| `core/url_utils.py` | URL normalisation (lowercase, strip www, trailing slash) |
| `mapreduce/bloom_mapper.py`, `bloom_reducer.py` | Job 1: builds the Bloom filter in parallel |
| `mapreduce/stats_mapper.py`, `stats_reducer.py` | Job 2: brands impersonated, domain endings, bait words |
| `mapreduce/run_local.py` | Simulates Hadoop locally: split → map → combine → shuffle/sort → reduce |
| `mapreduce/build_from_hadoop_output.py` | Builds bloom.bin from a real Hadoop job's output |
| `data/download_feeds.py` | Downloads REAL live scam feeds (OpenPhish, URLhaus) |
| `data/generate_sample_data.py` | Generates 50,000 synthetic India-style scam links (offline fallback) |
| `app.py` + `templates/index.html` | Web app: checker for users + "How it works" dashboard |
| `experiments/evaluate.py` | Charts and numbers for the report |

## How to run
```bash
pip install -r requirements.txt

# 1. Get data (choose one)
python data/download_feeds.py          # real live scam links (needs internet)
python data/generate_sample_data.py    # synthetic sample, works offline

# 2. Run the MapReduce jobs (local simulation of Hadoop)
python mapreduce/run_local.py

# 3. Start the app
python app.py                          # open http://127.0.0.1:5000

# 4. Report charts
python experiments/evaluate.py         # saved in experiments/results/
```
If you change the blacklist, re-run step 2 so the Bloom filter is rebuilt.

## Running on a real Hadoop cluster
```bash
# m and k for n URLs at 1% FP (run_local.py prints these too)
python -c "from core.bloom_filter import optimal_params; import sys; n=sum(1 for _ in open('data/blacklist.txt')); print(optimal_params(n,0.01))"

hdfs dfs -mkdir -p /safelink
hdfs dfs -put data/blacklist.txt /safelink/
hdfs fsck /safelink/blacklist.txt -files -blocks      # show blocks & replication

# Job 1: Bloom filter
hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -D mapreduce.job.name="SafeLink Bloom build" \
  -cmdenv BLOOM_M=<m> -cmdenv BLOOM_K=<k> \
  -input /safelink/blacklist.txt -output /safelink/bloom_out \
  -mapper bloom_mapper.py -combiner bloom_reducer.py -reducer bloom_reducer.py \
  -file mapreduce/bloom_mapper.py -file mapreduce/bloom_reducer.py
hdfs dfs -getmerge /safelink/bloom_out bloom_part.txt
python mapreduce/build_from_hadoop_output.py bloom_part.txt <m> <k>

# Job 2: analytics
hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar \
  -input /safelink/blacklist.txt -output /safelink/stats_out \
  -mapper stats_mapper.py -combiner stats_reducer.py -reducer stats_reducer.py \
  -file mapreduce/stats_mapper.py -file mapreduce/stats_reducer.py
hdfs dfs -cat /safelink/stats_out/part-* | sort -t$'\t' -k2 -nr | head -20
```

## Demo script (5 minutes)
1. **Check a link tab** → click "a known scam link" → red verdict. Click "a fake-looking bank link" → amber with reasons → Report it → check again → now red (Bloom filter updated live).
2. **How it works tab** → show the 7 bit positions of the last link: all 1 = "maybe", one 0 = "definitely not".
3. Click **Simulate 500 normal checks** → meter stays Calm. Click **Simulate a scam wave** → chart crosses the red line, meter shows Scam wave. Run normal again → it drops back.
4. Show DGIM buckets (1, 1, 2, 2, 4, 8 … ) and "10 buckets vs 1,000 bits".
5. Show MapReduce analytics and the `run_local.py` output (combiner cut network traffic).

## Results (50,000 scam links)
| Metric | Value |
|---|---|
| Bloom filter memory | 58.5 KB (normal Python set ≈ 4.3 MB) → **~75× smaller** |
| Hash functions k | 7 (optimal for 1%) |
| False-positive rate | theoretical 1.00%, observed 1.04% |
| False negatives | 0 (guaranteed) |
| Database lookups avoided | ~87% |
| MapReduce build = direct build | bit-for-bit identical |
| DGIM memory, N = 1000 | ~10 buckets (~80 bytes) vs 1,000 bits |
| DGIM error | mean ~12%, max ~35% (bound 50%) |
| DGIM buckets for N = 1,000,000 | ~29 |
| Wave detection | alert within ~50 checks of the wave starting |

## Team split (3 members)
| Member | Owns | Explains in viva |
|---|---|---|
| Member 1 | `core/bloom_filter.py`, `data/` scripts, `experiments` charts 1–2 | Bloom filter math, m/k formulas, false positives, why no deletes |
| Member 2 | `core/dgim.py`, wave alert logic, charts 3–4 | DGIM bucket rules, merging, estimate, 50% bound, memory |
| Member 3 | `mapreduce/`, Hadoop commands, `app.py` + UI | HDFS blocks, map/combine/shuffle/reduce, two-stage architecture |

## Likely viva questions
- **Why not just use a set or database?** At crore-scale a set needs GBs of RAM; the Bloom filter needs MBs and fits on a phone or edge server.
- **Can a Bloom filter miss a scam?** No. False negatives are impossible; only false positives, which the database step clears.
- **How do you remove a link from a Bloom filter?** You can't (clearing a bit could affect other links). Use a Counting Bloom filter or rebuild with MapReduce.
- **Why at most 2 buckets of each size in DGIM?** It keeps the oldest bucket small relative to the total, which bounds error at 50%; allowing r buckets per size gives error ≤ 1/(r−1).
- **Why is the reducer safe as a combiner?** Both jobs sum counts; sum is associative and commutative. (An average would not be safe.)
- **Why check both the full URL and the domain?** Some feeds list entire scam domains, others list one page on a hacked site.

## Limitations & future scope
- A link not on the list is not proof of safety; the pattern check helps but can be fooled.
- Add Flajolet-Martin to count unique scam links seen per day, Counting Bloom filter for deletions,
  per-city waves, a WhatsApp bot or browser extension front-end, and Spark Streaming for real-time scale.
- Sample data is synthetic; for the final demo run `data/download_feeds.py` to use real live feeds.
