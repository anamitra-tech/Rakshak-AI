"""
Deduplicate classified cards against the existing KB.
Reads  data/classified/all_cards.json  +  kb/scams.json
Writes data/final/new_cards.json
"""
import json
import logging
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

CLASSIFIED_PATH = Path(__file__).parent / "classified" / "all_cards.json"
KB_PATH = Path(__file__).parent.parent / "kb" / "scams.json"
FINAL_DIR = Path(__file__).parent / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

OVERLAP_THRESHOLD = 0.6

CYBER_SIGNAL = {
    "fraud", "scam", "phishing", "fake", "arrest", "otp",
    "malware", "cyber", "kyc", "biometric", "sim", "aadhaar",
    "investment", "lottery", "qr", "upi", "payment", "advisory",
    "alert", "warn", "victim", "criminal", "money", "account",
}
MIN_SUMMARY_WORDS = 20


def _text(card: dict) -> str:
    """Representative text for a KB card (uses what_to_do or summary)."""
    return card.get("summary") or card.get("what_to_do") or card.get("title") or ""


def _overlap(new_text: str, existing_text: str) -> float:
    new_words = set(new_text.lower().split())
    if not new_words:
        return 0.0
    existing_words = set(existing_text.lower().split())
    return len(new_words & existing_words) / len(new_words)


if __name__ == "__main__":
    if not CLASSIFIED_PATH.exists():
        print("ERROR: data/classified/all_cards.json not found. Run classifier.py first.")
        raise SystemExit(1)

    new_cards = json.loads(CLASSIFIED_PATH.read_text(encoding="utf-8"))
    kb_cards = json.loads(KB_PATH.read_text(encoding="utf-8"))
    log.info("New candidates: %d | Existing KB: %d", len(new_cards), len(kb_cards))

    kb_texts = [_text(c) for c in kb_cards]

    unique = []
    dup_count = 0

    for card in new_cards:
        card_text = _text(card)
        words = card_text.lower().split()

        if len(words) < MIN_SUMMARY_WORDS:
            log.info("SKIP (short/stub): %s", card.get("id", "?")[:50])
            dup_count += 1
            continue

        if not any(kw in card_text.lower() for kw in CYBER_SIGNAL):
            log.info("SKIP (no cyber signal): %s", card.get("id", "?")[:50])
            dup_count += 1
            continue

        # Reject navigation-header artifacts (common on JS-rendered sites)
        nav_signals = {"accessibility options", "sitemap", "skip to main content"}
        if any(sig in card_text.lower()[:120] for sig in nav_signals):
            log.info("SKIP (nav artifact): %s", card.get("id", "?")[:50])
            dup_count += 1
            continue

        max_overlap = max(
            (_overlap(card_text, kt) for kt in kb_texts if kt),
            default=0.0,
        )

        if max_overlap > OVERLAP_THRESHOLD:
            log.info("DUP  (overlap=%.2f)  %s", max_overlap, card.get("id", "?")[:50])
            dup_count += 1
        else:
            log.info("NEW  (overlap=%.2f)  %s", max_overlap, card.get("id", "?")[:50])
            unique.append(card)

    out_path = FINAL_DIR / "new_cards.json"
    out_path.write_text(json.dumps(unique, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✓ {len(unique)} new cards ready to merge  →  data/final/new_cards.json")
    print(f"✗ {dup_count} duplicates skipped (overlap > {OVERLAP_THRESHOLD})")
