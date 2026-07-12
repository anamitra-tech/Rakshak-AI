import base64
import re
import smtplib
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

import requests
from fastapi import FastAPI, Request, Form
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from twilio.rest import Client as TwilioRestClient
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"))
sys.path.insert(0, _ROOT)

from graph.fraud_graph import (
    build_fraud_graph_with_entities,
    get_graph_summary,
    get_hard_links,
    get_ring_clusters,
)
from ml.detector import ScamDetector
from ml.session import FraudSessionDetector
from voice.voice_fraud import analyze_transcript
from feedback.store import log_correction

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# ── /whatsapp/webhook — same classification pipeline CheckCallActivity uses
# (analyze_voice + analyze_session), NOT the LLM/RAG bot.agent.chat() pipeline
# that /webhook above uses. Separate ScamDetector/FraudSessionDetector
# instances, deliberately: this endpoint mirrors the Android app's Phase 1
# deterministic pipeline exactly, not the richer WhatsApp-bot RAG pipeline.
DETECTOR = ScamDetector()
SESSION = FraudSessionDetector(DETECTOR)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# Real gap found 2026-07-12: neither webhook here ever extracted anything
# about an attached media item (only Body/From, and for /webhook, NumMedia
# for geo-logging only) — a "Statement of Account6.25.zip ... forward kar
# dijiye ... computer par open kijiye" message reached the classifier as
# caption text ALONE, with no way for any pattern (including
# malware_attachment_delivery, see ml/detector.py) to ever see the risky
# ".zip" extension unless the sender happened to type it into the caption
# themselves. Twilio's webhook reliably provides MediaContentType{N} for
# every attached media item (documented, stable API surface); it does NOT
# reliably provide the sender's original filename as a plain form field —
# that requires a live HTTP fetch of MediaUrl{N} and reading a
# Content-Disposition header, which may or may not be present depending on
# how the media was relayed. _media_descriptor() below tries that fetch
# best-effort (short timeout, never raises, degrades to a MIME-derived
# extension guess on any failure) rather than assuming either the fetch
# always works or that it's not worth attempting.
_RISKY_MIME_TO_EXT = {
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
    "application/x-msdownload": ".exe",
    "application/x-ms-dos-executable": ".exe",
    "application/x-msdos-program": ".exe",
    "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    "application/vnd.ms-word.document.macroenabled.12": ".docm",
    "application/javascript": ".js",
    "text/javascript": ".js",
    "application/x-javascript": ".js",
}


def _media_descriptor(media_url: str, content_type: str) -> str | None:
    """Returns a short bracketed string to append to the message text sent
    to the classifier (e.g. "[Attached file: Statement of Account6.25.zip]"
    or, if the real filename couldn't be fetched, "[Attached file type:
    .zip]") — or None if there's no media or nothing informative to add.
    Never raises; a failed fetch degrades to the MIME-derived guess, never
    blocks the reply."""
    if not media_url or not content_type:
        return None

    filename = None
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            resp = requests.head(
                media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                timeout=5, allow_redirects=True,
            )
            disposition = resp.headers.get("Content-Disposition", "")
            m = re.search(r'filename="?([^";]+)"?', disposition)
            if m:
                filename = m.group(1).strip()
        except Exception as e:
            logging.info(f"_media_descriptor: filename fetch failed (falling back to MIME type): {e}")

    if filename:
        return f"[Attached file: {filename}]"

    ext = _RISKY_MIME_TO_EXT.get(content_type.lower())
    if ext:
        return f"[Attached file type: {ext}]"

    # Not a recognized risky type and no filename obtained — still note that
    # *something* was attached, since even that bare fact is more than the
    # classifier had before, without inventing a filename or extension.
    return f"[Attachment, type: {content_type}]"


_RISK_RANK = {"REAL": 0, "SUSPICIOUS": 1, "FRAUD": 2}

_HEADLINES = {
    "FRAUD": ("🔴 SCAM", "This looks like a scam. Do not share any code or send money.",
              "यह एक धोखाधड़ी लग रही है। कोई भी कोड या पैसा साझा न करें।"),
    "SUSPICIOUS": ("🟡 SUSPICIOUS", "This could be risky. Be careful and verify before doing anything.",
                   "यह जोखिम भरा हो सकता है। कुछ भी करने से पहले सावधानी से जांच लें।"),
    "REAL": ("🟢 SAFE", "This looks safe. Stay alert anyway.",
             "यह सुरक्षित लगता है। फिर भी सतर्क रहें।"),
}

_ACTION_EN = {
    "FRAUD": "Hang up / stop replying. Report at cybercrime.gov.in or call 1930.",
    "SUSPICIOUS": "Do not act on this. Verify independently before doing anything.",
    "REAL": "No action needed. Stay alert for follow-up messages.",
}
_ACTION_HI = {
    "FRAUD": "फोन काट दें / जवाब देना बंद करें। cybercrime.gov.in पर रिपोर्ट करें या 1930 पर कॉल करें।",
    "SUSPICIOUS": "इस पर अभी कोई कार्रवाई न करें। कुछ भी करने से पहले स्वयं जांच लें।",
    "REAL": "कोई कार्रवाई आवश्यक नहीं। फिर भी आगे के संदेशों से सतर्क रहें।",
}

# In-memory per-number language preference — same pattern as bot.agent's
# _sessions (no DB layer exists anywhere in this project; consistent with
# that). "en" | "hi" | "both" (default).
_lang_prefs: dict[str, str] = {}
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_LANG_COMMANDS = {
    "english": "en", "eng": "en",
    "hindi": "hi", "hi": "hi", "hindi mein": "hi",
    "both": "both", "donon": "both", "दोनों": "both",
}

# In-memory per-number "last verdict shown" — same no-DB-layer pattern as
# _lang_prefs above. Holds just enough to log a correction if the very next
# message is feedback on it; never read by any classification path.
_last_verdict: dict[str, dict] = {}

_FEEDBACK_POSITIVE = {"👍", "correct", "right", "sahi", "sahi hai", "yes correct"}
_FEEDBACK_NEGATIVE = {
    "👎", "wrong", "incorrect", "galat", "galat hai",
    "not a scam", "this wasn't a scam", "this wasn't actually a scam",
    "should have been flagged", "missed this", "yeh scam nahi tha",
}


def _resolve_feedback(text: str) -> bool | None:
    """None if `text` isn't a feedback reply; else True (confirmed correct)
    or False (user is correcting the verdict)."""
    stripped = text.strip().lower()
    if stripped in _FEEDBACK_POSITIVE:
        return True
    if stripped in _FEEDBACK_NEGATIVE:
        return False
    return None


def _resolve_language(session_id: str, text: str) -> str:
    stripped = text.strip().lower()
    if stripped in _LANG_COMMANDS:
        _lang_prefs[session_id] = _LANG_COMMANDS[stripped]
        return _lang_prefs[session_id]
    if session_id in _lang_prefs:
        return _lang_prefs[session_id]
    if _DEVANAGARI_RE.search(text):
        _lang_prefs[session_id] = "hi"
        return "hi"
    return "both"


def _decide(text_analysis: dict, session_analysis: dict) -> dict:
    """Mirrors android/.../intelligence/DecisionAgent.kt's decide(), minus the
    phone-lookup signal (no CNAP/Sanchar Saathi source for a WhatsApp number)."""
    level = text_analysis["risk_level"]
    reasons = list(text_analysis.get("signals") or [])
    if not reasons and level != "REAL":
        reasons = [text_analysis["reason"]]

    if session_analysis.get("active_scam_session") == "YES":
        reasons += session_analysis.get("session_triggers", [])
        if session_analysis.get("severity") in ("HIGH", "CRITICAL"):
            level = "FRAUD"

    return {"risk_level": level, "reasons": reasons}


def _build_reply(decision: dict, lang: str) -> str:
    level = decision["risk_level"]
    tag, headline_en, headline_hi = _HEADLINES[level]
    action_en, action_hi = _ACTION_EN[level], _ACTION_HI[level]
    reasons = decision["reasons"]

    lines = [tag]
    if lang == "en":
        lines.append(headline_en)
    elif lang == "hi":
        lines.append(headline_hi)
    else:
        lines.append(headline_en)
        lines.append(headline_hi)

    if reasons:
        lines.append("")
        lines.append("Why / क्यों:" if lang == "both" else ("Why:" if lang == "en" else "क्यों:"))
        lines.extend(f"• {r}" for r in reasons)

    lines.append("")
    if lang == "en":
        lines.append(action_en)
    elif lang == "hi":
        lines.append(action_hi)
    else:
        lines.append(action_en)
        lines.append(action_hi)

    return "\n".join(lines)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    Body: str = Form(default=""),
    From: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    session_id = From.replace("whatsapp:", "")
    try:
        text = Body.strip()
        media_descriptor = (
            _media_descriptor(MediaUrl0, MediaContentType0) if NumMedia != "0" else None
        )
        # A media-only message (attachment, no caption) used to be dropped
        # here entirely — classify_text is what actually reaches the
        # detector, so this only bails out when there's truly nothing at
        # all to classify, not just no caption.
        # A space, not a newline: HIGH_RISK_PATTERNS' .{0,N} gap patterns use
        # plain "." (does not cross a newline by default), so joining with
        # "\n" here would silently prevent any pattern needing to span the
        # caption/descriptor boundary from ever matching — confirmed by
        # testing before choosing a space.
        classify_text = " ".join(p for p in (text, media_descriptor) if p)
        if not classify_text:
            return Response(content="", media_type="application/xml")

        # Feedback/language resolution intentionally use the raw caption
        # (`text`), not classify_text — a media descriptor is never
        # something the user typed and must never be misread as a feedback
        # command or a language-detection signal.
        lang = _resolve_language(session_id, text)

        # Feedback on the verdict shown for the *previous* message, not a new
        # thing to classify — log it and stop, don't run it through the
        # classifier as if it were caller text.
        feedback = _resolve_feedback(text)
        pending = _last_verdict.get(session_id)
        if feedback is not None and pending is not None:
            verdict = pending["verdict"]
            if feedback:
                user_correction = "confirmed_correct"
            elif verdict != "REAL":
                user_correction = "not_a_scam"
            else:
                user_correction = "should_have_been_flagged"

            log_correction(
                channel="whatsapp",
                original_text=pending["original_text"],
                verdict=verdict,
                rule_categories=pending["rule_categories"],
                user_correction=user_correction,
                session_id=session_id,
            )
            del _last_verdict[session_id]

            thanks = "Thanks — recorded." if lang != "hi" else "धन्यवाद — दर्ज कर लिया गया।"
            if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                client.messages.create(from_=TWILIO_WHATSAPP_FROM, to=From, body=thanks)
            logging.info(f"whatsapp session={session_id} | feedback logged | correction={user_correction}")
            return Response(content="", media_type="application/xml")

        text_analysis = analyze_transcript(classify_text, DETECTOR)
        session_analysis = SESSION.ingest(session_id, classify_text)
        decision = _decide(text_analysis, session_analysis)
        reply = _build_reply(decision, lang)

        _last_verdict[session_id] = {
            "original_text": classify_text,
            "verdict": decision["risk_level"],
            "rule_categories": text_analysis.get("rule_categories", []),
        }

        logging.info(
            f"whatsapp session={session_id} | risk={decision['risk_level']} | "
            f"active_session={session_analysis.get('active_scam_session')} | lang={lang}"
        )

        if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(from_=TWILIO_WHATSAPP_FROM, to=From, body=reply)
        else:
            logging.error(
                "TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN not set — reply computed but not sent: "
                f"{reply!r}"
            )
    except Exception as e:
        logging.error(f"whatsapp_webhook error for session={session_id}: {e}")

    # Acknowledge the webhook itself; the actual reply (if any) was already
    # sent above via the Twilio REST API, not via this TwiML response.
    return Response(content="", media_type="application/xml")


class FeedbackRequest(BaseModel):
    channel: str
    original_text: str
    verdict: str
    rule_categories: list[str] = []
    user_correction: str
    session_id: str | None = None


@app.post("/feedback")
async def feedback(req: FeedbackRequest):
    """Log-only — see feedback/store.py. Exposed on this process too (not
    just api/server.py:8000) so the same endpoint shape is reachable and
    testable regardless of which Prahari process a client is pointed at."""
    row_id = log_correction(
        channel=req.channel,
        original_text=req.original_text,
        verdict=req.verdict,
        rule_categories=req.rule_categories,
        user_correction=req.user_correction,
        session_id=req.session_id,
    )
    return {"ok": True, "id": row_id}

# ── Missed-escalation evidence delivery ──────────────────────────────────
# Separate agent from the fixed Tier 1-4 sequence: Android detects a Tier 2
# SMS that wasn't delivered in time, or a Tier 3b call that likely wasn't
# answered, and calls these two endpoints in order (WhatsApp, then this
# process's email endpoint) — SMS itself is attempted directly by Android
# between the two, using the SmsManager already built for Tier 2.
EVIDENCE_DIR = Path(_ROOT) / "webhook" / "_evidence_files"
EVIDENCE_DIR.mkdir(exist_ok=True)

# The ngrok (or other public) URL this process is reachable at — required
# because Twilio's WhatsApp media API fetches the file from a URL, it can't
# take raw bytes. Same tunnel already used for /whatsapp/webhook.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

EMAIL_SMTP_ADDRESS = os.environ.get("EMAIL_SMTP_ADDRESS", "")
EMAIL_SMTP_APP_PASSWORD = os.environ.get("EMAIL_SMTP_APP_PASSWORD", "")

_EVIDENCE_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.pdf$")


class WhatsAppEvidenceRequest(BaseModel):
    phone_number: str  # E.164, no "whatsapp:" prefix — this adds it
    pdf_base64: str
    caption: str = "AbhayAI — missed escalation evidence"


class EmailEvidenceRequest(BaseModel):
    to_email: str
    subject: str
    text_summary: str
    pdf_base64: str
    pdf_filename: str = "evidence.pdf"


@app.post("/evidence/whatsapp")
async def evidence_whatsapp(req: WhatsAppEvidenceRequest):
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return {"success": False, "error": "Twilio not configured"}
    if not PUBLIC_BASE_URL:
        return {"success": False, "error": "PUBLIC_BASE_URL not set — cannot host media for Twilio to fetch"}

    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception as e:
        return {"success": False, "error": f"invalid pdf_base64: {e}"}

    filename = f"{uuid.uuid4().hex}.pdf"
    (EVIDENCE_DIR / filename).write_bytes(pdf_bytes)
    media_url = f"{PUBLIC_BASE_URL}/evidence/files/{filename}"

    to_whatsapp = req.phone_number if req.phone_number.startswith("whatsapp:") else f"whatsapp:{req.phone_number}"

    try:
        client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM, to=to_whatsapp,
            body=req.caption, media_url=[media_url],
        )
    except Exception as e:
        logging.error(f"evidence_whatsapp send failed: {e}")
        return {"success": False, "error": str(e)}

    # Twilio accepting the request ("queued") isn't the same as it actually
    # reaching the device — poll the real status once before deciding this
    # channel succeeded, rather than trusting the initial response blindly.
    time.sleep(3)
    try:
        status = client.messages(msg.sid).fetch().status
    except Exception:
        status = "unknown"
    success = status not in ("failed", "undelivered")
    logging.info(f"evidence_whatsapp sid={msg.sid} status={status} success={success}")
    return {"success": success, "status": status, "sid": msg.sid}


@app.get("/evidence/files/{filename}")
async def evidence_file(filename: str):
    if not _EVIDENCE_FILENAME_RE.match(filename):
        return Response(status_code=404)
    path = EVIDENCE_DIR / filename
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="application/pdf")


@app.post("/evidence/email")
async def evidence_email(req: EmailEvidenceRequest):
    if not (EMAIL_SMTP_ADDRESS and EMAIL_SMTP_APP_PASSWORD):
        logging.error(f"EMAIL_SMTP not configured — would have sent to {req.to_email}: {req.subject!r}")
        return {"success": False, "error": "Email SMTP not configured"}

    try:
        pdf_bytes = base64.b64decode(req.pdf_base64)
    except Exception as e:
        return {"success": False, "error": f"invalid pdf_base64: {e}"}

    try:
        msg = EmailMessage()
        msg["Subject"] = req.subject
        msg["From"] = EMAIL_SMTP_ADDRESS
        msg["To"] = req.to_email
        msg.set_content(req.text_summary)
        msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=req.pdf_filename)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SMTP_ADDRESS, EMAIL_SMTP_APP_PASSWORD)
            server.send_message(msg)
        logging.info(f"evidence_email sent to {req.to_email}")
        return {"success": True}
    except Exception as e:
        logging.error(f"evidence_email failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/webhook")
async def webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    FromCountry: str = Form(default=""),
    FromCity: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    # Lazy import: bot.agent pulls in the RAG/embedding stack (BAAI/bge-m3,
    # ~2GB download on first use), which is unrelated to every other route in
    # this file. Importing it at module load time meant a slow/failed model
    # download (e.g. low disk space) took down the whole process, including
    # /whatsapp/webhook and /health which don't need it at all.
    from bot.agent import chat, _sessions

    try:
        # Same real gap as /whatsapp/webhook (see _media_descriptor's doc
        # comment): without this, an attachment's filename/extension never
        # reached chat() -> ScamDetector.predict() either.
        media_descriptor = (
            _media_descriptor(MediaUrl0, MediaContentType0) if NumMedia != "0" else None
        )
        # Space-joined, not newline-joined — see /whatsapp/webhook's
        # classify_text for why (HIGH_RISK_PATTERNS' gap patterns don't
        # cross a "\n" by default).
        classify_text = " ".join(p for p in (Body.strip(), media_descriptor) if p)
        if not classify_text:
            reply = "Please send a message."
        else:
            session_id = From.replace("whatsapp:", "")
            result = chat(session_id, classify_text)
            reply = result["answer"]

            # ADDITION 3 — store Twilio geo metadata for graph indexing
            twilio_metadata = {
                "from_country": FromCountry,
                "from_city": FromCity,
                "num_media": NumMedia,
            }
            result["twilio_metadata"] = twilio_metadata
            if session_id in _sessions and _sessions[session_id]:
                _sessions[session_id][-1]["twilio_metadata"] = twilio_metadata

            logging.info(
                f"session={session_id} | "
                f"scam={result.get('scam_type')} | "
                f"profile={result.get('profile')} | "
                f"engine={result.get('engine')}"
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        reply = "Kuch gadbad ho gayi. Seedha 1930 pe call karein."

    resp = MessagingResponse()
    resp.message(reply.strip('"').strip("'"))
    return Response(content=str(resp), media_type="application/xml")

@app.get("/health")
async def health():
    return {"status": "ok", "cards": 75}

@app.get("/graph")
async def graph_endpoint():
    G = build_fraud_graph_with_entities()
    summary = get_graph_summary(G)
    hard_links = get_hard_links(G)
    rings = get_ring_clusters(G)
    return {
        "summary": summary,
        "hard_links": hard_links,
        "fraud_rings": rings,
        "nodes": [{"id": n, **d} for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)],
        "intelligence": {
            "confirmed_links": len(hard_links),
            "probable_rings": len(rings),
            "highest_confidence_ring": rings[0] if rings else None,
            "alert": (
                f"{len(rings)} probable fraud rings detected "
                f"across {sum(r['victim_count'] for r in rings)} victim reports"
            ) if rings else "Insufficient data for ring detection",
        },
    }
