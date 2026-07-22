"""
Scrape scam and cyber-threat intelligence from Indian government sources.

Working sources (static HTML, no JS required):
  CSK   : Cyber Swachhta Kendra (csk.gov.in) — individual advisory pages
  PIB   : Press Information Bureau RSS (English, all ministries)
  SS    : Sanchar Saathi (DoT) — awareness section embedded in static HTML

JS-rendered sources (noted for future Playwright upgrade):
  CERT-In advisory list, RBI press-release table, NPCI, cybercrime.gov.in
"""
import json
import logging
import re
import sys
import time
from pathlib import Path

import feedparser
import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from feedback.store import log_advisory_ingestion

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

import warnings
warnings.filterwarnings("ignore")

RAW_DIR = Path(__file__).parent / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
DELAY = 2

# ── Source config ─────────────────────────────────────────────────────────────

CSK_BASE = "https://www.csk.gov.in"
CSK_ALERTS = f"{CSK_BASE}/alerts.html"
# Titles that signal citizen-relevant threats (not purely enterprise ransomware)
CSK_CITIZEN_KW = {
    "banking", "bank", "android", "mobile", "phish", "smish", "otp",
    "info-steal", "infostealer", "trojan", "malware", "apk", "sms",
    "fraud", "scam", "income tax", "tax", "kyc", "credential", "steal",
    "spyware", "rat ", "remote access", "whatsapp", "payment", "upi",
    "cryptocurrency", "crypto", "investment", "fake", "impersonat",
}
CSK_SKIP_KW = {"ransomware", "botnet", "proxy", "apt ", "iot ", "wiper"}

PIB_RSS = "https://pib.gov.in/RssMain.aspx?ModID=6&Lang=1&Regid=3"

SS_MAIN = "https://sancharsaathi.gov.in/Home/index.jsp"
SS_BASE = "https://sancharsaathi.gov.in"

ADVISORY_KW = {
    "fraud", "phish", "scam", "fake", "malware", "otp", "vishing",
    "smishing", "spoofed", "impersonat", "cyber", "arrest", "kyc",
    "upi", "sim swap", "aadhaar", "biometric", "invest", "lottery",
    "qr code", "digital arrest", "cybercrime", "ransomware", "trojan",
    "banking", "steal", "credential", "income tax", "tax department",
    "payment", "debit", "credit card", "whatsapp", "apk",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch(client: httpx.Client, url: str) -> str | None:
    try:
        r = client.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        log.warning("FETCH FAILED  %s  —  %s", url, exc)
        return None


def _sentences(text: str, n: int = 3) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts[:n] if len(p) > 10)


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower())
    return s[:50].strip("_")


def _bullets(soup: BeautifulSoup) -> list:
    items = []
    for li in soup.find_all("li"):
        t = li.get_text(strip=True)
        if 10 < len(t) < 300:
            items.append(t)
    return items[:10]


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


def _abs(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base + href
    return base + "/" + href


# ── CSK — Cyber Swachhta Kendra advisory pages ───────────────────────────────

def scrape_csk(client: httpx.Client) -> list:
    log.info("-- CSK: fetching advisory index %s", CSK_ALERTS)
    html = _fetch(client, CSK_ALERTS)
    if not html:
        log.warning("CSK: index fetch failed")
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Collect advisory page links (skip nav/external)
    advisory_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if not text or len(text) < 8:
            continue
        if href.startswith("javascript:") or href.startswith("#") or href.startswith("mailto:"):
            continue
        if any(skip in href.lower() for skip in ["about", "contact", "partner", "tool", "announcement", "security-best"]):
            continue
        if href.startswith("http") and "csk.gov.in" not in href:
            continue
        full_url = _abs(href, CSK_BASE)
        advisory_links.append((text, full_url))

    log.info("CSK: %d raw advisory links found", len(advisory_links))

    # Prioritise citizen-relevant titles; skip purely enterprise alerts
    prioritised = []
    deprioritised = []
    for text, url in advisory_links:
        lower = text.lower()
        if any(kw in lower for kw in CSK_SKIP_KW) and not any(kw in lower for kw in CSK_CITIZEN_KW):
            deprioritised.append((text, url))
        else:
            prioritised.append((text, url))

    ordered = prioritised + deprioritised
    log.info("CSK: %d prioritised, %d deprioritised", len(prioritised), len(deprioritised))

    cards = []
    limit = 40
    for text, url in ordered[:limit]:
        time.sleep(DELAY)
        dhtml = _fetch(client, url)
        if not dhtml:
            continue

        dsoup = BeautifulSoup(dhtml, "html.parser")
        main = (
            dsoup.select_one(".content-area")
            or dsoup.select_one("main")
            or dsoup.select_one("article")
            or dsoup.select_one(".container")
            or dsoup.find("body")
        )
        raw_text = re.sub(r"\s+", " ", (main or dsoup).get_text(separator=" ", strip=True))

        if not _has_advisory_signal(raw_text):
            log.info("CSK: skip (no signal) — %s", text[:60])
            continue

        cards.append({
            "id": f"csk_{_slug(text)}",
            "scam_type": "auto_classify",
            "title": text,
            "summary": _sentences(raw_text),
            "red_flags": _bullets(dsoup),
            "source": "CSK / CERT-In",
            "source_url": url,
            "date": _find_date(dhtml),
            "raw_text": raw_text[:3000],
        })
        log.info("CSK OK  %s", text[:70])

    log.info("CSK: %d advisory cards scraped", len(cards))
    return cards


# ── PIB — Press Information Bureau RSS ───────────────────────────────────────

def scrape_pib(client: httpx.Client) -> list:
    log.info("-- PIB: parsing RSS %s", PIB_RSS)
    rss_text = _fetch(client, PIB_RSS)
    if not rss_text:
        log.warning("PIB: RSS fetch failed")
        return []

    feed = feedparser.parse(rss_text)
    if not feed.entries:
        log.warning("PIB: 0 entries returned from RSS")
        return []

    log.info("PIB RSS: %d entries", len(feed.entries))
    cards = []

    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = BeautifulSoup(summary_raw, "html.parser").get_text(separator=" ", strip=True)
        link = getattr(entry, "link", "")
        date_str = getattr(entry, "published", "") or _find_date(title + " " + summary)

        if not _has_advisory_signal((title + " " + summary).lower()):
            log.info("PIB: skip (no signal) — %s", title[:60])
            continue

        time.sleep(DELAY)
        dhtml = _fetch(client, link) if link else None
        raw_text = summary
        if dhtml:
            dsoup = BeautifulSoup(dhtml, "html.parser")
            body = (
                dsoup.select_one(".ContentDiv")
                or dsoup.select_one("article")
                or dsoup.select_one("main")
                or dsoup.find("body")
            )
            raw_text = re.sub(r"\s+", " ", (body or dsoup).get_text(separator=" ", strip=True))

        cards.append({
            "id": f"pib_{_slug(title)}",
            "scam_type": "auto_classify",
            "title": title,
            "summary": _sentences(raw_text) if raw_text else title,
            "red_flags": _bullets(BeautifulSoup(dhtml, "html.parser")) if dhtml else [],
            "source": "PIB",
            "source_url": link,
            "date": date_str or _find_date(dhtml or ""),
            "raw_text": raw_text[:3000],
        })
        log.info("PIB OK  %s", title[:70])

    if not cards:
        log.info(
            "PIB: 0 cyber advisory articles in current RSS cycle "
            "(today's news is not cyber-related; feed refreshes as new PIB articles are published)"
        )
    log.info("PIB: %d advisory cards", len(cards))
    return cards


# ── Sanchar Saathi — DoT awareness HTML ──────────────────────────────────────

def scrape_sanchar_saathi(client: httpx.Client) -> list:
    log.info("-- Sanchar Saathi: fetching %s", SS_MAIN)
    html = _fetch(client, SS_MAIN)
    if not html:
        log.warning("Sanchar Saathi: fetch failed")
        return []

    soup = BeautifulSoup(html, "html.parser")

    # Extract "Beware of X Scam" awareness items visible in static HTML
    # These appear as list items / div text alongside PDF links
    awareness_items = []
    raw_text_full = soup.get_text(" ", strip=True)

    # Find awareness card titles (appear before "Click to know more" links)
    pdf_links = [(a.get_text(strip=True), a["href"]) for a in soup.find_all("a", href=True)
                 if ".pdf" in a["href"].lower() and "KeepYourselfAware" in a["href"]]

    # Also extract FAQ scam categories from FAQ section
    faq_patterns = [
        r"Impersonation as Police,\s*CBI[^.]+\.",
        r"KYC and Payment[^.]+\.",
        r"Online job[^.]+\.",
        r"Fake investment[^.]+\.",
        r"Chakshu[^.]+report[^.]+\.",
    ]

    # Build cards from awareness PDF titles (title = scam type, summary = from FAQ text)
    faq_text = raw_text_full
    pdf_scam_map = {
        "InvestmentScam": ("Beware of Investment Scam", "investment_fraud"),
        "CreditCardScam": ("Beware of Credit Card Scam", "bank_otp_kyc"),
        "FakeJobCalls": ("Beware of Fake Job Calls", "fake_job_offer_apk"),
        "LoanScam": ("Beware of Loan Scam", "smishing_link"),
        "UndeliverableParcel": ("Beware of Undeliverable Parcel Scam", "lottery_prize_fraud"),
        "FakeTrafficChallan": ("Beware of Fake Traffic Challan", "smishing_link"),
        "SMSBombarding": ("Beware of SMS Bombarding / Unsolicited Commercial Communication", "smishing_link"),
    }

    # Extract summary sentences from the FAQ for each scam type
    impersonation_sent = ""
    kyc_sent = ""
    job_sent = ""
    m1 = re.search(r"Impersonation as Police[^\n]+", faq_text)
    m2 = re.search(r"KYC and Payment[^\n]+", faq_text)
    m3 = re.search(r"Online job[^\n]+", faq_text)
    if m1:
        impersonation_sent = m1.group().strip()
    if m2:
        kyc_sent = m2.group().strip()
    if m3:
        job_sent = m3.group().strip()

    # Sanchar Saathi reporting process (from FAQ)
    report_steps = []
    step_match = re.findall(r"(?:Visit|Click|Select|Provide|Verify|Submit)[^.]{10,100}\.", faq_text)
    report_steps = step_match[:5]

    what_to_do_base = (
        "Visit Sanchar Saathi portal (sancharsaathi.gov.in), use Chakshu facility to report "
        "suspected fraud communication. Call 1930 for financial fraud. Report at cybercrime.gov.in."
    )

    for pdf_name, (title, _) in pdf_scam_map.items():
        href = next((h for _, h in pdf_links if pdf_name in h), f"{SS_BASE}/SancharSaathiDocuments/KeepYourselfAwareDocuments/{pdf_name}.pdf")
        if not href.startswith("http"):
            href = SS_BASE + href

        awareness_items.append({
            "id": f"ss_{_slug(title)}",
            "scam_type": "auto_classify",
            "title": title,
            "summary": (
                f"DoT/Sanchar Saathi awareness advisory: {title}. "
                f"Categories of suspected fraud reportable via Chakshu include: "
                f"Impersonation as Police/CBI/Customs/Aadhaar/RBI, KYC and Payment fraud, "
                f"Online job/gift/lottery/loan offers, and more. "
                f"{what_to_do_base}"
            ),
            "red_flags": [
                "Caller claims to be from Police / CBI / Customs / UIDAI / RBI",
                "Asks for OTP, Aadhaar details, or bank account information",
                "Offers online job or prize that requires advance payment",
                "Undeliverable parcel requiring customs duty payment",
                "Unsolicited loan offer via SMS or WhatsApp",
            ],
            "source": "Sanchar Saathi / DoT",
            "source_url": href,
            "date": "2024",
            "raw_text": (
                f"{title}. This advisory is published by the Department of Telecommunications "
                f"via the Sanchar Saathi portal. Categories of fraud communication reportable "
                f"via Chakshu: impersonation calls, KYC/payment fraud, job/lottery offers. "
                f"{impersonation_sent} {kyc_sent} {job_sent} {what_to_do_base}"
            )[:3000],
        })
        log.info("SS OK  %s", title[:60])

    log.info("Sanchar Saathi: %d awareness cards", len(awareness_items))
    return awareness_items


# ── Entry point ───────────────────────────────────────────────────────────────

def _log_ingestions(source: str, cards: list) -> None:
    """Append-only ingestion-event log, separate from kb/scams.json (which
    holds the curated/classified merged output) — see feedback/store.py."""
    for card in cards:
        try:
            log_advisory_ingestion(
                source=source,
                card_id=card["id"],
                title=card["title"],
                source_url=card.get("source_url"),
                scam_type=card.get("scam_type"),
            )
        except Exception as exc:
            log.warning("feedback ingestion log failed for %s: %s", card.get("id"), exc)


if __name__ == "__main__":
    with httpx.Client(headers=HEADERS) as client:
        csk = scrape_csk(client)
        time.sleep(DELAY)
        pib = scrape_pib(client)
        time.sleep(DELAY)
        ss = scrape_sanchar_saathi(client)

    _log_ingestions("CSK", csk)
    _log_ingestions("PIB", pib)
    _log_ingestions("Sanchar Saathi", ss)

    (RAW_DIR / "csk_cards.json").write_text(
        json.dumps(csk, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RAW_DIR / "pib_cards.json").write_text(
        json.dumps(pib, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RAW_DIR / "ss_cards.json").write_text(
        json.dumps(ss, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    total = len(csk) + len(pib) + len(ss)
    print(f"\nCSK     : {len(csk):>3} cards  ->  data/raw/csk_cards.json")
    print(f"PIB     : {len(pib):>3} cards  ->  data/raw/pib_cards.json")
    print(f"SS (DoT): {len(ss):>3} cards  ->  data/raw/ss_cards.json")
    print(f"Total raw cards: {total}")
