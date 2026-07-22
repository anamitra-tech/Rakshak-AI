"""
MODULE 5 — Link Safety Engine.

Heuristic phishing/spoof detector over URL structure. No network calls
(works offline), explainable in plain language for citizens.
"""
import re
from urllib.parse import urlparse

SUSPICIOUS_TLDS = {"xyz", "tk", "ml", "ga", "cf", "gq", "top", "win", "club",
                   "online", "ru", "info", "click", "loan", "work"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
              "buff.ly", "rebrand.ly", "cutt.ly"}
BRAND_TOKENS = ["sbi", "hdfc", "icici", "axis", "paytm", "rbi", "amazon",
                "netflix", "irctc", "kotak", "gov", "upi", "kyc"]
LEGIT_HINTS = ["onlinesbi.sbi", "hdfcbank.com", "icicibank.com", "amazon.in",
               "irctc.co.in", "rbi.org.in", "paytm.com", "netflix.com",
               "cybercrime.gov.in", "google.com", ".gov.in"]


def analyze_url(url):
    url = (url or "").strip()
    if not url:
        return _fmt("SAFE", 0.0, "No URL provided.", [])
    parsed = urlparse(url if "://" in url else "http://" + url)
    host = (parsed.hostname or "").lower()
    signals, score = [], 0.0

    # whitelist of obvious legit domains
    if any(host.endswith(h.lstrip(".")) or host == h.lstrip(".") for h in LEGIT_HINTS):
        return _fmt("SAFE", 0.05, "Matches a known legitimate domain.", ["Verified known domain"])

    # raw IP address as host
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
        score += 0.5; signals.append("Uses a raw IP address instead of a domain name")

    # suspicious TLD
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in SUSPICIOUS_TLDS:
        score += 0.4; signals.append(f"Uses a high-risk domain extension (.{tld})")

    # URL shortener (hides destination)
    if host in SHORTENERS:
        score += 0.45; signals.append("Link shortener hides the real destination")

    # brand impersonation: brand token present but not the official domain
    brand_in = [b for b in BRAND_TOKENS if b in host.replace(".", "")]
    if brand_in:
        score += 0.45
        signals.append(f"Mimics a trusted brand ({brand_in[0]}) on a non-official domain")

    # homoglyph / digit substitution (amaz0n, netfiix)
    if re.search(r"[a-z]0[a-z]|[a-z]1[a-z]|rn[a-z]|[il]{2}", host):
        score += 0.25; signals.append("Misspelled / look-alike domain (character substitution)")

    # excessive subdomains / hyphenated bank-looking host
    if host.count("-") >= 2 or host.count(".") >= 3:
        score += 0.2; signals.append("Unusually complex host (many hyphens/subdomains)")

    # no https
    if parsed.scheme != "https":
        score += 0.1; signals.append("Connection is not secure (no HTTPS)")

    score = min(1.0, score)
    if score >= 0.6:
        level = "DANGEROUS"
    elif score >= 0.3:
        level = "SUSPICIOUS"
    else:
        level = "SAFE"
    reason = _reason(level, signals)
    return _fmt(level, round(score, 3), reason, signals)


def _reason(level, signals):
    if level == "SAFE" and not signals:
        return "No phishing indicators found in the link structure."
    return f"{level}: " + "; ".join(signals) + "."


def _fmt(level, score, reason, signals):
    action = {
        "DANGEROUS": "Do NOT click. Likely phishing/spoof. Report and delete.",
        "SUSPICIOUS": "Avoid clicking. Verify the sender and type the official URL manually.",
        "SAFE": "No issues detected, but always confirm sensitive actions on official apps.",
    }[level]
    return {"risk_level": level, "score": score, "reason": reason,
            "signals": signals, "recommended_action": action}


if __name__ == "__main__":
    for u in ["http://sbi-kyc-update.xyz/login", "https://bit.ly/3xScam",
              "https://www.onlinesbi.sbi/", "http://192.168.4.21/bank",
              "http://amaz0n-prize.club/win", "https://www.amazon.in/"]:
        r = analyze_url(u)
        print(f"[{r['risk_level']:10s} {r['score']:.2f}] {u}")
