"""
Generates a SAMPLE scam-link blacklist (synthetic, India-style phishing patterns)
and a list of safe sites. Use this when you have no internet.
For REAL data, run:  python data/download_feeds.py
"""
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(7)

BRANDS = ["sbi", "hdfc", "icici", "axis", "paytm", "phonepe", "gpay", "irctc", "amazon",
          "flipkart", "jio", "airtel", "uidai", "aadhaar", "pan", "epfo", "lic", "kotak",
          "mahavitaran", "bescom", "fastag", "indiapost", "bluedart", "whatsapp", "instagram"]
LURES = ["kyc-update", "reward", "cashback", "lucky-draw", "refund", "bill-pay", "verify",
         "login", "secure", "points-redeem", "gift", "offer", "claim", "blocked-account",
         "electricity-bill", "parcel-held", "job-offer", "loan-approved", "tax-refund"]
TLDS = ["xyz", "top", "online", "click", "shop", "info", "site", "live", "icu", "buzz",
        "in.net", "co.in", "com", "org", "vip", "store"]
PATHS = ["login", "verify", "kyc", "update", "claim", "redeem", "otp", "secure/login",
         "account/verify", "pay", "track", "form", "index.php", "reward/claim"]

SAFE_SITES = ["google.com", "youtube.com", "wikipedia.org", "amazon.in", "flipkart.com",
              "onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "axisbank.com", "paytm.com",
              "phonepe.com", "irctc.co.in", "uidai.gov.in", "incometax.gov.in", "epfindia.gov.in",
              "licindia.in", "jio.com", "airtel.in", "indiapost.gov.in", "bluedart.com",
              "whatsapp.com", "instagram.com", "facebook.com", "linkedin.com", "github.com",
              "stackoverflow.com", "zomato.com", "swiggy.com", "myntra.com", "nykaa.com",
              "makemytrip.com", "bookmyshow.com", "hotstar.com", "netflix.com", "spotify.com",
              "timesofindia.indiatimes.com", "ndtv.com", "thehindu.com", "moneycontrol.com",
              "zerodha.com", "groww.in", "naukri.com", "mu.ac.in", "nptel.ac.in",
              "geeksforgeeks.org", "w3schools.com", "kaggle.com", "coursera.org", "udemy.com"]


def scam_domain():
    style = rng.random()
    b, l, t = rng.choice(BRANDS), rng.choice(LURES), rng.choice(TLDS)
    n = rng.randint(1, 999)
    if style < 0.35:
        return f"{b}-{l}{n}.{t}"
    if style < 0.6:
        return f"{b}{rng.choice(['online', 'care', 'help', 'india', 'support'])}{n}.{t}"
    if style < 0.8:
        return f"{l}-{b}.{rng.choice(['xyz', 'top', 'click', 'icu'])}{n}.{t}"
    return f"{b}.{l}-{n}.{t}"


def main(n_entries=50_000):
    entries = set()
    while len(entries) < n_entries:
        d = scam_domain()
        if rng.random() < 0.5:
            entries.add(d)                                   # whole domain is a scam
        else:
            entries.add(f"{d}/{rng.choice(PATHS)}")          # specific scam page
    with open(os.path.join(HERE, "blacklist.txt"), "w") as f:
        f.write("\n".join(sorted(entries)) + "\n")
    with open(os.path.join(HERE, "safe_sites.txt"), "w") as f:
        f.write("\n".join(SAFE_SITES) + "\n")
    print(f"Wrote {len(entries):,} sample scam entries -> data/blacklist.txt (SYNTHETIC)")
    print(f"Wrote {len(SAFE_SITES)} safe sites -> data/safe_sites.txt")


if __name__ == "__main__":
    main()
