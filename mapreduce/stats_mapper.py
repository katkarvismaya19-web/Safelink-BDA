#!/usr/bin/env python3
"""
MapReduce Job 2 - MAPPER : scam-link analytics
Emits  tld:<tld> \t 1        which domain endings scammers use
       brand:<brand> \t 1    which brands they impersonate
       lure:<word> \t 1      which bait words they use
"""
import re
import sys

BRANDS = ["sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "gpay", "irctc", "amazon",
          "flipkart", "jio", "airtel", "uidai", "aadhaar", "pan", "epfo", "lic", "kotak",
          "mahavitaran", "bescom", "fastag", "indiapost", "bluedart", "whatsapp", "instagram",
          "paypal", "apple", "microsoft", "netflix", "facebook", "google", "dhl", "fedex"]
LURES = ["kyc", "reward", "cashback", "lucky", "refund", "bill", "verify", "login", "secure",
         "redeem", "gift", "offer", "claim", "blocked", "parcel", "job", "loan", "tax", "otp",
         "update", "account", "wallet", "bonus"]

for line in sys.stdin:
    url = line.strip().lower()
    if not url:
        continue
    host = url.split("/")[0].split(":")[0]
    parts = host.split(".")
    if len(parts) >= 2 and not host.replace(".", "").isdigit():
        tld = ".".join(parts[-2:]) if parts[-2] in ("co", "in", "com") and len(parts) > 2 else parts[-1]
        print(f"tld:.{tld}\t1")
    tokens = re.findall(r"[a-z]+", host)          # "sbi-kyc12.xyz" -> sbi, kyc, xyz
    for b in sorted(BRANDS, key=len, reverse=True):
        if any(t.startswith(b) for t in tokens):   # token match, so "click" != "lic"
            print(f"brand:{b}\t1")
            break
    for w in LURES:
        if w in url:
            print(f"lure:{w}\t1")
