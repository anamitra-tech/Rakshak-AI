"""
PIB Playwright harvester — searches PIB for cyber advisory press releases,
then runs the full pipeline inline:
  classify → quality gate → dedup → merge into kb/scams.json → rebuild store

Runs standalone:  python data/pib_harvest.py
"""
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import warnings
warnings.filterwarnings("ignore")

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

KB_PATH = Path(__file__).parent.parent / "kb" / "scams.json"
RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SEARCH_QUERIES = [
    "digital+arrest",
    "cyber+fraud",
    "OTP+scam",
    "fake+CBI",
    "digital+arrest+scam",
]
ARTICLES_PER_QUERY = 10
MAX_TOTAL = 40

VALID_LABELS = {
    "digital_arrest", "bank_otp_kyc", "investment_fraud",
    "qr_code_fraud", "lottery_prize_fraud", "smishing_link",
    "corporate_malware_bec", "sanchar_saathi_sim_swap",
    "fake_job_offer_apk", "aadhaar_biometric_freeze",
    "multi_call_escalation", "other",
}

ADVISORY_KW = {
    "fraud", "phish", "scam", "fake", "malware", "otp", "vishing",
    "smishing", "spoofed", "impersonat", "cyber", "arrest", "kyc",
    "upi", "sim swap", "aadhaar", "biometric", "invest", "lottery",
    "qr", "digital arrest", "cybercrime", "1930", "helpline",
    "warning", "advisory", "alert", "beware",
}

NAV_SIGNALS = {"accessibility options", "sitemap", "skip to main content"}

OVERLAP_THRESHOLD = 0.6
MIN_SUMMARY_WORDS = 20

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sentences(text: str, n: int = 3) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts[:n] if len(p) > 10)


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower())
    return s[:50].strip("_")


def _find_date(text: str) -> str:
    for pat in [
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
        r"\d{2}[/-]\d{2}[/-]\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group()
    return ""


def _has_advisory_signal(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in ADVISORY_KW)


def _text_for_dedup(card: dict) -> str:
    return card.get("summary") or card.get("what_to_do") or card.get("title") or ""


def _overlap(a: str, b: str) -> float:
    wa = set(a.lower().split())
    if not wa:
        return 0.0
    return len(wa & set(b.lower().split())) / len(wa)


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
        log.warning("Unrecognised label %r — skipping", resp.text.strip()[:80])
    except Exception as exc:
        log.warning("LLM error for %s: %s", card.get("id", "?"), exc)
    return None


def _passes_quality_gate(card: dict) -> bool:
    text = _text_for_dedup(card)
    words = text.lower().split()
    if len(words) < MIN_SUMMARY_WORDS:
        return False
    if not any(kw in text.lower() for kw in ADVISORY_KW):
        return False
    if any(sig in text.lower()[:120] for sig in NAV_SIGNALS):
        return False
    return True


def _prid_from_url(url: str) -> str | None:
    m = re.search(r"PRID=(\d+)", url, re.IGNORECASE)
    return m.group(1) if m else None


# ── Playwright scraper ────────────────────────────────────────────────────────

async def harvest_pib() -> list:
    cards = []
    seen_prids: set = set()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        for query in SEARCH_QUERIES:
            if len(cards) >= MAX_TOTAL:
                break

            search_url = f"https://pib.gov.in/search.aspx?reg=3&lang=1&k={query}"
            log.info("PIB search: %s", search_url)

            try:
                await page.goto(search_url, wait_until="networkidle", timeout=30000)
            except PlaywrightTimeout:
                log.warning("Timeout on search page: %s", query)
                continue

            # Extract article links from search results
            all_links = await page.query_selector_all("a[href]")
            article_hrefs = []
            for link in all_links:
                href = await link.get_attribute("href") or ""
                if re.search(r"PressRelease(Page|IframePage|Share)\.aspx.*PRID=", href, re.IGNORECASE):
                    prid = _prid_from_url(href)
                    if prid and prid not in seen_prids:
                        # Prefer the static Pressreleaseshare.aspx version
                        clean_url = f"https://pib.gov.in/Pressreleaseshare.aspx?PRID={prid}"
                        article_hrefs.append((prid, clean_url))

            log.info("  Found %d article links for query '%s'", len(article_hrefs), query)
            query_count = 0

            for prid, article_url in article_hrefs:
                if query_count >= ARTICLES_PER_QUERY or len(cards) >= MAX_TOTAL:
                    break
                if prid in seen_prids:
                    continue
                seen_prids.add(prid)

                try:
                    await page.goto(article_url, wait_until="networkidle", timeout=25000)
                except PlaywrightTimeout:
                    log.warning("  Timeout on article PRID=%s", prid)
                    continue

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Extract title
                title = ""
                for sel in ["h2", "h1", "title"]:
                    el = soup.select_one(sel)
                    if el:
                        title = el.get_text(strip=True)
                        break
                if not title or len(title) < 5:
                    title = f"PIB Advisory PRID {prid}"

                # Extract body
                body_el = (
                    soup.select_one(".ContentDiv")
                    or soup.select_one("article")
                    or soup.select_one("main")
                    or soup.find("body")
                )
                raw_text = re.sub(
                    r"\s+", " ",
                    (body_el or soup).get_text(separator=" ", strip=True)
                )

                if not _has_advisory_signal(raw_text):
                    log.info("  SKIP (no signal) PRID=%s — %s", prid, title[:50])
                    continue

                summary = _sentences(raw_text)
                date_str = _find_date(html)

                card = {
                    "id": f"pib_{_slug(title)}",
                    "scam_type": "auto_classify",
                    "title": title,
                    "summary": summary,
                    "red_flags": [],
                    "source": "PIB",
                    "source_url": article_url,
                    "date": date_str,
                    "raw_text": raw_text[:3000],
                }
                cards.append(card)
                query_count += 1
                log.info("  PIB OK  PRID=%s  %s", prid, title[:60])

                await asyncio.sleep(1)

        await browser.close()

    log.info("PIB Playwright: %d raw articles collected", len(cards))
    return cards


# ── Inline pipeline ───────────────────────────────────────────────────────────

def run_pipeline(raw_cards: list) -> int:
    kb_cards = json.loads(KB_PATH.read_text(encoding="utf-8"))
    kb_texts = [_text_for_dedup(c) for c in kb_cards]
    existing_ids = {c["id"] for c in kb_cards}

    classified = []
    for i, card in enumerate(raw_cards, 1):
        label = _classify(card)
        if label is None or label == "other":
            log.info("[%d/%d] SKIP  %s", i, len(raw_cards), card["id"][:40])
        else:
            card["scam_type"] = label
            classified.append(card)
            log.info("[%d/%d] %-35s  ->  %s", i, len(raw_cards), card["id"][:35], label)
        if i < len(raw_cards):
            time.sleep(1)

    print(f"\n  Classified : {len(classified)}")
    print(f"  Skipped    : {len(raw_cards) - len(classified)}")

    new_cards = []
    for card in classified:
        text = _text_for_dedup(card)
        if not _passes_quality_gate(card):
            log.info("GATE FAIL  %s", card["id"][:40])
            continue

        overlap = max((_overlap(text, kt) for kt in kb_texts if kt), default=0.0)
        if overlap > OVERLAP_THRESHOLD:
            log.info("DUP (%.2f)  %s", overlap, card["id"][:40])
        else:
            log.info("NEW (%.2f)  %s", overlap, card["id"][:40])
            new_cards.append(card)

    print(f"  New unique : {len(new_cards)}")

    added = 0
    for card in new_cards:
        if card["id"] in existing_ids:
            log.warning("ID collision — skipping %s", card["id"])
            continue

        kb_card = {
            "id": card["id"],
            "scam_type": card["scam_type"],
            "channel": "unknown",
            "languages": ["en"],
            "title": card.get("title", ""),
            "example_messages": [card.get("title", "")],
            "call_script": "",
            "red_flags": card.get("red_flags") or ["See official advisory for details"],
            "what_to_do": card.get("summary") or card.get("title", ""),
            "source": {
                "name": card.get("source", "PIB"),
                "url": card.get("source_url", ""),
                "date": card.get("date", "2024"),
            },
        }
        kb_cards.append(kb_card)
        existing_ids.add(card["id"])
        added += 1
        log.info("MERGED  %s  (%s)", kb_card["id"], kb_card["scam_type"])

    KB_PATH.write_text(json.dumps(kb_cards, indent=2, ensure_ascii=False), encoding="utf-8")
    return added, len(kb_cards)


def rebuild_store() -> None:
    log.info("Rebuilding vector store...")
    import subprocess
    import shutil
    store_path = Path(__file__).parent.parent / "rag" / "chroma_store"
    if store_path.exists():
        shutil.rmtree(store_path)
    result = subprocess.run(
        [sys.executable, "-m", "rag.build_store"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        log.error("build_store failed: %s", result.stderr[:400])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("PIB Playwright Harvester")
    print("=" * 60)

    # Step 1: Scrape
    print("\nSTEP 1: Playwright scrape")
    raw_cards = asyncio.run(harvest_pib())
    (RAW_DIR / "pib_playwright_cards.json").write_text(
        json.dumps(raw_cards, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  Raw articles: {len(raw_cards)}  ->  data/raw/pib_playwright_cards.json")

    if not raw_cards:
        print("\n  No articles found. Exiting.")
        sys.exit(0)

    # Step 2–4: Classify + dedup + merge
    print("\nSTEP 2–4: Classify → deduplicate → merge")
    added, total = run_pipeline(raw_cards)

    print(f"\n  Added to KB : {added}")
    print(f"  Total KB cards: {total}")

    # Step 5: Rebuild store only if new cards were added
    if added > 0:
        print("\nSTEP 5: Rebuilding vector store")
        rebuild_store()
        print(f"  Vector store rebuilt with {total} cards.")
    else:
        print("\nSTEP 5: No new cards — vector store unchanged.")

    print("\n" + "=" * 60)
    print(f"Final KB card count: {total}")
    print("=" * 60)
