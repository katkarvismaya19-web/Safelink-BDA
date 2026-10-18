"""
Downloads REAL, live phishing/malware URL feeds and merges them into data/blacklist.txt
  - OpenPhish community feed : https://openphish.com/feed.txt
  - URLhaus (abuse.ch)       : https://urlhaus.abuse.ch/downloads/text/
Run before the demo (needs internet). Falls back to sample data if both fail.
"""
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from core.url_utils import normalize_url  # noqa: E402

FEEDS = {
    "OpenPhish": "https://openphish.com/feed.txt",
    "URLhaus": "https://urlhaus.abuse.ch/downloads/text/",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (BDA mini project)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="ignore").splitlines()


def main():
    entries = set()
    for name, url in FEEDS.items():
        try:
            lines = [l for l in fetch(url) if l.strip() and not l.startswith("#")]
            before = len(entries)
            for line in lines:
                full, _ = normalize_url(line)
                if full:
                    entries.add(full)
            print(f"{name:10s}: {len(lines):,} lines, {len(entries) - before:,} new entries")
        except Exception as e:
            print(f"{name:10s}: failed ({e})")
    if not entries:
        print("No feed reachable. Generating sample data instead.")
        from generate_sample_data import main as gen
        gen()
        return
    with open(os.path.join(HERE, "blacklist.txt"), "w") as f:
        f.write("\n".join(sorted(entries)) + "\n")
    if not os.path.exists(os.path.join(HERE, "safe_sites.txt")):
        from generate_sample_data import SAFE_SITES
        with open(os.path.join(HERE, "safe_sites.txt"), "w") as f:
            f.write("\n".join(SAFE_SITES) + "\n")
    print(f"Total real blacklist entries: {len(entries):,} -> data/blacklist.txt")
    print("Now rebuild the Bloom filter:  python mapreduce/run_local.py")


if __name__ == "__main__":
    main()
