"""
Bloom Filter
------------
Answers "is this item in the set?" using a bit array and k hash functions.
  - "No"    -> definitely not in the set (no false negatives)
  - "Maybe" -> probably in the set (small false positive chance)

Optimal parameters for n items and target false-positive rate p:
  m = -(n * ln p) / (ln 2)^2      (bits)
  k = (m / n) * ln 2              (hash functions)
  actual FP rate = (1 - e^(-k*n/m))^k
"""
import hashlib
import json
import math


def optimal_params(n, p):
    m = math.ceil(-(n * math.log(p)) / (math.log(2) ** 2))
    k = max(1, round((m / n) * math.log(2)))
    return m, k


def bit_positions(item, m, k):
    """Double hashing: h_i(x) = (h1(x) + i*h2(x)) mod m  (Kirsch-Mitzenmacher)."""
    d = hashlib.md5(item.encode("utf-8")).digest()
    h1 = int.from_bytes(d[:8], "big")
    h2 = int.from_bytes(d[8:], "big") | 1
    return [(h1 + i * h2) % m for i in range(k)]


class BloomFilter:
    def __init__(self, m, k):
        self.m, self.k = m, k
        self.bits = bytearray(math.ceil(m / 8))
        self.count = 0

    @classmethod
    def for_capacity(cls, n, p=0.01):
        return cls(*optimal_params(n, p))

    def positions(self, item):
        return bit_positions(item, self.m, self.k)

    def set_bit(self, pos):
        self.bits[pos // 8] |= 1 << (pos % 8)

    def get_bit(self, pos):
        return bool(self.bits[pos // 8] & (1 << (pos % 8)))

    def add(self, item):
        for p in self.positions(item):
            self.set_bit(p)
        self.count += 1

    def check(self, item):
        """Returns (maybe_present, [(position, bit_value), ...]) for visualisation."""
        detail = [(p, self.get_bit(p)) for p in self.positions(item)]
        return all(b for _, b in detail), detail

    def __contains__(self, item):
        return self.check(item)[0]

    def fill_ratio(self):
        ones = sum(bin(b).count("1") for b in self.bits)
        return ones / self.m

    def expected_fp_rate(self):
        return (1 - math.exp(-self.k * self.count / self.m)) ** self.k

    def memory_bytes(self):
        return len(self.bits)

    # ---- persistence (used by the MapReduce build) ----
    def save(self, bin_path, meta_path):
        with open(bin_path, "wb") as f:
            f.write(self.bits)
        with open(meta_path, "w") as f:
            json.dump({"m": self.m, "k": self.k, "count": self.count}, f)

    @classmethod
    def load(cls, bin_path, meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        bf = cls(meta["m"], meta["k"])
        with open(bin_path, "rb") as f:
            bf.bits = bytearray(f.read())
        bf.count = meta["count"]
        return bf
