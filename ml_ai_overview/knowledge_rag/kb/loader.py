import json
import logging
from pathlib import Path
from typing import List

from kb.schema import ScamCard

logger = logging.getLogger(__name__)

_SCAMS_FILE = Path(__file__).parent / "scams.json"


def load_cards() -> List[ScamCard]:
    with open(_SCAMS_FILE, encoding="utf-8") as f:
        raw = json.load(f)

    valid: List[ScamCard] = []
    for entry in raw:
        try:
            card = ScamCard(
                id=entry.get("id", ""),
                scam_type=entry.get("scam_type", ""),
                channel=entry.get("channel", ""),
                languages=entry.get("languages", []),
                title=entry.get("title", ""),
                example_messages=entry.get("example_messages", []),
                call_script=entry.get("call_script", ""),
                red_flags=entry.get("red_flags", []),
                what_to_do=entry.get("what_to_do", ""),
                source=entry.get("source", {}),
                if_already_opened=entry.get("if_already_opened", ""),
                post_open_keywords=entry.get("post_open_keywords", []),
                severity=entry.get("severity", ""),
            )
            card.validate()
            valid.append(card)
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping invalid scam card %r: %s", entry.get("id", "?"), exc)

    return valid


def get_by_type(scam_type: str) -> List[ScamCard]:
    return [c for c in load_cards() if c.scam_type == scam_type]
