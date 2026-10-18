"""
Experiments for the project report. Produces charts in experiments/results/
  1. Bloom: observed vs theoretical false-positive rate for different target rates
  2. Bloom: effect of number of hash functions k (fixed m)
  3. DGIM: estimate vs exact on a stream with a scam wave
  4. DGIM: error distribution and memory vs window size
Run:  python experiments/evaluate.py
"""
import math
import os
import random
import sys
from collections import deque

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core.bloom_filter import BloomFilter, optimal_params  # noqa: E402
from core.dgim import DGIM  # noqa: E402
from core.url_utils import normalize_url  # noqa: E402

OUT = os.path.join(ROOT, "experiments", "results")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(1)

with open(os.path.join(ROOT, "data", "blacklist.txt")) as f:
    blacklist = [normalize_url(l)[0] for l in f if l.strip()]
bl = set(blacklist)
n = len(blacklist)
test = [f"site{rng.randint(1, 10**9)}.example/{rng.randint(1, 999)}" for _ in range(50_000)]
test = [t for t in test if t not in bl]

# 1. FP rate vs target
targets = [0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.001]
obs, theo, kb = [], [], []
for p in targets:
    bf = BloomFilter.for_capacity(n, p)
    for u in blacklist:
        bf.add(u)
    obs.append(sum(t in bf for t in test) / len(test) * 100)
    theo.append(bf.expected_fp_rate() * 100)
    kb.append(bf.memory_bytes() / 1024)
fig, ax = plt.subplots(figsize=(8, 4.5))
x = range(len(targets))
ax.bar(x, kb, color="#c6d4f5", label="Memory (KB)")
ax.set_ylabel("Memory (KB)")
ax.set_xticks(list(x)); ax.set_xticklabels([f"{p * 100:g}%" for p in targets])
ax.set_xlabel("Target false-positive rate")
ax2 = ax.twinx()
ax2.plot(list(x), theo, "o--", color="#1c2541", label="Theoretical FP %")
ax2.plot(list(x), obs, "s-", color="#b42318", label="Observed FP %")
ax2.set_ylabel("False-positive rate (%)")
fig.legend(loc="upper center", bbox_to_anchor=(0.55, 0.88))
plt.title(f"Bloom filter on {n:,} scam links: memory vs accuracy")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "1_bloom_fp_vs_memory.png"), dpi=150); plt.close()

# 2. effect of k at fixed m
m, k_opt = optimal_params(n, 0.01)
ks = list(range(1, 16))
fpk = []
for k in ks:
    bf = BloomFilter(m, k)
    for u in blacklist:
        bf.add(u)
    fpk.append(sum(t in bf for t in test[:20000]) / 20000 * 100)
plt.figure(figsize=(8, 4.5))
plt.plot(ks, fpk, "o-", color="#2f5bd3", label="Observed")
plt.plot(ks, [(1 - math.exp(-k * n / m)) ** k * 100 for k in ks], "--", color="#1c2541", label="(1 - e^(-kn/m))^k")
plt.axvline(k_opt, color="#13795b", linestyle=":", label=f"optimal k = {k_opt}")
plt.xlabel("Number of hash functions k"); plt.ylabel("False-positive rate (%)")
plt.title(f"Too few or too many hash functions both hurt (m = {m:,} bits)")
plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
plt.savefig(os.path.join(OUT, "2_bloom_effect_of_k.png"), dpi=150); plt.close()

# 3. DGIM on a stream with a wave
N, T = 1000, 30_000
d, exact = DGIM(N), deque(maxlen=N)
ts, est, act, errs = [], [], [], []
for t in range(1, T + 1):
    p = 0.45 if 15_000 <= t <= 18_000 else 0.03
    bit = 1 if rng.random() < p else 0
    d.add(bit); exact.append(bit)
    if t % 50 == 0:
        e, a = d.count(), sum(exact)
        ts.append(t); est.append(e); act.append(a)
        if a:
            errs.append((e - a) / a * 100)
plt.figure(figsize=(10, 4.5))
plt.plot(ts, act, lw=2, color="#1c2541", label="Exact count")
plt.plot(ts, est, "--", lw=1.4, color="#2f5bd3", label="DGIM estimate")
plt.axvspan(15_000, 18_000, color="#b42318", alpha=.08, label="Scam wave")
plt.xlabel("Links checked"); plt.ylabel(f"Scam links in last {N}")
plt.title("DGIM tracks the scam count closely using ~10 buckets instead of 1,000 bits")
plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
plt.savefig(os.path.join(OUT, "3_dgim_vs_exact.png"), dpi=150); plt.close()

# 4. DGIM error histogram + memory vs N
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
a1.hist(errs, bins=30, color="#2f5bd3")
a1.axvline(-50, color="#b42318", ls=":"); a1.axvline(50, color="#b42318", ls=":", label="±50% bound")
a1.set_xlabel("Estimation error (%)"); a1.set_ylabel("Snapshots"); a1.set_title("DGIM error stays inside the bound")
a1.legend()
Ns = [100, 1_000, 10_000, 100_000, 1_000_000]
buckets = []
for NN in Ns:
    dd = DGIM(NN)
    for _ in range(min(NN * 2, 1_200_000)):
        dd.add(1 if rng.random() < 0.3 else 0)
    buckets.append(len(dd.buckets))
a2.plot(Ns, [NN / 8 for NN in Ns], "o-", color="#1c2541", label="Store every bit (bytes)")
a2.plot(Ns, [b * 8 for b in buckets], "s-", color="#13795b", label="DGIM buckets (bytes)")
a2.set_xscale("log"); a2.set_yscale("log"); a2.set_xlabel("Window size N"); a2.set_ylabel("Memory (bytes)")
a2.set_title("Memory grows like log² N, not N"); a2.legend()
fig.tight_layout(); fig.savefig(os.path.join(OUT, "4_dgim_error_and_memory.png"), dpi=150); plt.close()

print(f"Blacklist n = {n:,}")
print("Target FP  | theoretical | observed | memory")
for p, t, o, k_ in zip(targets, theo, obs, kb):
    print(f"{p * 100:>8g}%  | {t:>9.3f}% | {o:>7.3f}% | {k_:.1f} KB")
print(f"DGIM: mean |error| = {sum(abs(e) for e in errs) / len(errs):.2f}%, max |error| = {max(abs(e) for e in errs):.2f}%")
print("DGIM buckets for N =", dict(zip(Ns, buckets)))
print(f"Charts saved in {OUT}")
