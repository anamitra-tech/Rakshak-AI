import base64
import json
import re
import smtplib
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

import requests
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from twilio.rest import Client as TwilioRestClient
from dotenv import load_dotenv
import logging
import os
import sys

# Windows' default console codepage (cp1252) can't encode the Unicode block
# characters ("█") easyocr's own model-download progress bar prints on first
# use — an uncaught UnicodeEncodeError there previously aborted OCR reader
# init entirely (real failure observed: 'charmap' codec can't encode
# character '█'). Reconfiguring stdout/stderr to UTF-8 fixes this at the
# source rather than relying on PYTHONIOENCODING being set by whoever starts
# this process. No-op on platforms where reconfigure isn't needed/available.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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


@app.on_event("startup")
async def _warm_up_models():
    """Pre-loads the RAG embedding model (BAAI/bge-m3, rag/embedder.py
    instantiates it at import time) and the EasyOCR reader eagerly at
    process start, instead of lazily on the first real webhook request.
    Added 2026-07-13: repeated real WhatsApp tests showed the first
    message after every restart taking 20-30s+ (measured: bge-m3 weight
    loading alone took ~15s) before this — a real, user-visible latency
    problem, not an assumption. This is a one-time cost per process
    lifetime either way; moving it to startup just means the app itself
    is slower to report "ready" instead of the first user being the one
    who pays for it. Wrapped in try/except so a slow/failed download here
    degrades to the original lazy-load-on-first-request behavior rather
    than blocking startup entirely — same safety property the lazy import
    below (bot.agent inside /webhook) was already written to preserve.
    """
    try:
        logging.info("Pre-warming RAG stack (bot.agent) and OCR reader...")
        import bot.agent  # noqa: F401 — import side effect loads bge-m3
        _get_ocr_reader()
        logging.info("Pre-warming complete — models are warm.")
    except Exception as e:
        logging.warning(f"Model pre-warm failed (will lazy-load on first request instead): {e}")

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


# ── Media content extraction — OCR (images) + Sarvam STT (audio) ────────────
# Added 2026-07-13. Previously, an image or voice note reached the classifier
# as nothing but _media_descriptor's filename/type note above (e.g. "[Attached
# file type: .jpg]") — the actual screenshot text or spoken words never got
# to ml.detector at all. _extract_media_content below downloads image/audio
# attachments and extracts real text (OCR / speech-to-text-translate) so that
# text, not just a type label, is what reaches the classifier. Non-image/audio
# attachments (zip/exe/etc.) are untouched — _media_descriptor still handles
# those exactly as before.
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")

_AUDIO_MIME_TO_EXT = {
    "audio/ogg": ".ogg", "audio/opus": ".ogg",
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
    "audio/mp4": ".m4a", "audio/aac": ".aac",
    "audio/amr": ".amr", "audio/webm": ".webm",
    "audio/wav": ".wav", "audio/x-wav": ".wav",
    "audio/flac": ".flac",
}

# Lazy singleton: easyocr.Reader(...) loads detection+recognition models
# (~64MB download on first use, cached after) and is slow to construct —
# built once, on the first actual image, not at process start. Same reason
# /webhook lazy-imports bot.agent below: a slow/failed model load must not
# take down routes that don't need it (health check, /whatsapp/webhook's
# text-only path, etc).
_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        logging.info("Initializing EasyOCR reader (first use — downloads models if not cached)...")
        _ocr_reader = easyocr.Reader(["en"], gpu=False)
    return _ocr_reader


_TESSDATA_DIR = os.path.join(_ROOT, "tessdata")
_TESSERACT_SUPPORTED_LANGS = {"ben", "tam", "tel", "kan", "mal", "guj", "pan", "ori", "urd", "eng"}
# Windows install location from `winget install UB-Mannheim.TesseractOCR` --
# not on PATH by default. Left alone (pytesseract's own PATH lookup) on
# Linux/prod where tesseract is installed via the system package manager.
_TESSERACT_WINDOWS_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _run_tesseract_ocr(image_bytes: bytes, lang: str) -> str | None:
    """Self-hosted OCR for the Android app's cloud-OCR fallback
    (ocr/CloudOcrClient.kt) — the 9 scripts ML Kit has no on-device
    recognizer for (Bengali/Tamil/Telugu/Kannada/Malayalam/Gujarati/Punjabi/
    Odia/Urdu). Google Cloud Vision was ruled out: it needs a billing
    account, unavailable for this project (same constraint that blocked the
    Meta WhatsApp Business API path earlier) — Tesseract 5 is free and
    self-hosted instead. tessdata/ is a project-local directory (not the
    system Program Files\\Tesseract-OCR\\tessdata one — no admin rights to
    write there when this was set up).

    Set via the TESSDATA_PREFIX env var, not a quoted `--tessdata-dir "..."`
    config string — real bug hit while wiring this up: pytesseract passes
    the config string through mostly unsplit, so the literal quote
    characters ended up as part of the path tesseract tried to open
    (confirmed via the exact error: `Error opening data file "...tessdata"
    /ben.traineddata`, quotes and all). TESSDATA_PREFIX has no such
    quoting/tokenizing step.

    Tries a cascade of --psm (page segmentation mode) values, not just the
    library default (psm 3, fully-automatic layout analysis). Real bug this
    fixed: psm 3 found zero text blocks at all for a real Bengali test image
    (confirmed empty output, not a confidence/accuracy issue -- `tsv` output
    showed no block/line/word entries whatsoever, i.e. layout analysis
    itself failed to segment the image), even though the same traineddata
    file (verified byte-identical to the upstream tessdata_fast release --
    not a bad/truncated download) correctly recognized the same text under
    psm 6 (uniform block) and psm 13 (raw line, no layout analysis at all).
    English/Tamil test images did not hit this with the plain default, but
    nothing rules out other scripts/layouts (e.g. a tightly-cropped
    single-line screenshot) hitting the same segmentation gap -- so every
    lang goes through the same cascade rather than special-casing Bengali.
    """
    import pytesseract
    from PIL import Image
    import io as _io

    if lang not in _TESSERACT_SUPPORTED_LANGS:
        logging.error(f"_run_tesseract_ocr: unsupported lang {lang!r}")
        return None
    try:
        if os.name == "nt" and os.path.exists(_TESSERACT_WINDOWS_CMD):
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WINDOWS_CMD
        os.environ["TESSDATA_PREFIX"] = _TESSDATA_DIR
        pil_image = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
        for psm in (3, 6, 11, 13):
            text = pytesseract.image_to_string(pil_image, lang=lang, config=f"--psm {psm}").strip()
            if text:
                return text
        return None
    except Exception as e:
        logging.error(f"_run_tesseract_ocr failed lang={lang}: {e}")
        return None


def _download_media(media_url: str) -> bytes | None:
    """Authenticated fetch of a Twilio media URL. None on any failure —
    callers must fall back to the type-only descriptor, never raise."""
    if not media_url or not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        return None
    try:
        resp = requests.get(
            media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=20,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logging.error(f"_download_media failed for {media_url}: {e}")
        return None


_OCR_MAX_DIMENSION = 1280  # phone-camera photos (3000px+) cost real seconds of
# EasyOCR inference time for no accuracy gain past this — text legible at
# 1280px on the long edge is still legible after detection/recognition.


def _ocr_image(image_bytes: bytes) -> str | None:
    """Runs on-device-equivalent OCR (English/Latin script only, same scope
    as the Android app's ScreenshotOcrHelper — no Devanagari support here
    either) over a downloaded image. None on failure or no text found."""
    try:
        import numpy as np
        from PIL import Image
        import io as _io

        pil_image = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
        if max(pil_image.size) > _OCR_MAX_DIMENSION:
            scale = _OCR_MAX_DIMENSION / max(pil_image.size)
            new_size = (round(pil_image.width * scale), round(pil_image.height * scale))
            pil_image = pil_image.resize(new_size, Image.LANCZOS)

        image = np.array(pil_image)
        reader = _get_ocr_reader()
        lines = reader.readtext(image, detail=0, paragraph=True)
        text = " ".join(line.strip() for line in lines if line.strip())
        return text or None
    except Exception as e:
        logging.error(f"_ocr_image failed: {e}")
        return None


def _transcribe_audio_sarvam(audio_bytes: bytes, content_type: str) -> str | None:
    """Sarvam speech-to-text, mode=translate — Indic speech (or English)
    straight to an English transcript, same translate-to-English behavior
    CLAUDE.md documented as the planned online-STT fallback (§11.3), here
    used server-side rather than on-device. None if SARVAM_API_KEY isn't
    configured or the call fails for any reason — never blocks the reply.

    Tries the fast synchronous /speech-to-text endpoint first (real limit,
    confirmed via a live 400 response: 30 seconds max). A voice note longer
    than that — real user report 2026-07-13 — falls back to Sarvam's async
    batch job API (client.speech_to_text_job), which supports files up to
    2 hours. Despite the "batch" name this completed in ~3s in live testing
    (create_job -> upload_files -> start -> wait_until_complete), so this
    isn't the slow path it sounds like."""
    if not SARVAM_API_KEY:
        logging.info("_transcribe_audio_sarvam: SARVAM_API_KEY not set, skipping")
        return None
    ext = _AUDIO_MIME_TO_EXT.get(content_type.lower(), ".ogg")
    try:
        resp = requests.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": (f"voice{ext}", audio_bytes, content_type)},
            data={"model": "saaras:v3", "mode": "translate"},
            timeout=30,
        )
        if resp.status_code == 400 and "exceeds the maximum limit" in resp.text:
            logging.info("_transcribe_audio_sarvam: audio too long for sync endpoint, trying batch job")
            return _transcribe_audio_sarvam_batch(audio_bytes, ext)
        if resp.status_code >= 400:
            logging.error(f"_transcribe_audio_sarvam: {resp.status_code} response body: {resp.text[:500]}")
        resp.raise_for_status()
        transcript = (resp.json().get("transcript") or "").strip()
        return transcript or None
    except Exception as e:
        logging.error(f"_transcribe_audio_sarvam failed: {e}")
        return None


def _transcribe_audio_sarvam_batch(audio_bytes: bytes, ext: str) -> str | None:
    """Async batch-job path for audio too long for the sync endpoint — see
    _transcribe_audio_sarvam's doc comment. The SDK's upload_files() takes
    file paths, not bytes, so this writes to a real temp file first. Output
    shape (a downloaded per-file JSON with the same {"transcript": ...}
    field as the sync endpoint) confirmed via a live test run, not assumed
    from Sarvam's docs — the docs for this specific flow don't publish exact
    schemas, only an SDK usage sketch."""
    import shutil
    import tempfile
    from sarvamai import SarvamAI

    tmp_path = None
    out_dir = None
    try:
        client = SarvamAI(api_subscription_key=SARVAM_API_KEY)
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(audio_bytes)

        job = client.speech_to_text_job.create_job(model="saaras:v3", mode="translate")
        job.upload_files(file_paths=[tmp_path])
        job.start()
        # 180s budget: real test completed in ~3s for a 2s clip; this leaves
        # headroom for a genuinely long (1-2 minute) voice note without
        # blocking indefinitely. The reply is sent out-of-band via the
        # Twilio REST API regardless of how long this takes (see /webhook's
        # and /whatsapp/webhook's reply-delivery doc comments), so there's
        # no hard deadline tying this to the original webhook connection.
        job.wait_until_complete(poll_interval=3, timeout=180)
        if not job.is_successful():
            logging.error(f"_transcribe_audio_sarvam_batch: job did not complete successfully: {job.get_status()}")
            return None

        out_dir = tempfile.mkdtemp()
        job.download_outputs(output_dir=out_dir)
        json_files = [f for f in os.listdir(out_dir) if f.endswith(".json")]
        if not json_files:
            logging.error("_transcribe_audio_sarvam_batch: no output file downloaded")
            return None
        with open(os.path.join(out_dir, json_files[0]), encoding="utf-8") as f:
            data = json.load(f)
        transcript = (data.get("transcript") or "").strip()
        return transcript or None
    except Exception as e:
        logging.error(f"_transcribe_audio_sarvam_batch failed: {e}")
        return None
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if out_dir:
            shutil.rmtree(out_dir, ignore_errors=True)


def _is_audio_content_type(content_type: str) -> bool:
    return bool(content_type) and content_type.lower().startswith("audio/")


# Real bug found 2026-07-13: when Sarvam STT failed (observed cause: audio
# over its 30s synchronous-endpoint limit — the batch API would be needed for
# longer files, not wired up here), _extract_media_content correctly returned
# None, but the caller then fell back to _media_descriptor's bare filename
# note (e.g. "[Attached file: File.m4a]") and ran that through the classifier
# as if it were the entire message. With no actual speech content, the
# classifier — correctly, given what it was handed — scored this as SAFE,
# but that reads to the user as "I checked your voice message and it's fine,"
# which is false: nothing about what was actually said was ever analyzed.
# Callers must treat this as a distinct, honest "could not analyze" case
# instead of silently degrading to a real-sounding but unfounded verdict.
_AUDIO_UNANALYZED_EN = (
    "I could not process this voice message — it may be longer than 30 seconds, "
    "or transcription failed. Please type out what was said, or send a shorter clip, "
    "so I can actually check it."
)
_AUDIO_UNANALYZED_HI = (
    "मैं इस वॉइस मैसेज को प्रोसेस नहीं कर पाया — यह 30 सेकंड से लंबा हो सकता है, "
    "या ट्रांसक्रिप्शन विफल रहा। कृपया जो कहा गया था वह टाइप करें, या एक छोटा क्लिप भेजें, "
    "ताकि मैं इसे सही से जांच सकूं।"
)


def _audio_unanalyzed_reply(lang: str) -> str:
    if lang == "en":
        return "⚠️ COULD NOT ANALYZE\n" + _AUDIO_UNANALYZED_EN
    if lang == "hi":
        return "⚠️ जांच नहीं हो पाई\n" + _AUDIO_UNANALYZED_HI
    return "⚠️ COULD NOT ANALYZE / जांच नहीं हो पाई\n" + _AUDIO_UNANALYZED_EN + "\n\n" + _AUDIO_UNANALYZED_HI


def _extract_media_content(media_url: str, content_type: str) -> str | None:
    """Returns real extracted text for an image (OCR) or audio (Sarvam STT-
    translate) attachment, bracketed for the classifier the same way
    _media_descriptor's notes are — or None for any other media type, or if
    download/extraction failed, in which case the caller falls back to
    _media_descriptor's type-only note rather than sending nothing."""
    if not media_url or not content_type:
        return None
    content_type = content_type.lower()

    if content_type.startswith("image/"):
        data = _download_media(media_url)
        if data is None:
            return None
        text = _ocr_image(data)
        return f"[Image text: {text}]" if text else None

    if content_type.startswith("audio/"):
        data = _download_media(media_url)
        if data is None:
            return None
        text = _transcribe_audio_sarvam(data, content_type)
        return f"[Voice message: {text}]" if text else None

    return None


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
        media_descriptor = None
        audio_unanalyzed = False
        if NumMedia != "0":
            # Real content (OCR'd image text / translated voice message)
            # first; only fall back to the type-only note if extraction
            # wasn't possible (no key configured, download failed, no text
            # found) or the attachment isn't an image/audio at all.
            media_descriptor = _extract_media_content(MediaUrl0, MediaContentType0)
            if media_descriptor is None:
                if _is_audio_content_type(MediaContentType0):
                    audio_unanalyzed = True
                media_descriptor = _media_descriptor(MediaUrl0, MediaContentType0)
            logging.info(f"whatsapp session={session_id} | media_descriptor={media_descriptor!r}")

        # Feedback/language resolution intentionally use the raw caption
        # (`text`), not classify_text — a media descriptor is never
        # something the user typed and must never be misread as a feedback
        # command or a language-detection signal.
        lang = _resolve_language(session_id, text)

        # An audio message that failed to transcribe must never be silently
        # classified off just its filename note — see _AUDIO_UNANALYZED_EN's
        # doc comment for the real false-SAFE-verdict bug this replaces.
        if audio_unanalyzed:
            reply = _audio_unanalyzed_reply(lang)
            if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
                client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                client.messages.create(from_=TWILIO_WHATSAPP_FROM, to=From, body=reply)
            logging.info(f"whatsapp session={session_id} | audio unanalyzed, sent honest could-not-process reply")
            return Response(content="", media_type="application/xml")

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
        # reached chat() -> ScamDetector.predict() either. As of 2026-07-13,
        # image/audio attachments get real extracted content (OCR/Sarvam
        # STT-translate) via _extract_media_content, same as /whatsapp/webhook,
        # falling back to the type-only note on any failure.
        media_descriptor = None
        audio_unanalyzed = False
        if NumMedia != "0":
            media_descriptor = _extract_media_content(MediaUrl0, MediaContentType0)
            if media_descriptor is None:
                if _is_audio_content_type(MediaContentType0):
                    audio_unanalyzed = True
                media_descriptor = _media_descriptor(MediaUrl0, MediaContentType0)
            logging.info(f"webhook from={From} | media_descriptor={media_descriptor!r}")
        # Space-joined, not newline-joined — see /whatsapp/webhook's
        # classify_text for why (HIGH_RISK_PATTERNS' gap patterns don't
        # cross a "\n" by default).
        classify_text = " ".join(p for p in (Body.strip(), media_descriptor) if p)
        if audio_unanalyzed:
            # Same real bug as /whatsapp/webhook (see _AUDIO_UNANALYZED_EN's
            # doc comment) — never let chat() classify off a bare filename
            # note when the actual speech was never transcribed.
            reply = _audio_unanalyzed_reply("both")
        elif not classify_text:
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

    # Sent via the Twilio REST API (same pattern /whatsapp/webhook and
    # /evidence/whatsapp already use), not returned in the TwiML response
    # body. Real gap found 2026-07-13: with media handling added, a cold
    # RAG-stack + EasyOCR-reader load can take 20-30s+ (confirmed via a live
    # test — bge-m3 weight loading alone took ~15s), which blew past
    # whatever Twilio/ngrok waits for a webhook HTTP response. The reply
    # this function computed was correct, but was silently lost — ngrok
    # showed status_code=0 on the original connection even though this
    # process logged "200 OK" for the response it tried to send into an
    # already-abandoned connection. Sending via the REST API here means the
    # reply is delivered as soon as it's computed, regardless of whether
    # Twilio is still waiting on the original webhook connection.
    reply = reply.strip('"').strip("'")
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(from_=TWILIO_WHATSAPP_FROM, to=From, body=reply)
        except Exception as e:
            logging.error(f"webhook reply send failed: {e}")
    else:
        logging.error(f"TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN not set — reply computed but not sent: {reply!r}")

    return Response(content="", media_type="application/xml")

@app.get("/health")
async def health():
    return {"status": "ok", "cards": 75}


@app.post("/stt/sarvam")
async def stt_sarvam(file: UploadFile = File(...)):
    """Called by the Android app's SarvamApiClient.transcribeAndTranslate —
    proxies through _transcribe_audio_sarvam (this file's own, already
    battle-tested WhatsApp media-handling code) rather than having the
    Android client call api.sarvam.ai directly. Real bug this fixed: the
    Android client's own direct-to-Sarvam call had a hard client-side ~25s
    recording cap and no fallback, so anything longer than the sync
    endpoint's 30s limit just failed outright — this endpoint reuses the
    sync-then-async-batch fallback (see _transcribe_audio_sarvam's own doc
    comment) that already handles audio up to 2 hours, proven working
    against real WhatsApp voice notes."""
    audio_bytes = await file.read()
    content_type = file.content_type or "audio/mp4"
    transcript = _transcribe_audio_sarvam(audio_bytes, content_type)
    if transcript is None:
        return {"transcript": "", "found": False}
    return {"transcript": transcript, "found": True}


@app.post("/ocr/tesseract")
async def ocr_tesseract(file: UploadFile = File(...), lang: str = Form(...)):
    """Called by the Android app's ocr/CloudOcrClient.kt — online-only OCR
    for the 9 scripts ML Kit's on-device recognizer doesn't cover. [lang]
    is a 3-letter Tesseract code (ben/tam/tel/kan/mal/guj/pan/ori/urd),
    mapped client-side from the app's spoken-language tag."""
    image_bytes = await file.read()
    text = _run_tesseract_ocr(image_bytes, lang)
    if text is None:
        return {"text": "", "found": False}
    return {"text": text, "found": True}

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
