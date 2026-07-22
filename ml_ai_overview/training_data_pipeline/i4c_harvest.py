"""
I4C Advisory harvester.
Fetches https://cybercrime.gov.in/Webform/Advisory.aspx via httpx (no Playwright needed),
parses the 20 official advisory cards, then runs:
  classify + extract → quality gate → dedup → merge → rebuild → test

Usage:  python -m data.i4c_harvest
"""
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
import warnings
warnings.filterwarnings("ignore")

from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
KB_PATH = ROOT / "kb" / "scams.json"
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

ADVISORY_URL = "https://cybercrime.gov.in/Webform/Advisory.aspx"
ADVISORY_BASE = "https://cybercrime.gov.in/Webform/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

VALID_LABELS = {
    "digital_arrest", "bank_otp_kyc", "investment_fraud",
    "qr_code_fraud", "lottery_prize_fraud", "smishing_link",
    "corporate_malware_bec", "sanchar_saathi_sim_swap",
    "fake_job_offer_apk", "aadhaar_biometric_freeze",
    "multi_call_escalation", "other",
}

FILTER_KW = {
    "digital arrest", "otp", "kyc", "phishing", "vishing", "investment",
    "lottery", "qr", "upi", "malware", "sextortion", "courier",
    "cyber fraud", "scam", "fake", "impersonat", "aadhaar", "sim",
    "smishing", "job", "fraud", "spoofing", "banking", "trojan",
    "browser extension", "customer care", "electricity", "qr code",
}

ADVISORY_KW = {
    "fraud", "phish", "scam", "fake", "malware", "otp", "vishing",
    "smishing", "impersonat", "cyber", "arrest", "kyc", "upi",
    "sim", "aadhaar", "invest", "lottery", "qr", "1930",
    "advisory", "alert", "beware", "warning", "trojan", "job",
    "spoofing", "banking", "criminal", "extension",
}

NAV_SIGNALS = {"accessibility options", "sitemap", "skip to main content"}

OVERLAP_THRESHOLD = 0.6
MIN_SUMMARY_WORDS = 15  # relaxed: advisory titles are long but descriptions are short

CLASSIFY_PROMPT = """\
Classify this Indian cybercrime advisory into exactly one scam type. \
Return only the label, nothing else.

Labels:
digital_arrest, bank_otp_kyc, investment_fraud, \
qr_code_fraud, lottery_prize_fraud, smishing_link,
corporate_malware_bec, sanchar_saathi_sim_swap, \
fake_job_offer_apk, aadhaar_biometric_freeze,
multi_call_escalation, other

Advisory: {title}. {summary}

Label:\
"""

EXTRACT_PROMPT = """\
Extract structured fields from this Indian cybercrime advisory. \
Return ONLY a valid JSON object with exactly these keys:

"red_flags": list of 3-6 short warning signs a victim would notice (≤15 words each)
"what_to_do": 1-2 sentences of actionable advice for the victim
"example_messages": list of 1-3 example phrases the fraudster uses (English/Hindi/Hinglish)
"call_script": one sentence describing how this scam unfolds from start to finish

Advisory title: {title}
Advisory text: {text}

JSON:\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower())
    return s[:50].strip("_")


def _sentences(text: str, n: int = 3) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts[:n] if len(p) > 10)


def _text_for_dedup(card: dict) -> str:
    return card.get("summary") or card.get("what_to_do") or card.get("title") or ""


def _overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    if not wa:
        return 0.0
    return len(wa & set(b.lower().split())) / len(wa)


def _has_filter_signal(card: dict) -> bool:
    text = (card.get("title", "") + " " + card.get("raw_text", "")).lower()
    return any(kw in text for kw in FILTER_KW)


def _passes_quality_gate(card: dict) -> bool:
    text = _text_for_dedup(card)
    if len(text.lower().split()) < MIN_SUMMARY_WORDS:
        return False
    if not any(kw in text.lower() for kw in ADVISORY_KW):
        return False
    if any(sig in text.lower()[:120] for sig in NAV_SIGNALS):
        return False
    return True


# ── LLM calls ─────────────────────────────────────────────────────────────────

def _classify(card: dict) -> str | None:
    from llm.client import generate
    prompt = CLASSIFY_PROMPT.format(
        title=card.get("title", ""),
        summary=card.get("summary", "")[:400],
    )
    try:
        resp = generate(prompt)
        for word in resp.text.strip().lower().split():
            cleaned = word.rstrip(".,:")
            if cleaned in VALID_LABELS:
                return cleaned
        log.warning("Unrecognised label %r — %s", resp.text.strip()[:60], card.get("id", "?"))
    except Exception as exc:
        log.warning("Classify error for %s: %s", card.get("id", "?"), exc)
    return None


def _extract_fields(title: str, raw_text: str) -> dict:
    from llm.client import generate
    prompt = EXTRACT_PROMPT.format(title=title, text=raw_text[:1500])
    try:
        resp = generate(prompt)
        text = resp.text.strip()
        m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if m:
            text = m.group(1)
        else:
            m2 = re.search(r"\{[\s\S]*\}", text)
            if m2:
                text = m2.group(0)
        return json.loads(text)
    except Exception as exc:
        log.warning("Extract error for '%s': %s", title[:50], exc)
        return {}


# ── Scraper ───────────────────────────────────────────────────────────────────

def scrape_advisory_page() -> list:
    log.info("Fetching %s", ADVISORY_URL)
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            r = client.get(ADVISORY_URL)
            r.raise_for_status()
    except Exception as exc:
        log.error("Fetch failed: %s", exc)
        return []

    html = r.text
    if "Unauthorised Access" in html or "Page Not Found" in html:
        log.error("Advisory page returned access error")
        return []

    log.info("Fetched %d bytes", len(html))
    (RAW_DIR / "i4c_advisory.html").write_text(html, encoding="utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    # Find the advisories h2, then the row div containing cards
    adv_h2 = next(
        (h for h in soup.find_all("h2") if "Advisories" in h.get_text()), None
    )
    if not adv_h2:
        log.warning("Could not find 'Advisories' h2 on page")
        return []

    row_div = adv_h2.parent.find_next_sibling("div", class_="row")
    if not row_div:
        log.warning("Could not find row div after Advisories h2")
        return []

    cards = []
    for card_div in row_div.find_all("div", class_="other_cont"):
        h3 = card_div.find("h3")
        if not h3:
            continue
        title = re.sub(r"\s+", " ", h3.get_text(strip=True))

        # PDF / anchor link
        a_tag = card_div.find("a", href=True)
        pdf_href = a_tag["href"] if a_tag else ""
        if pdf_href and not pdf_href.startswith("http"):
            pdf_href = "https://cybercrime.gov.in/Webform/" + pdf_href.lstrip("/")

        # Date + description from .info div
        info = card_div.find("div", class_="info")
        date_text = ""
        desc_text = ""
        if info:
            ps = info.find_all("p")
            date_text = ps[0].get_text(strip=True) if ps else ""
            desc_text = " ".join(
                re.sub(r"\s+", " ", p.get_text(strip=True))
                for p in ps[1:]
            )

        summary = (title + ". " + desc_text).strip()
        raw_text = (title + " " + desc_text).strip()

        cards.append({
            "id": f"i4c_{_slug(title)}",
            "scam_type": "auto_classify",
            "title": title,
            "summary": summary,
            "red_flags": [],
            "source": "I4C / cybercrime.gov.in Advisory",
            "source_url": ADVISORY_URL,
            "pdf_url": pdf_href,
            "date": date_text or "2022-2026",
            "raw_text": raw_text[:3000],
        })
        log.info("Parsed: %s", title[:70])

    log.info("Parsed %d advisory cards", len(cards))
    return cards


# ── Inline pipeline ───────────────────────────────────────────────────────────

def run_pipeline(raw_cards: list) -> tuple:
    kb_cards = json.loads(KB_PATH.read_text(encoding="utf-8"))
    kb_texts = [_text_for_dedup(c) for c in kb_cards]
    existing_ids = {c["id"] for c in kb_cards}

    enriched = []
    n = len(raw_cards)
    for i, card in enumerate(raw_cards, 1):
        log.info("[%d/%d] Classify: %s", i, n, card["id"][:45])
        label = _classify(card)
        if label is None or label == "other":
            log.info("  SKIP (label=%s)", label)
            time.sleep(1)
            continue

        card["scam_type"] = label
        time.sleep(1)

        log.info("  Extract fields...")
        extracted = _extract_fields(card.get("title", ""), card.get("raw_text", ""))
        if extracted:
            for key in ("red_flags", "what_to_do", "example_messages", "call_script"):
                val = extracted.get(key)
                if val:
                    card[key] = val

        enriched.append(card)
        log.info("  -> %s", label)
        time.sleep(1)

    print(f"\n  Classified + enriched : {len(enriched)} / {n}")

    new_cards = []
    for card in enriched:
        if not _passes_quality_gate(card):
            log.info("GATE FAIL  %s", card["id"][:40])
            continue
        text = _text_for_dedup(card)
        overlap = max((_overlap(text, kt) for kt in kb_texts if kt), default=0.0)
        if overlap > OVERLAP_THRESHOLD:
            log.info("DUP  (%.2f)  %s", overlap, card["id"][:40])
        else:
            log.info("NEW  (%.2f)  %s", overlap, card["id"][:40])
            new_cards.append(card)

    print(f"  New unique             : {len(new_cards)}")

    added = 0
    for card in new_cards:
        if card["id"] in existing_ids:
            log.warning("ID collision — skipping %s", card["id"])
            continue

        red_flags = card.get("red_flags") or ["See official I4C advisory for details"]
        if isinstance(red_flags, str):
            red_flags = [red_flags]

        example_messages = card.get("example_messages") or [card.get("title", "")]
        if isinstance(example_messages, str):
            example_messages = [example_messages]
        if not example_messages:
            example_messages = [card.get("title", "")]

        what_to_do = (
            card.get("what_to_do")
            or card.get("summary")
            or card.get("title", "")
        )

        kb_card = {
            "id": card["id"],
            "scam_type": card["scam_type"],
            "channel": "call",
            "languages": ["en", "hi", "hinglish"],
            "title": card.get("title", ""),
            "example_messages": example_messages,
            "call_script": card.get("call_script", ""),
            "red_flags": red_flags,
            "what_to_do": what_to_do,
            "source": {
                "name": card.get("source", "I4C / cybercrime.gov.in"),
                "url": card.get("source_url", ADVISORY_URL),
                "date": card.get("date", "2022-2026"),
            },
            "if_already_opened": "",
            "post_open_keywords": [],
            "severity": "",
        }
        kb_cards.append(kb_card)
        existing_ids.add(card["id"])
        added += 1
        log.info("MERGED  %s  (%s)", kb_card["id"], kb_card["scam_type"])

    KB_PATH.write_text(json.dumps(kb_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("KB written: %d cards total", len(kb_cards))
    return added, len(kb_cards)


def rebuild_store() -> None:
    log.info("Rebuilding vector store...")
    store_path = ROOT / "rag" / "chroma_store"
    if store_path.exists():
        shutil.rmtree(store_path)
    result = subprocess.run(
        [sys.executable, "-m", "rag.build_store"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        log.error("build_store failed:\n%s", result.stderr[:400])


def run_bot_tests() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "bot.test_agent"],
        cwd=str(ROOT),
    )
    return result.returncode == 0


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("I4C Advisory Harvester")
    print("=" * 60)

    # Step 1: Scrape advisory page
    print(f"\nSTEP 1: Fetch {ADVISORY_URL}")
    raw_cards = scrape_advisory_page()

    if not raw_cards:
        print("\nERROR: No advisory cards scraped. Exiting.")
        sys.exit(1)

    (RAW_DIR / "i4c_advisory_raw.json").write_text(
        json.dumps(raw_cards, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  {len(raw_cards)} advisory cards  →  data/raw/i4c_advisory_raw.json")

    # Step 2: Keyword filter
    filtered = [c for c in raw_cards if _has_filter_signal(c)]
    print(f"\nSTEP 2: Keyword filter — {len(raw_cards)} → {len(filtered)} pass")

    if not filtered:
        print("  Nothing matched filter. Exiting.")
        sys.exit(1)

    # Steps 3–5: Classify + extract + dedup + merge
    print("\nSTEP 3-5: Classify → extract → dedup → merge")
    added, total = run_pipeline(filtered)

    print(f"\n  Added to KB  : {added}")
    print(f"  KB total     : {total}")

    if added > 0:
        print("\nSTEP 5b: Rebuild vector store")
        rebuild_store()
    else:
        print("\nSTEP 5b: No new cards — store unchanged.")

    # Step 6: Bot tests
    print("\nSTEP 6: Bot tests")
    ok = run_bot_tests()
    if not ok:
        print("\nERROR: Bot tests failed.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"Final KB card count: {total}")
    print("=" * 60)
