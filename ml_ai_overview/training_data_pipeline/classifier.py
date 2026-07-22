"""
Auto-classify raw scraped cards using the LLM.
Reads data/raw/*.json  →  writes data/classified/all_cards.json
"""
import json
import logging
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from llm.client import generate

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

RAW_DIR = Path(__file__).parent / "raw"
CLASSIFIED_DIR = Path(__file__).parent / "classified"
CLASSIFIED_DIR.mkdir(parents=True, exist_ok=True)

VALID_LABELS = {
    "digital_arrest", "bank_otp_kyc", "investment_fraud",
    "qr_code_fraud", "lottery_prize_fraud", "smishing_link",
    "corporate_malware_bec", "sanchar_saathi_sim_swap",
    "fake_job_offer_apk", "aadhaar_biometric_freeze",
    "multi_call_escalation", "other",
}

_CLASSIFY_PROMPT = """\
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


def classify_card(card: dict) -> str | None:
    prompt = _CLASSIFY_PROMPT.format(
        title=card.get("title", ""),
        summary=card.get("summary", "")[:400],
    )
    try:
        resp = generate(prompt)
        label = resp.text.strip().split()[0].lower().rstrip(".,")
        if label in VALID_LABELS:
            return label
        # try second word in case the model adds punctuation
        words = resp.text.strip().lower().split()
        for w in words:
            cleaned = w.rstrip(".,:")
            if cleaned in VALID_LABELS:
                return cleaned
        log.warning("Unrecognised label %r for card %s — skipping", resp.text.strip(), card["id"])
        return None
    except Exception as exc:
        log.warning("LLM call failed for %s: %s", card["id"], exc)
        return None


def load_raw() -> list:
    cards = []
    for fname in ("csk_cards.json", "pib_cards.json", "ss_cards.json"):
        path = RAW_DIR / fname
        if not path.exists():
            log.warning("Missing raw file: %s", path)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        log.info("Loaded %d cards from %s", len(data), fname)
        cards.extend(data)
    return cards


if __name__ == "__main__":
    raw = load_raw()
    to_classify = [c for c in raw if c.get("scam_type") == "auto_classify"]
    log.info("%d cards to classify", len(to_classify))

    classified = []
    skipped = 0

    for i, card in enumerate(to_classify, 1):
        label = classify_card(card)
        if label is None or label == "other":
            log.info("[%d/%d] SKIP  %s", i, len(to_classify), card["id"])
            skipped += 1
        else:
            card["scam_type"] = label
            classified.append(card)
            log.info("[%d/%d] %-30s  →  %s", i, len(to_classify), card["id"][:30], label)

        if i < len(to_classify):
            time.sleep(1)

    out_path = CLASSIFIED_DIR / "all_cards.json"
    out_path.write_text(json.dumps(classified, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n✓ Classified : {len(classified)} cards  →  data/classified/all_cards.json")
    print(f"✗ Skipped    : {skipped} cards (label=other or LLM error)")
