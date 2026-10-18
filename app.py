"""
SafeLink - Scam Link Checker with live Scam-Wave Alerts
Big Data Analytics mini project: Bloom Filter + DGIM + MapReduce (Hadoop)

  Bloom filter : instant "is this link a known scam?" check using ~60 KB for 50,000 links
  DGIM         : counts scam links checked in the last N checks -> "scam wave" alert
  MapReduce    : builds the Bloom filter and scam analytics from the blacklist in parallel

Run:  python app.py   then open http://127.0.0.1:5000
"""
import json
import os
import random
import threading
from collections import deque

from flask import Flask, jsonify, render_template, request

from core.bloom_filter import BloomFilter
from core.dgim import DGIM
from core.url_utils import keys_for, normalize_url

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
WINDOW = 1000                  # DGIM window N
SHORT = 100                    # "recent" window used for the wave meter (k <= N)
WAVE_RISING, WAVE_ALERT = 10, 25   # scam links per last 100 checks

# Extra warning layer for links NOT on the list (Bloom only knows listed links)
BRANDS = ["sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "gpay", "irctc", "amazon",
          "flipkart", "jio", "airtel", "uidai", "aadhaar", "epfo", "lic", "kotak", "fastag",
          "indiapost", "bluedart", "whatsapp", "instagram", "paypal", "netflix", "google"]
LURES = ["kyc", "reward", "cashback", "lucky", "refund", "verify", "secure", "redeem", "gift",
         "claim", "blocked", "parcel", "loan", "otp", "bonus", "update", "prize", "free"]
RISKY_TLDS = {"xyz", "top", "online", "click", "shop", "site", "live", "icu", "buzz", "vip",
              "store", "info", "rest", "cfd", "sbs"}

app = Flask(__name__)
lock = threading.Lock()


def ensure_data():
    if not os.path.exists(os.path.join(DATA, "blacklist.txt")):
        import data.generate_sample_data as g
        g.main()
    if not os.path.exists(os.path.join(DATA, "bloom.bin")):
        from mapreduce.run_local import main as build
        build()


ensure_data()
bloom = BloomFilter.load(os.path.join(DATA, "bloom.bin"), os.path.join(DATA, "bloom_meta.json"))
# Exact blacklist = the "server database". In a real system it sits on a server and is only
# queried when the Bloom filter says "maybe" (this is how Chrome Safe Browsing worked).
with open(os.path.join(DATA, "blacklist.txt")) as f:
    blacklist_db = {normalize_url(l)[0] for l in f if l.strip()}
blacklist_list = sorted(blacklist_db)
with open(os.path.join(DATA, "safe_sites.txt")) as f:
    safe_sites = [l.strip() for l in f if l.strip()]
scam_stats = {}
if os.path.exists(os.path.join(DATA, "scam_stats.json")):
    with open(os.path.join(DATA, "scam_stats.json")) as f:
        scam_stats = json.load(f)

dgim = DGIM(WINDOW)
exact_window = deque(maxlen=WINDOW)       # ground truth, only to prove DGIM accuracy
timeline = deque(maxlen=3000)
counters = {"checks": 0, "bloom_no": 0, "bloom_maybe": 0, "confirmed": 0,
            "false_pos": 0, "reported": 0}


def suspicious_reasons(host):
    import re
    if host in safe_sites or any(host.endswith("." + s) for s in safe_sites):
        return []
    tokens = re.findall(r"[a-z]+", host)
    reasons = []
    brand = next((b for b in BRANDS if any(t.startswith(b) for t in tokens)), None)
    lure = next((w for w in LURES if any(w in t for t in tokens)), None)
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if brand:
        reasons.append(f"Uses the name \"{brand}\" but is not the official {brand} website")
    if lure:
        reasons.append(f"Contains the bait word \"{lure}\"")
    if tld in RISKY_TLDS:
        reasons.append(f"Ends in .{tld}, a domain ending scammers use often")
    if re.fullmatch(r"[0-9.]+", host):
        reasons.append("Uses a raw IP address instead of a website name")
    if host.count("-") >= 2:
        reasons.append("Has many hyphens, a common trick in fake websites")
    is_ip = bool(re.fullmatch(r"[0-9.]+", host))
    return reasons if (brand and (lure or tld in RISKY_TLDS)) or is_ip or len(reasons) >= 2 else []


def check_link(raw):
    keys = keys_for(raw)
    if not keys:
        return None
    per_key, maybe = [], False
    for key in keys:
        hit, detail = bloom.check(key)
        per_key.append({"key": key, "bloom_says": "maybe" if hit else "no",
                        "bits": [{"pos": p, "bit": int(b)} for p, b in detail]})
        maybe = maybe or hit
    confirmed = maybe and any(k in blacklist_db for k in keys)
    reasons = [] if confirmed else suspicious_reasons(normalize_url(raw)[1])
    if confirmed:
        verdict = "scam"
    elif reasons:
        verdict = "suspicious"
    elif maybe:
        verdict = "false_positive"        # Bloom said maybe, database said no
    else:
        verdict = "safe"
    with lock:
        counters["checks"] += 1
        counters["bloom_no" if not maybe else "bloom_maybe"] += 1
        if confirmed:
            counters["confirmed"] += 1
        elif maybe:
            counters["false_pos"] += 1
        bit = 1 if confirmed else 0
        dgim.add(bit)
        exact_window.append(bit)
        timeline.append({"t": dgim.t, "est": dgim.count(SHORT),
                         "exact": sum(list(exact_window)[-SHORT:])})
    return {"input": raw, "keys": per_key, "verdict": verdict,
            "bloom_maybe": maybe, "db_lookup": maybe, "reasons": reasons,
            "wave": wave_status()}


def wave_status():
    est = dgim.count(SHORT)
    level = "alert" if est >= WAVE_ALERT else "rising" if est >= WAVE_RISING else "calm"
    return {"level": level, "scams_last_100": est}


def random_safe_url(rng):
    return f"https://{rng.choice(safe_sites)}/{rng.choice(['', 'home', 'login', 'offers', 'help', 'p/' + str(rng.randint(1, 9999))])}"


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/check")
def api_check():
    url = (request.get_json(silent=True) or {}).get("url", "")
    result = check_link(url)
    if result is None:
        return jsonify({"error": "Paste a link to check, for example sbi-kyc-update.xyz"}), 400
    return jsonify(result)


@app.get("/api/sample")
def api_sample():
    """A random known-scam link, for the "Try" button in the demo."""
    return jsonify({"url": "http://" + random.choice(blacklist_list)})


@app.post("/api/report")
def api_report():
    url = (request.get_json(silent=True) or {}).get("url", "")
    full, _ = normalize_url(url)
    if not full:
        return jsonify({"error": "Paste the link you want to report"}), 400
    with lock:
        bloom.add(full)           # Bloom filters support add, but NOT delete
        blacklist_db.add(full)
        counters["reported"] += 1
    return jsonify({"reported": full})


@app.post("/api/simulate")
def api_simulate():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "normal")
    n = max(1, min(int(body.get("n", 300)), 5000))
    scam_ratio = 0.45 if mode == "wave" else 0.03
    rng = random.Random()
    for _ in range(n):
        if rng.random() < scam_ratio:
            check_link("http://" + rng.choice(blacklist_list))
        else:
            check_link(random_safe_url(rng))
    return jsonify({"simulated": n, "mode": mode, "wave": wave_status()})


@app.get("/api/stats")
def api_stats():
    with lock:
        exact_n = sum(exact_window)
        exact_short = sum(list(exact_window)[-SHORT:])
        est_n, est_short = dgim.count(), dgim.count(SHORT)
        lookups_saved = counters["bloom_no"] / counters["checks"] * 100 if counters["checks"] else 0
        clean = counters["checks"] - counters["confirmed"]
        return jsonify({
            "bloom": {"m": bloom.m, "k": bloom.k, "items": bloom.count,
                      "memory_kb": round(bloom.memory_bytes() / 1024, 1),
                      "set_memory_kb": round(len(blacklist_db) * 90 / 1024, 1),
                      "fill_pct": round(bloom.fill_ratio() * 100, 1),
                      "expected_fp_pct": round(bloom.expected_fp_rate() * 100, 2),
                      "observed_fp_pct": round(counters["false_pos"] / clean * 100, 2) if clean else 0,
                      "lookups_saved_pct": round(lookups_saved, 1)},
            "dgim": {"N": WINDOW, "t": dgim.t, "buckets": dgim.snapshot(), "merges": dgim.merges,
                     "est_N": est_n, "exact_N": exact_n, "est_100": est_short,
                     "exact_100": exact_short, "memory_bytes": dgim.memory_bytes(),
                     "exact_memory_bytes": WINDOW // 8},
            "counters": counters, "wave": wave_status(),
            "thresholds": {"rising": WAVE_RISING, "alert": WAVE_ALERT},
            "timeline": list(timeline), "scam_stats": scam_stats,
        })


@app.post("/api/reset")
def api_reset():
    global dgim
    with lock:
        dgim = DGIM(WINDOW)
        exact_window.clear()
        timeline.clear()
        for k in counters:
            counters[k] = 0
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("SafeLink running at http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
