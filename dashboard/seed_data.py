"""
Seed-data loader for the investigator dashboard.

Two real sources, merged into one node schema:

  1. feedback/data/feedback.db `corrections` rows with verdict == 'FRAUD' and
     a real phone number + non-empty text (read-only SQLite access -- no
     writes, no schema changes; feedback/store.py is untouched).
  2. rakshak_eval_testset.json's cases, scored through the actual, unmodified
     ml.detector.ScamDetector.predict() (a function call, not an edit) --
     FRAUD-level results only. These cases carry no phone number or
     timestamp in the source file, so a deterministic synthetic one is
     assigned per case and every such node is tagged
     source="eval_testset_synthetic" so it is never mistaken for a real
     complaint in the UI.

This is demo-scale data (37 nodes total as of this writing), not live
production volume -- labelled as such in the dashboard UI.
"""
import hashlib
import json
import sqlite3
from pathlib import Path

from ml.detector import ScamDetector
from dashboard.telecom_circles import lookup_circle

_ROOT = Path(__file__).resolve().parent.parent
_FEEDBACK_DB = _ROOT / "feedback" / "data" / "feedback.db"
_EVAL_TESTSET = _ROOT / "rakshak_eval_testset.json"

# Prefixes used only to give synthetic eval-testset numbers demo-visible
# spread across circles -- see telecom_circles.py for what each maps to.
_DEMO_PREFIXES = [
    "7838", "9820", "9880", "9840", "9830", "9825", "9847", "9977", "9435", "9720",
]

_CALLBACK_NUMBER_RE = __import__("re").compile(r"(?:\+91[-\s]?)?[6-9]\d{9}\b")


def _synthetic_phone(case_id: str) -> str:
    """Deterministic, plausible-shaped Indian mobile number for a case that
    has no real number attached. Same case_id always yields the same number
    so re-running the loader doesn't reshuffle the demo graph."""
    digest = hashlib.sha1(case_id.encode()).hexdigest()
    prefix = _DEMO_PREFIXES[int(digest[:8], 16) % len(_DEMO_PREFIXES)]
    remainder = "".join(str(int(c, 16) % 10) for c in digest[8:14])
    return f"+91{prefix}{remainder}"


def _synthetic_timestamp(case_id: str, base_iso: str = "2026-07-01T00:00:00+00:00") -> str:
    """Deterministic demo timestamp spread over ~30 days. Marked
    timestamp_is_synthetic=True on the node so graph_model.py never treats
    it as real temporal evidence."""
    from datetime import datetime, timedelta, timezone
    digest = hashlib.sha1(case_id.encode()).hexdigest()
    offset_minutes = int(digest[:8], 16) % (30 * 24 * 60)
    base = datetime.fromisoformat(base_iso)
    return (base + timedelta(minutes=offset_minutes)).isoformat()


def _extract_mentioned_numbers(text: str, own_number: str) -> list:
    found = set()
    for m in _CALLBACK_NUMBER_RE.finditer(text or ""):
        digits = "".join(ch for ch in m.group() if ch.isdigit())
        if len(digits) == 10:
            digits = "91" + digits
        candidate = "+" + digits
        if candidate != own_number:
            found.add(candidate)
    return sorted(found)


def _load_feedback_db_nodes() -> list:
    if not _FEEDBACK_DB.exists():
        return []
    conn = sqlite3.connect(_FEEDBACK_DB)
    try:
        rows = conn.execute(
            "SELECT id, timestamp_utc, channel, session_id, original_text, "
            "verdict, rule_categories FROM corrections "
            "WHERE verdict = 'FRAUD' AND session_id IS NOT NULL AND original_text != ''"
        ).fetchall()
    finally:
        conn.close()

    nodes = []
    for row_id, ts, channel, session_id, text, verdict, rule_categories_json in rows:
        phone = session_id
        rule_categories = json.loads(rule_categories_json or "[]")
        nodes.append({
            "node_id": phone,
            "node_type": "phone",
            "source": "feedback_db",
            "rule_categories": rule_categories,
            "risk_level": verdict,
            "score": None,  # not stored by feedback/store.py at correction time
            "text_excerpt": text,
            "channel": channel,
            "timestamp_utc": ts,
            "timestamp_is_synthetic": False,
            "telecom_circle": lookup_circle(phone),
            "self_reported_city": None,
            "self_reported_state": None,
            "mentioned_numbers": _extract_mentioned_numbers(text, phone),
        })
    return nodes


def _load_eval_testset_nodes(detector: ScamDetector) -> list:
    if not _EVAL_TESTSET.exists():
        return []
    data = json.loads(_EVAL_TESTSET.read_text(encoding="utf-8"))
    nodes = []
    for case in data.get("cases", []):
        result = detector.predict(case["text"])
        if result["risk_level"] != "FRAUD":
            continue
        phone = _synthetic_phone(case["id"])
        nodes.append({
            "node_id": phone,
            "node_type": "phone",
            "source": "eval_testset_synthetic",
            "rule_categories": result["rule_categories"],
            "risk_level": result["risk_level"],
            "score": result["score"],
            "text_excerpt": case["text"],
            "channel": "eval_testset",
            "timestamp_utc": _synthetic_timestamp(case["id"]),
            "timestamp_is_synthetic": True,
            "telecom_circle": lookup_circle(phone),
            "self_reported_city": None,
            "self_reported_state": None,
            "mentioned_numbers": _extract_mentioned_numbers(case["text"], phone),
            "category": case.get("category"),
        })
    return nodes


def load_seed_nodes() -> list:
    detector = ScamDetector()
    nodes = _load_feedback_db_nodes() + _load_eval_testset_nodes(detector)
    # De-dup by node_id, keeping the first (real feedback_db rows loaded
    # first, so a collision favors the real row over a synthetic one).
    seen = set()
    deduped = []
    for n in nodes:
        if n["node_id"] in seen:
            continue
        seen.add(n["node_id"])
        deduped.append(n)
    return deduped


if __name__ == "__main__":
    nodes = load_seed_nodes()
    print(f"total nodes: {len(nodes)}")
    by_source = {}
    for n in nodes:
        by_source[n["source"]] = by_source.get(n["source"], 0) + 1
    print("by source:", by_source)
    print(json.dumps(nodes[0], indent=2, ensure_ascii=False))
