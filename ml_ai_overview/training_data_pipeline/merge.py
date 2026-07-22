"""
Merge deduplicated new cards into kb/scams.json.
Transforms scraped card schema → KB schema.
Does NOT rebuild the vector store.
"""
import json
import logging
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

NEW_CARDS_PATH = Path(__file__).parent / "final" / "new_cards.json"
KB_PATH = Path(__file__).parent.parent / "kb" / "scams.json"


def _to_kb_schema(card: dict) -> dict:
    """Convert scraped card format to the kb/scams.json schema."""
    title = card.get("title", "").strip()
    summary = card.get("summary", "").strip()
    raw = card.get("raw_text", "").strip()
    red_flags = card.get("red_flags") or []

    # what_to_do: prefer explicit field, then first actionable sentence from raw
    what_to_do = card.get("what_to_do", "")
    if not what_to_do:
        # look for sentences with action verbs in the advisory text
        body = summary or raw
        action_sents = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+", body)
            if re.search(r"\b(do not|never|avoid|report|call|hang up|disconnect|warn)\b", s, re.I)
        ]
        what_to_do = " ".join(action_sents[:2]) if action_sents else (summary or title)

    # example_messages: extract short sentences (< 120 chars) from raw that sound like scam lures
    example_messages = []
    for sent in re.split(r"(?<=[.!?])\s+", raw):
        sent = sent.strip()
        if 20 < len(sent) < 120 and re.search(
            r"\b(OTP|arrest|fraud|kyc|biometric|account|click|download|pay|prize|won|send)\b",
            sent, re.I
        ):
            example_messages.append(sent)
        if len(example_messages) >= 3:
            break
    if not example_messages:
        example_messages = [title]

    # red_flags: use scraped bullets if any, else derive from keywords in raw
    if not red_flags:
        red_flags = ["See official advisory for full details"]

    return {
        "id": card["id"],
        "scam_type": card["scam_type"],
        "channel": "unknown",
        "languages": ["en"],
        "title": title,
        "example_messages": example_messages,
        "call_script": "",
        "red_flags": red_flags,
        "what_to_do": what_to_do or summary or title,
        "source": {
            "name": card.get("source", "Official Advisory"),
            "url": card.get("source_url", ""),
            "date": card.get("date", "2024"),
        },
    }


if __name__ == "__main__":
    if not NEW_CARDS_PATH.exists():
        print("ERROR: data/final/new_cards.json not found. Run dedup.py first.")
        raise SystemExit(1)

    new_cards = json.loads(NEW_CARDS_PATH.read_text(encoding="utf-8"))
    kb_cards = json.loads(KB_PATH.read_text(encoding="utf-8"))

    existing_ids = {c["id"] for c in kb_cards}
    added = 0

    for card in new_cards:
        if card["id"] in existing_ids:
            log.warning("ID collision — skipping %s (already in KB)", card["id"])
            continue
        kb_card = _to_kb_schema(card)
        kb_cards.append(kb_card)
        existing_ids.add(card["id"])
        added += 1
        log.info("MERGED  %s  (%s)", kb_card["id"], kb_card["scam_type"])

    KB_PATH.write_text(json.dumps(kb_cards, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✓ Added {added} new cards to kb/scams.json")
    print(f"✓ Total cards in KB: {len(kb_cards)}")
    print("  (Vector store NOT rebuilt — run rag/build_store.py separately)")
