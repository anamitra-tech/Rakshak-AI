"""
Lightweight regex-based entity extraction for Indian phone numbers,
UPI IDs, bank account-like numbers, and URLs.

This runs entirely locally -- no API key needed -- so it works even
before the LLM integration is wired up. The LLM service also asks the
model to extract entities as a cross-check; you can reconcile the two
lists once the AI/ML side is live.
"""

import re

PHONE_RE = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")
UPI_RE = re.compile(r"\b[\w.\-]{2,256}@[a-zA-Z]{2,64}\b")
BANK_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
URL_RE = re.compile(r"https?://[^\s]+")


def extract_entities(text: str) -> dict:
    phone_numbers = list(dict.fromkeys(PHONE_RE.findall(text)))
    urls = list(dict.fromkeys(URL_RE.findall(text)))

    # UPI IDs look like name@bank -- exclude anything that's actually a URL
    upi_candidates = UPI_RE.findall(text)
    upi_ids = list(dict.fromkeys(
        u for u in upi_candidates if not any(u in url for url in urls)
    ))

    # Bank account numbers: long digit runs, excluding ones already
    # captured as phone numbers
    bank_accounts = list(dict.fromkeys(
        b for b in BANK_ACCOUNT_RE.findall(text) if b not in phone_numbers
    ))

    return {
        "phone_numbers": phone_numbers,
        "upi_ids": upi_ids,
        "bank_accounts": bank_accounts,
        "urls": urls,
    }
