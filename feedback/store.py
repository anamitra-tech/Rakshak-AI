"""
Append-only feedback/ingestion store — READ/LOG ONLY.

Nothing in this module feeds back into any live decision (ml/detector.py,
voice/voice_fraud.py, ml/session.py, casefile/case_generator.py are untouched).
It exists purely to collect two kinds of events for later offline analysis:

  1. User corrections on a verdict shown to them (Android "Check a call"
     screen, Android in-call warning, WhatsApp bot reply) — did the model
     get it right?
  2. Raw advisory-card ingestion events from data/scraper.py (CSK / PIB /
     Sanchar Saathi) — separate from kb/scams.json, which stores the
     curated/classified/merged output, not a log of ingestion events.

SQLite so both `api/server.py` (port 8000) and `webhook/app.py` (port 8001) —
separate processes — can append to the same store without a DB server.
WAL mode lets both write concurrently without blocking each other.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).parent / "data" / "feedback.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            channel TEXT NOT NULL,
            session_id TEXT,
            original_text TEXT NOT NULL,
            verdict TEXT NOT NULL,
            rule_categories TEXT NOT NULL,
            user_correction TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS advisory_ingestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            source TEXT NOT NULL,
            card_id TEXT NOT NULL,
            title TEXT NOT NULL,
            source_url TEXT,
            scam_type TEXT
        )
    """)
    return conn


def log_correction(
    *,
    channel: str,
    original_text: str,
    verdict: str,
    rule_categories: list,
    user_correction: str,
    session_id: str | None = None,
) -> int:
    """channel: 'android_check_call' | 'android_warning' | 'whatsapp'.
    user_correction: 'confirmed_correct' | 'not_a_scam' | 'should_have_been_flagged'.
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO corrections "
            "(timestamp_utc, channel, session_id, original_text, verdict, rule_categories, user_correction) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                channel,
                session_id,
                original_text,
                verdict,
                json.dumps(rule_categories or []),
                user_correction,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def log_advisory_ingestion(
    *,
    source: str,
    card_id: str,
    title: str,
    source_url: str | None = None,
    scam_type: str | None = None,
) -> int:
    """source: 'CSK' | 'PIB' | 'Sanchar Saathi'. One row per scraped card per
    scraper run — this is an ingestion event log, not a dedup'd table; the
    curated/merged output still lives in kb/scams.json."""
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO advisory_ingestions "
            "(timestamp_utc, source, card_id, title, source_url, scam_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                source,
                card_id,
                title,
                source_url,
                scam_type,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch_recent_corrections(limit: int = 50) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, timestamp_utc, channel, session_id, original_text, verdict, rule_categories, user_correction "
            "FROM corrections ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        cols = ["id", "timestamp_utc", "channel", "session_id", "original_text", "verdict", "rule_categories", "user_correction"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def fetch_recent_advisory_ingestions(limit: int = 50) -> list:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, timestamp_utc, source, card_id, title, source_url, scam_type "
            "FROM advisory_ingestions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        cols = ["id", "timestamp_utc", "source", "card_id", "title", "source_url", "scam_type"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()
