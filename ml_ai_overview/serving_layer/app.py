import base64
import json
import re
import smtplib
import threading
import time
import uuid
from email.message import EmailMessage
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Form, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
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
from ml.detector import ScamDetector, SUSPICIOUS_THRESHOLD
from ml.session import FraudSessionDetector
from voice.voice_fraud import analyze_transcript
from feedback.store import log_correction

logging.basicConfig(level=logging.INFO)
app = FastAPI()

# TEMPORARY, testing-only: allow all origins so the external website
# dashboard (a different domain) can call /chat from a browser at all --
# without this, the browser blocks the request before it even reaches this
# server, regardless of whether the backend itself works. Tighten
# allow_origins to the real deployed domain once it's known (Tuesday).
# allow_credentials=False is deliberate and required: browsers reject
# allow_origins=["*"] combined with allow_credentials=True, and /chat's auth
# is a custom header (X-API-Key), not a cookie, so no credentials are needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
# "hin" added 2026-07-15 for _ocr_image's WhatsApp-media cascade only (see
# its doc comment) -- CloudOcrClient.kt's tesseractLangFor() never requests
# "hin" (Hindi/Marathi go through ML Kit's on-device Devanagari recognizer
# on Android, never reaching this endpoint), so this is unreachable from
# the Android /ocr/tesseract path and doesn't change its behavior.
_TESSERACT_SUPPORTED_LANGS = {"ben", "tam", "tel", "kan", "mal", "guj", "pan", "ori", "urd", "hin", "eng"}
# Windows install location from `winget install UB-Mannheim.TesseractOCR` --
# not on PATH by default. Left alone (pytesseract's own PATH lookup) on
# Linux/prod where tesseract is installed via the system package manager.
_TESSERACT_WINDOWS_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _run_tesseract_ocr_with_confidence(image_bytes: bytes, lang: str) -> tuple[str | None, float]:
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

    Also returns Tesseract's own average per-word confidence for the
    winning psm attempt (0.0 if nothing was found) — added for _ocr_image's
    multi-language cascade (see its doc comment): traced live that Tesseract,
    given an explicit `lang`, always constrains its output to that
    language's character set, so a WRONG language still returns confident-
    looking, script-valid garbage rather than an error or a script mismatch.
    Confirmed on a real Punjabi test image: the correct language (pan)
    scored avg_conf=93.0, while all 8 wrong languages scored 15-45 despite
    each producing script-"valid" text — confidence, not script validity,
    is what actually distinguishes a real read from forced-wrong-language
    noise here.
    """
    import pytesseract
    from pytesseract import Output
    from PIL import Image, ImageFile
    import io as _io

    # Real bug traced live via the Android app's cloud-OCR fallback: a
    # genuine forwarded-screenshot JPEG (re-saved/cropped by some upstream
    # app) was missing its trailing EOI marker -- lenient viewers (and
    # Android's own bitmap decoder, which is why the phone displayed it
    # fine) don't care, but Pillow does by default and raises `OSError:
    # image file is truncated (N bytes not processed)` on `.load()`,
    # which `.convert("RGB")` below triggers. Confirmed the pixel data
    # Pillow can recover is still enough for Tesseract to read the real
    # message text once this is set -- a few missing trailing bytes
    # shouldn't block OCR on an otherwise-intact image.
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    if lang not in _TESSERACT_SUPPORTED_LANGS:
        logging.error(f"_run_tesseract_ocr: unsupported lang {lang!r}")
        return None, 0.0
    try:
        if os.name == "nt" and os.path.exists(_TESSERACT_WINDOWS_CMD):
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_WINDOWS_CMD
        os.environ["TESSDATA_PREFIX"] = _TESSDATA_DIR
        pil_image = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
        for psm in (3, 6, 11, 13):
            text = pytesseract.image_to_string(pil_image, lang=lang, config=f"--psm {psm}").strip()
            if text:
                data = pytesseract.image_to_data(
                    pil_image, lang=lang, config=f"--psm {psm}", output_type=Output.DICT,
                )
                confs = [int(c) for c in data["conf"] if c not in ("-1", -1)]
                avg_conf = sum(confs) / len(confs) if confs else 0.0
                return text, avg_conf
        return None, 0.0
    except Exception as e:
        logging.error(f"_run_tesseract_ocr failed lang={lang}: {e}")
        return None, 0.0


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


# The 9 scripts CloudOcrClient.kt cascades through for the Android app's
# cloud-OCR fallback, plus "hin" (Devanagari, covers Marathi too by the same
# ambiguous-script approximation used everywhere else in this project) --
# real bug traced live: a Hindi WhatsApp test image was confidently
# misread as Gujarati (guj, confidence 65.2, script-valid but semantically
# meaningless output) with no Devanagari option in the cascade at all.
# Android doesn't need "hin" here since ML Kit's on-device Devanagari
# recognizer already covers Hindi/Marathi there before ever reaching this
# server -- but this WhatsApp path has no on-device recognizer of any kind,
# so it needs its own Devanagari coverage. hin.traineddata downloaded from
# the same tessdata_fast source as every other language here (see
# _run_tesseract_ocr_with_confidence's doc comment).
_OCR_CASCADE_LANGS = ["ben", "tam", "tel", "kan", "mal", "guj", "pan", "ori", "urd", "hin"]
_OCR_LOW_CONFIDENCE_THRESHOLD = 0.5
# Real bug fixed 2026-07-15, traced live via an actual Punjabi WhatsApp
# screenshot (a forwarded-attachment card: "Statement of Account6.25.zip
# ZIP - 29 MB", a "Punjabi" filename label, and a "1:40 pm" timestamp, all
# genuine high-confidence English UI chrome, sitting alongside the actual
# Gurmukhi scam text EasyOCR forced through its English model). The actual
# scam-text fragments scored 0.026 and 0.066 confidence individually -- a
# clear forced-wrong-script misread -- but AVERAGING across all fragments
# (the three high-confidence English chrome fragments at 0.93-0.99 each)
# pulled the mean up to ~0.60, comfortably above _OCR_LOW_CONFIDENCE_THRESHOLD,
# so the Tesseract cascade never even ran and the garbled EasyOCR text (which
# is what actually reached the classifier) was returned as if it were a
# confident, complete read. Confirmed live: the "pan" Tesseract cascade entry
# alone scored 72.95 confidence and correctly read the real Gurmukhi message.
# A single genuinely garbled fragment is real signal regardless of how many
# unrelated, correctly-read English fragments (filenames/timestamps/"ZIP"/
# "MB" labels -- near-universal in forwarded-attachment screenshots
# regardless of the scam text's actual language) surround it, so the gate
# now also checks the WORST individual fragment, not just the mean. 0.15 is
# a conservative floor -- every genuinely-forced-wrong-script fragment
# checked across the real Punjabi/Bengali/Marathi/Gujarati/Odia test images
# scored under 0.16 (0.012-0.153), while every legitimately-read fragment
# checked (English UI chrome, plain English test image) scored 0.68-0.996 --
# a wide, comfortably-separated gap in the real data, not a guess.
_OCR_MIN_FRAGMENT_CONFIDENCE_THRESHOLD = 0.15
# Tesseract's 0-100 avg-confidence scale (see
# _run_tesseract_ocr_with_confidence). Checked against 3 real test images:
# correct-language confidence was 93-95 (Punjabi), 86 (Telugu), and as low
# as 45.6 (Bengali) -- while every WRONG language attempt across all three
# stayed at or below 45 (mostly under 33). 40 sits in the gap between the
# lowest real match seen (45.6) and the highest wrong match seen (~45,
# close enough to the real Bengali match that this floor is a real, if
# imperfect, cutoff, not a hard guarantee — the highest-confidence
# candidate is used regardless of this floor per _ocr_image's fallback
# logic, so this only controls the log-level confidence framing, not
# whether a Tesseract read is trusted at all.
_TESSERACT_CASCADE_MIN_CONFIDENCE = 40.0

# Real bug this fixes (2026-07-18, live Malayalam test with CloudOcrClient
# re-enabled): the confidence floor above can't reliably separate real from
# wrong-language reads on its own -- this same doc comment's own data shows
# real Bengali reads as low as 45.6 confidence overlapping with wrong-
# language reads as high as ~45, too narrow a gap to raise the floor without
# also rejecting genuine weak reads. A wrong-language (Telugu) cascade
# candidate scored just above the 40 floor on a Malayalam screenshot and
# passed the script-plausibility check too (Tesseract's forced-script
# output still uses genuine Telugu Unicode characters even when it's
# reading noise), producing text like "ఆం 5 క ఆజంక అక 9 658 9 ఆక8" -- heavy
# digit/symbol soup, not a real sentence. Real scam messages in any of
# these languages are predominantly letters; garbled OCR reads consistently
# were not (this exact pattern -- digits interleaved with script characters
# -- also showed up in the earlier Punjabi failure: "01&6600116.25.200").
# Digit density is a cheap, independent signal confidence alone can't
# provide.
_OCR_MAX_DIGIT_RATIO = 0.20


def _looks_like_ocr_noise(text: str) -> bool:
    """True if [text] is dominated by digits relative to letters -- see
    _OCR_MAX_DIGIT_RATIO's doc comment for the real failure this catches."""
    letters = sum(1 for c in text if c.isalpha())
    digits = sum(1 for c in text if c.isdigit())
    total = letters + digits
    if total < 5:
        return False
    return (digits / total) > _OCR_MAX_DIGIT_RATIO


def _ocr_image(image_bytes: bytes) -> tuple[str | None, float]:
    """Runs on-device-equivalent OCR (English/Latin script via EasyOCR)
    over a downloaded image, falling back to the same 9-language Tesseract
    cascade CloudOcrClient.kt uses (plus Devanagari/"hin", which the
    Android app doesn't need server-side — see _OCR_CASCADE_LANGS) when
    EasyOCR's English-only read doesn't look confident. Returns
    (None, 0.0) on failure or no text found.

    Also returns the confidence of whichever result was actually returned,
    normalized to EasyOCR's 0.0-1.0 scale (Tesseract's own 0-100 scale is
    divided by 100) — added 2026-07-18 so callers can apply
    _OCR_CONFIDENCE_SAFETY_FLOOR (see that constant's doc comment) on top
    of the language-level _OCR_RELIABLE_LANGUAGES gate. Real, live-observed
    motivation: the 2026-07-15/16 OCR audit (CLAUDE.md Section 13) found
    Telugu/Tamil confidently returning a false REAL/SAFE verdict on a real
    scam script due to OCR corruption — the language gate now prevents
    those two specific languages from ever reaching this function at all,
    but this return value lets a caller catch the same failure shape for
    any OCR result, including a low-confidence read within one of the 3
    "reliable" languages (e.g. a blurry/low-light en/hi/mr screenshot),
    which the language gate alone cannot catch.

    Real bug traced live via an actual WhatsApp message: a Punjabi malware-
    attachment screenshot sent to the Twilio sandbox came back as pure
    garbage ("faayr aad feng ra &4a} & &d84 Aena...") because this function
    only ever ran EasyOCR's English-only reader, with no fallback at all --
    unlike the Android app's CloudOcrClient, which already cascades through
    9 non-Latin Tesseract languages. EasyOCR forced to read Gurmukhi glyphs
    through an English-only model produced confident-looking Latin noise,
    not an error, so there was nothing to catch before this fix.

    EasyOCR's own per-detection confidence (available via detail=1,
    discarded before this fix by using detail=0/paragraph=True, which drops
    confidence entirely) is a principled signal that the English read
    wasn't right, not a heuristic guess. Below _OCR_LOW_CONFIDENCE_THRESHOLD
    (mean) OR _OCR_MIN_FRAGMENT_CONFIDENCE_THRESHOLD (worst single fragment
    -- see that constant's doc comment for the real dilution bug this second
    check fixes: a forwarded-attachment screenshot's high-confidence English
    filename/size/timestamp chrome can pull the mean above the first
    threshold even while the actual scam text sits at near-zero confidence),
    tries each language in _OCR_CASCADE_LANGS and picks whichever produces
    the HIGHEST Tesseract confidence -- not whichever comes first, and NOT
    validated by script/language of the result (tried that first; abandoned
    it after finding, on the same real Punjabi image, that Tesseract given
    an explicit `lang` always constrains its output to that language's
    character set, so every wrong language ALSO produced script-"valid"
    text for the Bengali-alphabet request, Telugu-alphabet request, etc. --
    script validity doesn't distinguish a real read from forced-wrong-
    language noise here, only Tesseract's own confidence does). Falls back
    to the best (even low-confidence) Tesseract result if one was found at
    all, since any real-script read beats a definite English-model misread
    of non-Latin glyphs; only falls back to the original EasyOCR text when
    literally no Tesseract candidate produced anything.
    """
    try:
        import numpy as np
        from PIL import Image, ImageFile
        import io as _io

        # Same truncated-JPEG tolerance as _run_tesseract_ocr -- see its
        # comment for the real, live-traced bug this fixes.
        ImageFile.LOAD_TRUNCATED_IMAGES = True

        pil_image = Image.open(_io.BytesIO(image_bytes)).convert("RGB")
        if max(pil_image.size) > _OCR_MAX_DIMENSION:
            scale = _OCR_MAX_DIMENSION / max(pil_image.size)
            new_size = (round(pil_image.width * scale), round(pil_image.height * scale))
            pil_image = pil_image.resize(new_size, Image.LANCZOS)

        image = np.array(pil_image)
        reader = _get_ocr_reader()
        detections = reader.readtext(image, detail=1, paragraph=False)
        easy_text = " ".join(t.strip() for _, t, _ in detections if t.strip())
        confidences = [c for _, _, c in detections]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        min_confidence = min(confidences) if confidences else 0.0

        if (
            easy_text
            and avg_confidence >= _OCR_LOW_CONFIDENCE_THRESHOLD
            and min_confidence >= _OCR_MIN_FRAGMENT_CONFIDENCE_THRESHOLD
        ):
            return easy_text, avg_confidence

        logging.info(
            f"_ocr_image: EasyOCR result low-confidence (avg={avg_confidence:.2f}, "
            f"min={min_confidence:.2f}, text={easy_text!r}), trying Tesseract cascade"
        )
        best_lang, best_text, best_conf = None, None, -1.0
        for tess_lang in _OCR_CASCADE_LANGS:
            candidate, conf = _run_tesseract_ocr_with_confidence(image_bytes, tess_lang)
            if not candidate:
                continue
            if conf > best_conf:
                best_lang, best_text, best_conf = tess_lang, candidate, conf

        # Real bug fixed here: a real Bengali test image's correct match
        # (ben) scored only 45.6 confidence -- comfortably the best of the
        # 9 (next-highest was 32.0), but below an earlier, too-tight fixed
        # threshold, which fell back to EasyOCR's English-model garbage
        # instead of preferring the best (even if not "confident enough")
        # Tesseract candidate. Any real Tesseract read beats a definite
        # English-model misread of non-Latin glyphs -- only fall back to
        # EasyOCR's text when NO Tesseract candidate produced anything at
        # all.
        if best_text is not None:
            if best_conf >= _TESSERACT_CASCADE_MIN_CONFIDENCE:
                logging.info(f"_ocr_image: Tesseract cascade picked lang={best_lang} confidence={best_conf:.1f}")
            else:
                logging.info(
                    f"_ocr_image: Tesseract cascade best guess lang={best_lang} "
                    f"confidence={best_conf:.1f} (below floor, using anyway over EasyOCR)"
                )
            return best_text, best_conf / 100.0

        return (easy_text, avg_confidence) if easy_text else (None, 0.0)
    except Exception as e:
        logging.error(f"_ocr_image failed: {e}")
        return None, 0.0


class SarvamQuotaExceededError(Exception):
    """Raised when Sarvam responds 402 (payment required) or 429 (rate/quota
    limit) — a caller-actionable condition distinct from a generic STT
    failure (bad audio, network blip, etc). Deliberately not swallowed by
    _transcribe_audio_sarvam's own broad except-Exception-return-None
    fallback: the Android AI Services screen now tells users up front that
    Sarvam is "free trial credits, then pay-as-you-go", so when that trial
    runs out the app needs to say so explicitly rather than report the same
    generic "couldn't understand" message it would give for a bad recording.
    429 is confirmed as Sarvam's documented rate/quota-limit status (their
    own API guidance says retry only on 429/500/503); 402 is included
    defensively per general REST billing convention, not independently
    confirmed against a live Sarvam response — treat as best-effort."""


def _transcribe_audio_sarvam(audio_bytes: bytes, content_type: str, mode: str = "translate") -> str | None:
    """Sarvam speech-to-text. [mode] defaults to "translate" (Indic speech,
    or English, straight to an English transcript — the WhatsApp bot's own
    behavior, documented as the planned online-STT fallback, CLAUDE.md
    §11.3) but callers that want the transcript in its original script
    (e.g. the Android app's voice-input box, so the user sees back what
    they actually said) pass mode="transcribe" instead. None if
    SARVAM_API_KEY isn't configured or the call fails for any reason —
    never blocks the reply.

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
            data={"model": "saaras:v3", "mode": mode},
            timeout=30,
        )
        if resp.status_code == 400 and "exceeds the maximum limit" in resp.text:
            logging.info("_transcribe_audio_sarvam: audio too long for sync endpoint, trying batch job")
            return _transcribe_audio_sarvam_batch(audio_bytes, ext, mode)
        if resp.status_code in (402, 429):
            logging.error(f"_transcribe_audio_sarvam: quota/rate limit hit ({resp.status_code}): {resp.text[:300]}")
            raise SarvamQuotaExceededError(f"Sarvam STT returned HTTP {resp.status_code}")
        if resp.status_code >= 400:
            logging.error(f"_transcribe_audio_sarvam: {resp.status_code} response body: {resp.text[:500]}")
        resp.raise_for_status()
        resp_json = resp.json()
        logging.info(f"DIAG_sarvam_sync_raw_response mode={mode} json={resp_json}")
        transcript = (resp_json.get("transcript") or "").strip()
        return transcript or None
    except SarvamQuotaExceededError:
        raise
    except Exception as e:
        logging.error(f"_transcribe_audio_sarvam failed: {e}")
        return None


def _transcribe_audio_sarvam_batch(audio_bytes: bytes, ext: str, mode: str = "translate") -> str | None:
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

        job = client.speech_to_text_job.create_job(model="saaras:v3", mode=mode)
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
        logging.info(f"DIAG_sarvam_batch_raw_response mode={mode} json={data}")
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


# Moved to bot/sarvam_translate.py so assistant/pipeline.py's /chat
# multilingual wrapping can reuse the exact same detection regexes and
# translate-call shape instead of a second copy that could drift out of
# sync (same reasoning as bot/languages.py's own extraction). Aliased back
# to their original names here so none of this file's existing call sites
# need to change.
from bot.sarvam_translate import (
    translate_text_sarvam as _translate_text_sarvam,
    detect_native_script_lang as _detect_native_script_lang,
)


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


def _audio_unanalyzed_reply(lang_tag: str) -> str:
    """`lang_tag` is the user's STORED language preference (one of the 12
    BCP-47 tags in _LANGUAGE_MENU), same decoupling as _reply_in_preference —
    not whatever language the (failed) voice message happened to be in."""
    if lang_tag == "en-IN":
        return "⚠️ COULD NOT ANALYZE\n" + _AUDIO_UNANALYZED_EN
    if lang_tag == "hi-IN":
        return "⚠️ जांच नहीं हो पाई\n" + _AUDIO_UNANALYZED_HI
    translated = _translate_text_sarvam(_AUDIO_UNANALYZED_EN, "en-IN", _to_sarvam_lang_code(lang_tag))
    if translated:
        return "⚠️ COULD NOT ANALYZE\n" + translated
    return "⚠️ COULD NOT ANALYZE / जांच नहीं हो पाई\n" + _AUDIO_UNANALYZED_EN + "\n\n" + _AUDIO_UNANALYZED_HI


def _extract_media_content(media_url: str, content_type: str) -> tuple[str | None, float | None]:
    """Returns (real extracted text, ocr_confidence) for an image (OCR) or
    audio (Sarvam STT-translate) attachment, bracketed for the classifier
    the same way _media_descriptor's notes are — or (None, None) for any
    other media type, or if download/extraction failed, in which case the
    caller falls back to _media_descriptor's type-only note rather than
    sending nothing.

    ocr_confidence is only ever non-None for an image attachment that
    produced text — None for audio (Sarvam STT has no comparable per-call
    confidence surfaced here), no-media, and failed-extraction cases, so a
    caller can tell "this wasn't an image/OCR result at all" apart from "OCR
    ran and was confident." See _OCR_CONFIDENCE_SAFETY_FLOOR for the caller-
    side use of this value."""
    if not media_url or not content_type:
        return None, None
    content_type = content_type.lower()

    if content_type.startswith("image/"):
        data = _download_media(media_url)
        if data is None:
            return None, None
        text, confidence = _ocr_image(data)
        return (f"[Image text: {text}]", confidence) if text else (None, None)

    if content_type.startswith("audio/"):
        data = _download_media(media_url)
        if data is None:
            return None, None
        text = _transcribe_audio_sarvam(data, content_type)
        return (f"[Voice message: {text}]", None) if text else (None, None)

    return None, None


# Reuses the exact same evidence-based cutoff as _TESSERACT_CASCADE_MIN_CONFIDENCE
# (see that constant's doc comment: real correct-language matches scored
# 45.6-95, wrong-language/forced misreads scored under 45, normalized here to
# the 0.0-1.0 scale _ocr_image returns) — one real, already-validated number,
# not a second independent guess. Defense-in-depth ON TOP OF the
# _OCR_RELIABLE_LANGUAGES gate (see _ocr_image's doc comment for why the gate
# alone doesn't cover every case this catches, e.g. a low-confidence read
# within an already-"reliable" language).
_OCR_CONFIDENCE_SAFETY_FLOOR = 0.40

_OCR_LOW_CONFIDENCE_CAVEAT_EN = (
    "We couldn't read this image clearly enough to be confident — please type "
    "the message or use voice input instead for an accurate check."
)


def _apply_ocr_confidence_floor(text_analysis: dict, ocr_confidence: float | None, safe_level: str) -> dict:
    """Never let a genuinely low-confidence OCR read render as the SAFE tier
    (`safe_level` — "REAL" for voice.voice_fraud's spelling, "SAFE" for
    ml.detector's) — force it to SUSPICIOUS with an honest caveat instead,
    regardless of what the (possibly garbled) OCR text itself scored.
    Directly targets the real, live-confirmed failure mode this session's
    audit found: Telugu/Tamil OCR corruption producing a confident FALSE
    SAFE verdict on an actual scam script (CLAUDE.md Section 13). A no-op
    (returns text_analysis unchanged) when ocr_confidence is None (not an
    image result at all) or at/above the floor, and never downgrades an
    already-SUSPICIOUS/FRAUD verdict — this only ever escalates a false
    "safe" read, never softens a real one."""
    if ocr_confidence is None or ocr_confidence >= _OCR_CONFIDENCE_SAFETY_FLOOR:
        return text_analysis
    if text_analysis.get("risk_level") != safe_level:
        return text_analysis
    floored = dict(text_analysis)
    floored["risk_level"] = "SUSPICIOUS"
    floored["score"] = max(text_analysis.get("score", 0.0), SUSPICIOUS_THRESHOLD)
    floored["reason"] = _OCR_LOW_CONFIDENCE_CAVEAT_EN
    floored["signals"] = []
    floored["ocr_confidence_floor_applied"] = True
    logging.info(
        f"_apply_ocr_confidence_floor: OCR confidence {ocr_confidence:.2f} below floor "
        f"{_OCR_CONFIDENCE_SAFETY_FLOOR} — forced {safe_level} to SUSPICIOUS"
    )
    return floored


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
# that). Keyed by session_id (WhatsApp number), valued by one of the 12
# BCP-47 tags in _LANGUAGE_MENU below. Shared across both WhatsApp routes
# (/whatsapp/webhook and /webhook) so a preference set via either one is
# honored by both, since Twilio's session_id (From.replace("whatsapp:", ""))
# is computed identically in both handlers.
_lang_prefs: dict[str, str] = {}

# Real race confirmed 2026-07-16: /whatsapp/webhook and /webhook both run
# their slow work (_process_whatsapp_message / _process_webhook_message) as
# BackgroundTasks, which FastAPI dispatches via a thread pool for sync
# callables -- so two messages from the SAME session_id, sent close
# together, can run concurrently in separate threads. If the first
# message's chat()/ml.session call is still waiting on a slow LLM response
# when the second arrives, the second can read _sessions/SessionStore
# before the first has written its result -- confirmed live: a rapid
# follow-up during an active scam session saw bot.agent's "already active"
# check as False (no prior scam recorded yet) purely because the earlier
# turn hadn't finished, silently skipping the calm-guidance short-circuit
# (its "trust but verify" fallback still produced a correct verdict, so
# this was never a wrong-answer bug -- just lost the intended calmer UX for
# exactly the rapid-fire-during-panic scenario this feature exists for).
# This lock registry serializes background-task processing per session_id
# (never across different sessions, which still run fully in parallel) so
# messages from one user are always handled in the order they arrived.
_session_locks: dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def _get_session_lock(session_id: str) -> threading.Lock:
    with _session_locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_locks[session_id] = lock
        return lock


def _run_serialized_per_session(fn, session_id, *args) -> None:
    """Wraps a BackgroundTask target so it only runs while holding this
    session_id's lock -- see _session_locks' doc comment above."""
    with _get_session_lock(session_id):
        fn(session_id, *args)


# Extracted to bot/languages.py so bot.agent.chat()'s LANGUAGE_CHANGE intent
# can resolve free-text language mentions through the exact same table this
# first-contact menu and _parse_language_selection use, instead of a second
# copy that could drift out of sync.
from bot.languages import (
    LANGUAGE_MENU as _LANGUAGE_MENU,
    to_sarvam_lang_code as _to_sarvam_lang_code,
    parse_language_selection as _parse_language_selection,
)

_LANGUAGE_INTRO = (
    "🛡️ *Namaste! I'm PraHARI-AI.*\n\n"
    "Apni bhasha chuniye / Please select your language:\n\n"
    + "\n".join(
        f"{i}. {native}" if native == english else f"{i}. {native} ({english})"
        for i, (_tag, native, english) in enumerate(_LANGUAGE_MENU, start=1)
    )
    + "\n\nReply with a number (1-12) to select your language."
)

def _language_confirmation_reply(lang_tag: str) -> str:
    english_name = next(english for tag, _native, english in _LANGUAGE_MENU if tag == lang_tag)
    confirmation = (
        f"Language set to {english_name}. "
        "You can now send a suspicious call, message, or screenshot and I'll check it for you."
    )
    if lang_tag == "en-IN":
        return confirmation
    translated = _translate_text_sarvam(confirmation, "en-IN", _to_sarvam_lang_code(lang_tag))
    return translated or confirmation


def _send_whatsapp_reply(to: str, body: str) -> None:
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        logging.error(f"TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN not set — reply computed but not sent: {body!r}")
        return
    try:
        client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(from_=TWILIO_WHATSAPP_FROM, to=to, body=body)
    except Exception as e:
        logging.error(f"_send_whatsapp_reply failed: {e}")

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


# Real bug reproduced live (2026-07-16): a WhatsApp session already flagged
# high-risk (per SESSION.is_already_active) got a follow-up message that was
# a first-person description of an ONGOING situation ("But he says he will
# arrest me as soon") -- not a new suspicious message being submitted for
# checking. _build_reply's normal technical reasons dump (ML score %,
# "N high-risk messages", session duration) isn't useful to someone who
# needs a direct next action, not a report. Checked against both the
# original and English-translated text (a short reactive phrase's
# translation isn't always a reliable English pattern match on its own --
# same original+translated dual-check already used for classify_text
# above). Deliberately does NOT change scoring/session-tracking at all
# (see _process_whatsapp_message's call site) -- this only changes what's
# DISPLAYED, gated additionally on this specific message having triggered
# no rule_categories of its own, so a message that *also* contains a fresh
# scam ask (e.g. "he says send OTP now") still gets the full verdict, not
# just the calm-guidance short-circuit.
#
# Detection regex + reply copy extracted to bot/calm_guidance.py so
# bot.agent.chat()'s ACTIVE_SESSION_FOLLOWUP intent (a separate pipeline,
# separate session store) reuses the exact same detector/copy instead of a
# second copy that could silently drift from this one.
from bot.calm_guidance import (
    is_conversational_followup as _is_conversational_followup,
    CONVERSATIONAL_FOLLOWUP_EN as _CONVERSATIONAL_FOLLOWUP_EN,
    CONVERSATIONAL_FOLLOWUP_HI as _CONVERSATIONAL_FOLLOWUP_HI,
)


def _conversational_followup_reply(lang_tag: str) -> str:
    if lang_tag == "en-IN":
        return _CONVERSATIONAL_FOLLOWUP_EN
    if lang_tag == "hi-IN":
        return _CONVERSATIONAL_FOLLOWUP_HI
    translated = _translate_text_sarvam(_CONVERSATIONAL_FOLLOWUP_EN, "en-IN", _to_sarvam_lang_code(lang_tag))
    return translated or _CONVERSATIONAL_FOLLOWUP_EN


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
    """Builds the plain English ("en") or hardcoded Hindi ("hi") template
    reply. Every other target language is produced by _reply_in_preference
    translating the "en" build via Sarvam instead of a hardcoded template."""
    level = decision["risk_level"]
    tag, headline_en, headline_hi = _HEADLINES[level]
    action_en, action_hi = _ACTION_EN[level], _ACTION_HI[level]
    reasons = decision["reasons"]

    lines = [tag]
    lines.append(headline_hi if lang == "hi" else headline_en)

    if reasons:
        lines.append("")
        lines.append("क्यों:" if lang == "hi" else "Why:")
        lines.extend(f"• {r}" for r in reasons)

    lines.append("")
    lines.append(action_hi if lang == "hi" else action_en)

    return "\n".join(lines)


def _reply_in_preference(decision: dict, lang_tag: str) -> str:
    """Builds the WhatsApp risk-verdict reply in the user's STORED language
    preference — decoupled entirely from whatever language the input
    (message text or OCR'd/transcribed media) was actually in. Previously
    this mirrored the input's detected script (translated_source_lang /
    general_native_lang), so a Tamil screenshot from a user who had
    selected Hindi got a Tamil reply instead of Hindi — this is the fix."""
    if lang_tag == "en-IN":
        return _build_reply(decision, "en")

    if lang_tag == "hi-IN":
        translated_reasons = [_translate_text_sarvam(r, "en-IN", "hi-IN") for r in decision["reasons"]]
        if not decision["reasons"] or all(translated_reasons):
            return _build_reply({**decision, "reasons": translated_reasons}, "hi")
        logging.info("whatsapp | reason translate-to-Hindi failed, using Hindi headline/English reasons")
        return _build_reply(decision, "hi")

    # Every other target language has no hardcoded template -- translate the
    # whole English reply via Sarvam, same best-effort/English-fallback
    # pattern used throughout this file.
    english_reply = _build_reply(decision, "en")
    translated = _translate_text_sarvam(english_reply, "en-IN", _to_sarvam_lang_code(lang_tag))
    if translated:
        return translated
    logging.info(f"whatsapp | reply translate to {lang_tag} failed, sending English reply")
    return english_reply


def _translate_reply_to_preference(reply_text: str, lang_tag: str) -> str:
    """/webhook's twin of _reply_in_preference: chat()'s reply is a single
    free-form string (no structured reasons list to special-case), so this
    just translates the whole thing into the user's STORED preference —
    never whatever language the input happened to be in. English
    preference is returned as-is; any translation failure falls back to
    the original (English/Hinglish) text rather than blocking."""
    if lang_tag == "en-IN":
        return reply_text
    translated = _translate_text_sarvam(reply_text, "en-IN", _to_sarvam_lang_code(lang_tag))
    return translated or reply_text


# Real, measured OCR-accuracy audit (2026-07-15, rendered clean ground-truth
# text through the actual production _ocr_image pipeline, one real scam
# sentence per language): only English, Hindi, and Marathi came back
# reliable (CER under 8%, correct FRAUD classification). The other 9 -- most
# of which route through Tesseract's non-Latin cascade -- ranged from
# "directionally right but under-called" (Bengali/Gujarati/Kannada/
# Malayalam/Punjabi/Odia landed SUSPICIOUS, not FRAUD, on a textbook scam
# script) to genuinely broken (Telugu/Tamil scored REAL -- a false
# negative -- and Urdu's 84% character error rate was bad enough that
# Sarvam's translation of the garbage OCR text didn't just mistranslate, it
# hallucinated a fabricated, unrelated story).
#
# 2026-07-16 re-verification: a prior version of this comment claimed a
# gTTS-generated-audio STT test had already confirmed Sarvam STT as the
# reliable replacement path, with specific per-language scores -- but no
# test script, audio file, or log for that claim survived anywhere in this
# repo, so it was re-run for real instead of trusted as-is (a one-off verification
# script, not committed / not part of the app). Real, measured result for
# the three worst
# OCR failures specifically: a real digital-arrest-scam ground-truth
# sentence per language (native script) -> gTTS audio -> the actual
# _transcribe_audio_sarvam() (mode=translate, unmocked, live Sarvam API) ->
# ScamDetector.predict() on the returned transcript. Telugu: transcript
# matched the ground truth almost word-for-word, FRAUD score=1.0. Tamil:
# transcript matched almost word-for-word, FRAUD score=0.713 (a real FRAUD
# verdict, not merely SUSPICIOUS). Urdu: transcript matched (CBI expanded to
# "Central Bureau of Investigation" but meaning intact), FRAUD score=1.0. A
# follow-up benign-message sanity check (a harmless "coming home for dinner"
# sentence, same three languages) transcribed accurately and correctly
# scored SAFE (0.39-0.43) in all three -- ruling out the STT path just
# always outputting scam-shaped text regardless of input. Net: Sarvam STT is
# a substantially more reliable path than OCR for these languages, evidence
# now real rather than assumed. Mirrored in CLAUDE.md's "OCR reliability by
# language" table -- keep both in sync if this list changes.
# 2026-07-18: product decision to re-enable OCR for the 7 "under-called"
# languages (Bengali/Gujarati/Kannada/Malayalam/Punjabi/Odia/Urdu) despite
# the audit above, on the reasoning that under-calling to SUSPICIOUS (not
# FRAUD) is a real but bounded degradation, not a silent miss -- unlike
# Telugu/Tamil's outright false-negative-to-SAFE, which stays gated. Flagged
# distinctly: Urdu's failure mode in the same audit isn't "under-called",
# it's a translation hallucinating a fabricated, unrelated story from
# 84%-CER garbage OCR text -- a materially worse failure than under-scoring,
# re-enabled here only because it was explicitly requested alongside the
# other 6, not because the hallucination risk stopped applying.
_OCR_RELIABLE_LANGUAGES = {"en-IN", "hi-IN", "mr-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "pa-IN", "or-IN", "ur-IN"}

_OCR_UNRELIABLE_TEMPLATE_EN = (
    "Text recognition for {language} isn't reliable enough yet — please type the message, "
    "or use voice input instead."
)


def _ocr_unreliable_reply(lang_tag: str) -> str:
    english_name = next(english for tag, _native, english in _LANGUAGE_MENU if tag == lang_tag)
    message = _OCR_UNRELIABLE_TEMPLATE_EN.format(language=english_name)
    if lang_tag == "en-IN":
        return message
    translated = _translate_text_sarvam(message, "en-IN", _to_sarvam_lang_code(lang_tag))
    return translated or message


_ANALYZING_IMAGE_TEMPLATE_EN = "Analyzing your image, one moment…"
_ANALYZING_AUDIO_TEMPLATE_EN = "Analyzing your voice message, one moment…"


def _analyzing_reply(lang_tag: str, is_audio: bool) -> str:
    """Sent immediately, before any OCR/STT/translate/classify work starts,
    for any media message that reaches this far (i.e. wasn't already
    redirected by the OCR-reliability gate above). Real, live-observed bug
    this exists for (2026-07-16): a real WhatsApp image needing the full
    EasyOCR->Tesseract-cascade->Sarvam-translate chain took 35s+, and that
    one specific message got NO reply at all, not even the usual delayed
    async one -- Twilio's own message log confirmed total silence, worse
    than a wrong answer. Sending this first guarantees the user sees
    *something* immediately, independent of whether the slow work that
    follows (now itself backgrounded -- see _process_whatsapp_message's doc
    comment) finishes, is delayed, or is later found to have failed."""
    message = _ANALYZING_AUDIO_TEMPLATE_EN if is_audio else _ANALYZING_IMAGE_TEMPLATE_EN
    if lang_tag == "en-IN":
        return message
    translated = _translate_text_sarvam(message, "en-IN", _to_sarvam_lang_code(lang_tag))
    return translated or message


def _process_whatsapp_message(
    session_id: str,
    From: str,
    text: str,
    lang_tag: str,
    NumMedia: str,
    MediaUrl0: str,
    MediaContentType0: str,
) -> None:
    """The slow half of /whatsapp/webhook -- OCR/STT, translate, classify,
    and the real verdict reply -- scheduled as a BackgroundTask so it runs
    AFTER the webhook's TwiML response has already been sent, not inside
    the request/response cycle Twilio is waiting on.

    Real, live-observed bug this replaces (2026-07-16): this used to run
    inline, before returning to Twilio. A multi-language Tesseract OCR
    cascade measured at 35.5s (see CLAUDE.md Section 13) blew past Twilio's
    own webhook response window (Twilio logged error 11200, "HTTP retrieval
    failure") -- and for the slowest real case, worse than that: no reply of
    any kind ever reached the user, confirmed via Twilio's own message log
    showing total silence where three earlier, faster (~15-20s) 11200s in
    the same conversation still got their real reply moments later.
    Mechanism: uvicorn cancels the in-flight ASGI task if the underlying
    connection is torn down while the app is still producing a response
    (Twilio/ngrok give up and close their end); a request still executing
    *inside that same task* when the connection drops can be killed
    mid-flight, losing the reply it was about to send. Running this as a
    BackgroundTask means the original request task already produced its
    (empty) response and exited before this function even starts -- there
    is no in-flight request task left for a dropped connection to cancel.

    Also sends an immediate "Analyzing..." acknowledgment (see
    _analyzing_reply) before any of the slow work below starts, for any
    media message -- so the user sees *something* right away even if the
    slow work that follows is delayed, or (as happened live) fails softly.
    """
    try:
        has_media = NumMedia != "0"
        is_audio = has_media and _is_audio_content_type(MediaContentType0)
        if has_media:
            _send_whatsapp_reply(From, _analyzing_reply(lang_tag, is_audio))

        # Real content (OCR'd image text / translated voice message)
        # first; only fall back to the type-only note if extraction
        # wasn't possible (no key configured, download failed, no text
        # found) or the attachment isn't an image/audio at all.
        media_descriptor = None
        ocr_confidence = None
        audio_unanalyzed = False
        if has_media:
            media_descriptor, ocr_confidence = _extract_media_content(MediaUrl0, MediaContentType0)
            if media_descriptor is None:
                if is_audio:
                    audio_unanalyzed = True
                media_descriptor = _media_descriptor(MediaUrl0, MediaContentType0)
            logging.info(f"whatsapp session={session_id} | media_descriptor={media_descriptor!r}")

        # An audio message that failed to transcribe must never be silently
        # classified off just its filename note — see _AUDIO_UNANALYZED_EN's
        # doc comment for the real false-SAFE-verdict bug this replaces.
        if audio_unanalyzed:
            reply = _audio_unanalyzed_reply(lang_tag)
            _send_whatsapp_reply(From, reply)
            logging.info(f"whatsapp session={session_id} | audio unanalyzed, sent honest could-not-process reply")
            return

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
            return

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

            if lang_tag == "en-IN":
                thanks = "Thanks — recorded."
            elif lang_tag == "hi-IN":
                thanks = "धन्यवाद — दर्ज कर लिया गया।"
            else:
                thanks = _translate_text_sarvam(
                    "Thanks — recorded.", "en-IN", _to_sarvam_lang_code(lang_tag)
                ) or "Thanks — recorded."
            _send_whatsapp_reply(From, thanks)
            logging.info(f"whatsapp session={session_id} | feedback logged | correction={user_correction}")
            return

        # Real bug fixed 2026-07-13, generalized 2026-07-13: classify_text
        # used to reach the detector completely untranslated. ml.detector's
        # patterns (including malware_attachment_delivery) are Latin-script
        # Hinglish only -- CLAUDE.md Section 6.2's second documented gap,
        # zero native-script training examples -- so a genuine native-script
        # caption never matched any pattern at all, regardless of content or
        # which of the 12 target languages it was in. The first fix here was
        # itself a real bug: it only checked Devanagari, on the mistaken
        # assumption that "Hindi is Devanagari-script" meant every other
        # language's native script was a separate, lower-priority gap. It
        # isn't -- ml.detector has zero native-script training data for any
        # of them. _detect_native_script_lang checks all 12 scripts, not
        # just Devanagari.
        #
        # Real bug fixed 2026-07-15: this used to detect/translate script
        # only in the caption (`text`), never in `media_descriptor` (OCR'd
        # image text), on the assumption that _ocr_image was Latin-script
        # EasyOCR only and native-script OCR output was "a separate,
        # still-open gap." That assumption stopped being true once
        # _ocr_image gained its Tesseract cascade for the 10 non-Latin
        # scripts (see _ocr_image's doc comment) -- confirmed live with a
        # real Hindi bank-KYC scam screenshot: OCR correctly extracted
        # "आपका बैंक खाता 24 घंटे में ब्लॉक हो जाएगा, तुरंत OTP भेजें" into
        # media_descriptor, but with no caption at all (`text` == ""),
        # _detect_native_script_lang(text) returned None and the whole
        # Devanagari OCR text reached ml.detector's Latin-only patterns
        # completely untranslated, scoring a confident SAFE/REAL verdict on
        # an actual scam message. Now detects/translates across the full
        # classify_text (caption + media_descriptor together), not the
        # caption alone. Falls back to the untranslated text on any
        # translation failure rather than blocking the whole check.
        text_for_detector = classify_text
        translated_source_lang = _detect_native_script_lang(classify_text)
        if translated_source_lang:
            translated_text = _translate_text_sarvam(classify_text, translated_source_lang, "en-IN")
            if translated_text:
                text_for_detector = translated_text
                logging.info(
                    f"whatsapp session={session_id} | translated classify_text "
                    f"({translated_source_lang}) to English for classification"
                )
            else:
                logging.info(f"whatsapp session={session_id} | translation failed, classifying untranslated text")

        # Captured BEFORE ingest() so this reflects the session's state from
        # PRIOR messages only -- a fresh, non-flagged session's first
        # message must still go through full classification/display even if
        # it happens to trip the same thresholds on its own (see
        # _is_conversational_followup's doc comment above).
        was_already_active = SESSION.is_already_active(session_id)

        text_analysis = analyze_transcript(text_for_detector, DETECTOR)
        # Defense-in-depth on top of the _OCR_RELIABLE_LANGUAGES gate — see
        # _apply_ocr_confidence_floor's doc comment. "REAL" is
        # voice.voice_fraud's spelling of the safe tier.
        text_analysis = _apply_ocr_confidence_floor(text_analysis, ocr_confidence, "REAL")
        session_analysis = SESSION.ingest(session_id, text_for_detector)
        decision = _decide(text_analysis, session_analysis)

        # Reply language is the user's STORED preference (lang_tag), never
        # whatever language the input happened to be in — see
        # _reply_in_preference's doc comment for the bug this replaces (a
        # Tamil screenshot from a Hindi-preference user used to get a Tamil
        # reply because this used to key off translated_source_lang/
        # general_native_lang, the *input's* detected script, instead).
        #
        # Scoring/session-tracking above is completely unchanged regardless
        # of what happens next -- only the DISPLAYED reply switches to calm,
        # direct guidance when: the session was already flagged high-risk
        # from prior messages, this message reads as a first-person
        # reactive follow-up rather than a script being submitted for
        # checking, AND this specific message triggered no rule_categories
        # of its own (so a message that also contains a fresh scam ask still
        # gets the full verdict).
        if (
            was_already_active
            and not text_analysis.get("rule_categories")
            and _is_conversational_followup(classify_text, text_for_detector)
        ):
            reply = _conversational_followup_reply(lang_tag)
            logging.info(f"whatsapp session={session_id} | conversational followup, calm-guidance reply sent")
        else:
            reply = _reply_in_preference(decision, lang_tag)

        _last_verdict[session_id] = {
            "original_text": classify_text,
            "verdict": decision["risk_level"],
            "rule_categories": text_analysis.get("rule_categories", []),
        }

        logging.info(
            f"whatsapp session={session_id} | risk={decision['risk_level']} | "
            f"active_session={session_analysis.get('active_scam_session')} | lang={lang_tag}"
        )

        _send_whatsapp_reply(From, reply)
    except Exception as e:
        logging.error(f"whatsapp background processing error for session={session_id}: {e}")


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    session_id = From.replace("whatsapp:", "")
    try:
        text = Body.strip()

        # First-contact / language-change gate, before any media/OCR work or
        # classification: a bare menu number or language name (English name
        # or native self-name) always sets/changes the stored preference and
        # short-circuits with a confirmation, whether this is the user's
        # very first message or a later request to switch language. A
        # session with no stored preference yet gets the selection menu
        # instead of having its message silently classified in the wrong
        # (or no) language.
        selected_tag = _parse_language_selection(text)
        if selected_tag:
            _lang_prefs[session_id] = selected_tag
            _send_whatsapp_reply(From, _language_confirmation_reply(selected_tag))
            logging.info(f"whatsapp session={session_id} | language set to {selected_tag}")
            return Response(content="", media_type="application/xml")
        if session_id not in _lang_prefs:
            _send_whatsapp_reply(From, _LANGUAGE_INTRO)
            logging.info(f"whatsapp session={session_id} | first contact, sent language menu")
            return Response(content="", media_type="application/xml")
        lang_tag = _lang_prefs[session_id]

        # Real, measured OCR-accuracy gate (see _OCR_RELIABLE_LANGUAGES' doc
        # comment): for the 9 languages where OCR was proven unreliable
        # (under-called or outright false-negative on a textbook scam
        # screenshot), never run OCR and classify whatever garbage comes out
        # of it -- that's exactly the silently-wrong-verdict failure mode
        # audited today. Redirect to typed/voice input instead, before
        # spending any OCR/translate/classify work on the image at all.
        if (
            NumMedia != "0"
            and MediaContentType0.lower().startswith("image/")
            and lang_tag not in _OCR_RELIABLE_LANGUAGES
        ):
            _send_whatsapp_reply(From, _ocr_unreliable_reply(lang_tag))
            logging.info(f"whatsapp session={session_id} | image upload blocked, OCR unreliable for {lang_tag}")
            return Response(content="", media_type="application/xml")

        # Everything from here on (OCR/STT, translate, classify, and the
        # real verdict reply) is genuinely slow -- measured 35s+ for a hard
        # multi-language Tesseract cascade, and Sarvam's audio batch-job
        # fallback can take up to 180s -- comfortably past Twilio's own
        # webhook response window. Scheduled as a background task so this
        # request always returns immediately regardless, and so a dropped
        # Twilio/ngrok connection can no longer cancel the work mid-flight.
        # See _process_whatsapp_message's doc comment for the real
        # 2026-07-16 bug (Twilio error 11200, and worse, a genuinely
        # unreplied message) this fixes.
        background_tasks.add_task(
            _run_serialized_per_session,
            _process_whatsapp_message, session_id, From, text, lang_tag, NumMedia, MediaUrl0, MediaContentType0,
        )
    except Exception as e:
        logging.error(f"whatsapp_webhook error for session={session_id}: {e}")

    # Acknowledge the webhook itself immediately; the real reply is sent
    # later, out-of-band, via the Twilio REST API from the background task
    # above (or, for the fast synchronous gates before it, already sent).
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

# ── Standalone conversational /chat endpoint ──────────────────────────────
# Clean JSON in/out for an external website dashboard — separate from
# /webhook (Twilio form-encoded) and separate from bot.agent.chat()'s
# WhatsApp scam-triage flow. Legal/citizen-rights RAG over
# kb/legal_info.json only; see assistant/pipeline.py for the full pipeline
# (query rewrite -> hybrid retrieval -> confidence floor -> rerank ->
# generation -> citation verification -> faithfulness check). Session
# history reuses bot.agent's existing in-memory store (add_to_memory/
# get_history) rather than a new one.


class ChatRequest(BaseModel):
    session_id: str
    message: str


_CHAT_API_KEY = os.environ.get("CHAT_API_KEY")


def _require_chat_api_key(x_api_key: str | None = Header(default=None)):
    # Fails closed by construction: if CHAT_API_KEY isn't set server-side,
    # _CHAT_API_KEY is None, and no client-sent header value can equal None
    # over HTTP -- every request 401s rather than silently running unauthed.
    if not _CHAT_API_KEY or x_api_key != _CHAT_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")


@app.post("/chat", dependencies=[Depends(_require_chat_api_key)])
async def chat_endpoint(req: ChatRequest):
    from assistant.pipeline import handle_chat_multilang

    try:
        return handle_chat_multilang(req.session_id, req.message)
    except Exception:
        logging.exception("Unhandled /chat failure for session %s", req.session_id)
        return {
            "reply": "Something went wrong on our side. Please call 1930 directly or try again.",
            "sources": [],
            "metrics": {"error": "unhandled_exception"},
        }


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
    caption: str = "PraHARI-AI — missed escalation evidence"


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


def _process_webhook_message(
    session_id: str,
    From: str,
    text: str,
    lang_tag: str,
    FromCountry: str,
    FromCity: str,
    NumMedia: str,
    MediaUrl0: str,
    MediaContentType0: str,
) -> None:
    """The slow half of /webhook -- media extraction, translate, chat()
    (the RAG/LLM stack), and the real reply -- scheduled as a BackgroundTask
    for exactly the same reason as /whatsapp/webhook's twin function (see
    _process_whatsapp_message's doc comment for the full 2026-07-16 incident
    this fixes): running it inline, before the webhook's TwiML response was
    returned, meant a slow message could still be killed mid-flight by a
    dropped Twilio/ngrok connection, losing the reply entirely -- the same
    failure mode the 2026-07-13 fix below (REST-API delivery instead of
    inline TwiML body) reduced the *frequency* of but didn't eliminate,
    since the reply was still computed inside the same request task Twilio
    could time out and disconnect from.
    """
    # Lazy import: bot.agent pulls in the RAG/embedding stack (BAAI/bge-m3,
    # ~2GB download on first use), which is unrelated to every other route in
    # this file. Importing it at module load time meant a slow/failed model
    # download (e.g. low disk space) took down the whole process, including
    # /whatsapp/webhook and /health which don't need it at all.
    from bot.agent import chat, _sessions

    try:
        has_media = NumMedia != "0"
        is_audio = has_media and _is_audio_content_type(MediaContentType0)
        if has_media:
            _send_whatsapp_reply(From, _analyzing_reply(lang_tag, is_audio))

        # Same real gap as /whatsapp/webhook (see _media_descriptor's doc
        # comment): without this, an attachment's filename/extension never
        # reached chat() -> ScamDetector.predict() either. As of 2026-07-13,
        # image/audio attachments get real extracted content (OCR/Sarvam
        # STT-translate) via _extract_media_content, same as /whatsapp/webhook,
        # falling back to the type-only note on any failure.
        media_descriptor = None
        ocr_confidence = None
        audio_unanalyzed = False
        if has_media:
            media_descriptor, ocr_confidence = _extract_media_content(MediaUrl0, MediaContentType0)
            if media_descriptor is None:
                if is_audio:
                    audio_unanalyzed = True
                media_descriptor = _media_descriptor(MediaUrl0, MediaContentType0)
            logging.info(f"webhook from={From} | media_descriptor={media_descriptor!r}")
        # Space-joined, not newline-joined — see /whatsapp/webhook's
        # classify_text for why (HIGH_RISK_PATTERNS' gap patterns don't
        # cross a "\n" by default).
        classify_text = " ".join(p for p in (text, media_descriptor) if p)
        if audio_unanalyzed:
            # Same real bug as /whatsapp/webhook (see _AUDIO_UNANALYZED_EN's
            # doc comment) — never let chat() classify off a bare filename
            # note when the actual speech was never transcribed.
            reply = _audio_unanalyzed_reply(lang_tag)
        elif not classify_text:
            reply = _translate_reply_to_preference("Please send a message.", lang_tag)
        else:
            # Same real bug as /whatsapp/webhook (see that handler's matching
            # doc comment), generalized the same way: chat() ->
            # retrieve_and_respond() -> ScamDetector.predict() only ever
            # sees Latin-script Hinglish patterns (including
            # malware_attachment_delivery) -- a genuine native-script Body,
            # in any of the 12 target languages (not just Devanagari Hindi),
            # never matched anything. Translates across the full
            # classify_text (caption + media_descriptor together), not the
            # caption alone -- same real bug (and fix) as /whatsapp/webhook:
            # OCR'd image text can now itself be native-script (Tesseract
            # cascade, see _ocr_image), and a media-only message with no
            # caption at all used to skip translation entirely since
            # _detect_native_script_lang(text) on an empty caption always
            # returns None. Mirrors the Android app's translateToEnglish step
            # in CheckCallActivity.kt's runAnalysis. Falls back to the
            # untranslated text on translation failure rather than blocking
            # the whole check.
            text_for_chat = classify_text
            translated_source_lang = _detect_native_script_lang(classify_text)
            if translated_source_lang:
                translated_text = _translate_text_sarvam(classify_text, translated_source_lang, "en-IN")
                if translated_text:
                    text_for_chat = translated_text
                    logging.info(
                        f"webhook session={session_id} | translated classify_text "
                        f"({translated_source_lang}) to English for chat()"
                    )
                else:
                    logging.info(f"webhook session={session_id} | translation failed, chatting with untranslated text")

            result = chat(session_id, text_for_chat)

            # Same defense-in-depth floor as /whatsapp/webhook (see
            # _apply_ocr_confidence_floor's doc comment), applied here
            # against chat()'s result instead of analyze_transcript()'s —
            # chat()/retrieve_and_respond() marks its classifier-driven SAFE
            # verdict with engine="classifier_safe" (rag/retriever.py) before
            # any RAG/LLM step runs, which is the one reliable signal
            # available here without reaching into retrieve_and_respond()
            # itself. Known, honest limitation: if the intent router (a
            # separate LLM call) misroutes a garbled/low-confidence OCR text
            # away from SCAM_CHECK entirely (e.g. to GENERAL_CHAT), this
            # never fires — bot.agent.chat()'s own mandatory rule-based
            # backstop only force-routes to SCAM_CHECK when a rule pattern
            # actually matches, which corrupted OCR text may not do.
            if (
                ocr_confidence is not None
                and ocr_confidence < _OCR_CONFIDENCE_SAFETY_FLOOR
                and result.get("engine") == "classifier_safe"
            ):
                logging.info(
                    f"webhook session={session_id} | OCR confidence {ocr_confidence:.2f} below floor "
                    f"{_OCR_CONFIDENCE_SAFETY_FLOOR} — forcing classifier_safe reply to low-confidence caveat"
                )
                result["answer"] = _OCR_LOW_CONFIDENCE_CAVEAT_EN
                result["ocr_confidence_floor_applied"] = True

            # bot.agent's LANGUAGE_CHANGE intent (free-text language switches
            # mid-conversation, e.g. "reply to me in Tamil") can't mutate
            # _lang_prefs itself -- chat() doesn't own that state, it lives
            # here (shared with /whatsapp/webhook's pre-chat gate). Apply the
            # switch and use the same confirmation copy that gate already
            # sends, instead of translating chat()'s generic answer.
            if result.get("intent") == "language_change" and result.get("lang_tag"):
                new_tag = result["lang_tag"]
                _lang_prefs[session_id] = new_tag
                reply = _language_confirmation_reply(new_tag)
                logging.info(f"webhook session={session_id} | language changed mid-conversation to {new_tag}")
            else:
                # Reply language is the user's STORED preference (lang_tag),
                # never whatever language the input was in -- see
                # _translate_reply_to_preference's doc comment for the bug this
                # replaces (this used to translate back into
                # translated_source_lang, the *input's* detected script).
                reply = _translate_reply_to_preference(result["answer"], lang_tag)

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
                f"intent={result.get('intent')} | "
                f"scam={result.get('scam_type')} | "
                f"profile={result.get('profile')} | "
                f"engine={result.get('engine')}"
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        reply = "Kuch gadbad ho gayi. Seedha 1930 pe call karein."

    # Twilio's own request/response log (below) never includes the message
    # body, only headers -- logged separately here since a send failure
    # (e.g. Twilio's daily cap, seen live 2026-07-16) previously left no way
    # to see what the actual computed reply was without re-deriving it.
    logging.info(f"session={session_id} | reply={reply!r}")

    # Sent via the Twilio REST API (same pattern /whatsapp/webhook and
    # /evidence/whatsapp already use), not returned in the TwiML response
    # body -- and, as of 2026-07-16, computed inside a BackgroundTask rather
    # than inline in the request handler, so a dropped Twilio/ngrok
    # connection can no longer cancel this mid-flight and lose the reply
    # entirely (see this function's doc comment).
    reply = reply.strip('"').strip("'")
    _send_whatsapp_reply(From, reply)


@app.post("/webhook")
async def webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    FromCountry: str = Form(default=""),
    FromCity: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: str = Form(default=""),
    MediaContentType0: str = Form(default=""),
):
    session_id = From.replace("whatsapp:", "")
    try:
        text = Body.strip()

        # Same first-contact / language-change gate as /whatsapp/webhook
        # (shared _lang_prefs store, keyed identically off session_id) —
        # see that handler's matching doc comment for why this runs before
        # any media/OCR work or classification.
        selected_tag = _parse_language_selection(text)
        if selected_tag:
            _lang_prefs[session_id] = selected_tag
            _send_whatsapp_reply(From, _language_confirmation_reply(selected_tag))
            logging.info(f"webhook session={session_id} | language set to {selected_tag}")
            return Response(content="", media_type="application/xml")
        if session_id not in _lang_prefs:
            _send_whatsapp_reply(From, _LANGUAGE_INTRO)
            logging.info(f"webhook session={session_id} | first contact, sent language menu")
            return Response(content="", media_type="application/xml")
        lang_tag = _lang_prefs[session_id]

        # Same real, measured OCR-reliability gate as /whatsapp/webhook --
        # see _OCR_RELIABLE_LANGUAGES' doc comment for the audit this is
        # based on.
        if (
            NumMedia != "0"
            and MediaContentType0.lower().startswith("image/")
            and lang_tag not in _OCR_RELIABLE_LANGUAGES
        ):
            _send_whatsapp_reply(From, _ocr_unreliable_reply(lang_tag))
            logging.info(f"webhook session={session_id} | image upload blocked, OCR unreliable for {lang_tag}")
            return Response(content="", media_type="application/xml")

        # Media extraction / translate / chat() / reply -- genuinely slow
        # (RAG stack + LLM call, plus OCR/STT for attachments) -- scheduled
        # as a background task for the same reason as /whatsapp/webhook.
        # See _process_webhook_message's doc comment.
        background_tasks.add_task(
            _run_serialized_per_session,
            _process_webhook_message,
            session_id, From, text, lang_tag, FromCountry, FromCity, NumMedia, MediaUrl0, MediaContentType0,
        )
    except Exception as e:
        logging.error(f"webhook error for session={session_id}: {e}")

    return Response(content="", media_type="application/xml")

@app.get("/health")
async def health():
    return {"status": "ok", "cards": 75}


@app.post("/stt/sarvam")
async def stt_sarvam(file: UploadFile = File(...), mode: str = Form("translate")):
    """Called by the Android app's SarvamApiClient —
    proxies through _transcribe_audio_sarvam (this file's own, already
    battle-tested WhatsApp media-handling code) rather than having the
    Android client call api.sarvam.ai directly. Real bug this fixed: the
    Android client's own direct-to-Sarvam call had a hard client-side ~25s
    recording cap and no fallback, so anything longer than the sync
    endpoint's 30s limit just failed outright — this endpoint reuses the
    sync-then-async-batch fallback (see _transcribe_audio_sarvam's own doc
    comment) that already handles audio up to 2 hours, proven working
    against real WhatsApp voice notes.

    [mode] defaults to "translate" (English transcript) for backward
    compatibility with any other caller, but CheckCallActivity's voice
    input passes mode="transcribe" so the user sees their own words back
    in the language they actually spoke — real bug this fixes: the
    transcript box was always showing an English translation regardless
    of the configured language, since translate-mode was the only mode
    ever requested. The existing content-based script-detection + translate
    bridge in CheckCallActivity.runAnalysis already handles native-script
    text correctly (built for OCR/typed input) — this just stops
    pre-translating away the native text before that bridge ever sees it."""
    audio_bytes = await file.read()
    content_type = file.content_type or "audio/mp4"
    try:
        transcript = _transcribe_audio_sarvam(audio_bytes, content_type, mode)
    except SarvamQuotaExceededError:
        return {"transcript": "", "found": False, "quota_exceeded": True}
    if transcript is None:
        return {"transcript": "", "found": False}
    return {"transcript": transcript, "found": True}


@app.post("/ocr/tesseract")
async def ocr_tesseract(file: UploadFile = File(...), lang: str = Form(...)):
    """Called by the Android app's ocr/CloudOcrClient.kt — online-only OCR
    for the 9 scripts ML Kit's on-device recognizer doesn't cover. [lang]
    is a 3-letter Tesseract code (ben/tam/tel/kan/mal/guj/pan/ori/urd),
    mapped client-side from the app's spoken-language tag.

    Applies the same _TESSERACT_CASCADE_MIN_CONFIDENCE floor _ocr_image
    already uses for the WhatsApp path — real bug this fixes: a live
    Punjabi test with CloudOcrClient re-enabled (2026-07-18) came back
    "found": true with confident-looking Gurmukhi-script garbage (Tesseract
    always constrains output to the requested script, so wrong/garbled
    reads still pass the script-plausibility check CloudOcrClient does
    client-side) — that garbage then translated to equally meaningless
    English and correctly-but-uselessly scored SAFE, since there's no scam
    pattern in noise. Below-floor reads now report "found": false instead,
    letting CloudOcrClient's existing per-candidate cascade move on to try
    another language rather than confidently returning noise as the
    result."""
    image_bytes = await file.read()
    text, confidence = _run_tesseract_ocr_with_confidence(image_bytes, lang)
    if text is None or confidence < _TESSERACT_CASCADE_MIN_CONFIDENCE:
        logging.info(f"ocr_tesseract: rejecting low-confidence read lang={lang} confidence={confidence:.1f}")
        return {"text": "", "found": False}
    if _looks_like_ocr_noise(text):
        logging.info(f"ocr_tesseract: rejecting digit-heavy noise read lang={lang} confidence={confidence:.1f} text={text!r}")
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
