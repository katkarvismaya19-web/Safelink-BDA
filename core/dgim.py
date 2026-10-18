"""
DGIM (Datar-Gionis-Indyk-Motwani)
---------------------------------
Estimates the number of 1s in the last N bits of a stream using only
O(log^2 N) memory instead of storing all N bits.

Rules:
  1. Each bucket stores (timestamp of its most recent 1, size).
  2. Sizes are powers of 2.
  3. At most 2 buckets of each size (r = 2).
  4. When a 3rd bucket of a size appears, merge the 2 oldest into one of double size.
  5. Buckets whose timestamp leaves the window are dropped.
Estimate = sum of all bucket sizes in window - half of the oldest bucket.
Error is at most 50%.
"""


class DGIM:
    def __init__(self, window_size):
        self.N = window_size
        self.buckets = []      # [timestamp, size], newest first
        self.t = 0
        self.merges = 0

    def add(self, bit):
        self.t += 1
        while self.buckets and self.buckets[-1][0] <= self.t - self.N:
            self.buckets.pop()
        if bit != 1:
            return
        self.buckets.insert(0, [self.t, 1])
        size = 1
        while True:
            same = [i for i, b in enumerate(self.buckets) if b[1] == size]
            if len(same) <= 2:
                break
            newer, oldest = same[-2], same[-1]
            self.buckets[newer][1] = size * 2   # merged bucket keeps the newer timestamp
            del self.buckets[oldest]
            self.merges += 1
            size *= 2

    def count(self, k=None):
        """Estimated 1s in the last k bits (k <= N)."""
        k = self.N if k is None else min(k, self.N)
        total = last = 0
        for ts, size in self.buckets:
            if ts > self.t - k:
                total += size
                last = size
            else:
                break
        return total - last // 2

    def snapshot(self):
        return [{"timestamp": ts, "size": s, "age": self.t - ts} for ts, s in self.buckets]

    def memory_bytes(self):
        return len(self.buckets) * 8   # ~2 small ints per bucket
