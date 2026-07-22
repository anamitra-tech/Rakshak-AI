"""
Shared Sarvam script-detection + translation bridge. Extracted from
webhook/app.py (where it was originally built and proven against the
WhatsApp classify_text path) so assistant/pipeline.py's /chat multilingual
wrapping can reuse the exact same detection regexes and API-call shape
instead of a second copy that could drift out of sync — same reasoning as
bot/languages.py's own extraction.
"""
import json
import logging
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")


def translate_text_sarvam(text: str, source_lang: str, target_lang: str) -> str | None:
    """Sarvam /translate — the server-side twin of the Android app's
    SarvamApiClient.translateToEnglish/translateFromEnglish (same endpoint,
    same request shape). None if SARVAM_API_KEY isn't configured or the call
    fails for any reason — callers must fall back to the untranslated text,
    never block on this.

    Real bug traced live via the Android app's identical client-side call
    (SarvamApiClient.kt): Sarvam's /translate defaults to the "mayura:v1"
    model when no `model` field is sent, and mayura:v1 flatly rejects Urdu
    with HTTP 400 ("Language 'ur-IN' is not supported in mayura:v1. Please
    switch to sarvam-translate:v1 to use this language.") — every Urdu
    WhatsApp message would have silently fallen back to the untranslated-
    text path. Scoped to Urdu only, same as the Android fix, since only
    Urdu was confirmed broken under the default model.

    Real bug found 2026-07-22, while wiring this into assistant/pipeline.py's
    /chat multilingual translate-back step: mayura:v1 also hard-rejects any
    input over 1000 characters (confirmed live: HTTP 400 "Input text must
    not exceed 1000 characters for mayura:v1"). A /chat reply easily crosses
    that on a citizen's very first turn, since handle_chat's INTRO_MESSAGE
    (~570 chars) gets prepended to the generated answer before this function
    ever sees it -- every first-turn non-English reply was silently falling
    back to English. Confirmed live that sarvam-translate:v1 (already used
    for the Urdu case above) accepts the same over-1000-char text with a 200.
    Switching model by length, not just by language, fixes this for every
    caller of this shared function, not only /chat -- a WhatsApp reply this
    long would have hit the exact same silent failure before this fix.
    """
    if not SARVAM_API_KEY:
        logging.info("translate_text_sarvam: SARVAM_API_KEY not set, skipping")
        return None
    body = {
        "input": text,
        "source_language_code": source_lang,
        "target_language_code": target_lang,
    }
    if source_lang.lower() == "ur-in" or target_lang.lower() == "ur-in" or len(text) > 1000:
        body["model"] = "sarvam-translate:v1"
    try:
        resp = requests.post(
            "https://api.sarvam.ai/translate",
            headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout=15,
        )
        resp.raise_for_status()
        translated = (resp.json().get("translated_text") or "").strip()
        return translated or None
    except Exception as e:
        logging.error(f"translate_text_sarvam failed ({source_lang}->{target_lang}): {e}")
        return None


# Unicode script blocks for all 12 target languages' native (non-Latin)
# scripts. Devanagari is shared by Hindi/Marathi and Bengali script is shared
# by Bengali/Assamese (both ambiguous — default to the more common of the
# pair, same accepted approximation the Android app's OCR script routing
# already makes); Arabic script covers Urdu. English/Hinglish stay Latin and
# are intentionally not in this list — ml.detector's patterns already cover
# both without translation.
_SCRIPT_RANGES: list[tuple[re.Pattern, str]] = [
    # Devanagari (Hindi/Marathi) -- deliberately excludes U+0964/U+0965
    # (danda / double danda). Real bug found while testing this fix: those
    # two codepoints live in the Devanagari Unicode block but are shared
    # punctuation reused as a sentence-final mark across several other
    # Brahmic scripts (Bengali in particular) -- a Bengali message ending in
    # "।" was misdetected as Devanagari/Hindi on a naive full-block check,
    # so it was never actually translated from Bengali at all.
    (re.compile(r"[ऀ-ॣ०-ॿ]"), "hi-IN"),
    (re.compile(r"[ঀ-৿]"), "bn-IN"),  # Bengali (Bengali/Assamese)
    (re.compile(r"[਀-੿]"), "pa-IN"),  # Gurmukhi (Punjabi)
    (re.compile(r"[઀-૿]"), "gu-IN"),  # Gujarati
    (re.compile(r"[଀-୿]"), "od-IN"),  # Odia (Sarvam uses "od-IN", not BCP-47 "or-IN")
    (re.compile(r"[஀-௿]"), "ta-IN"),  # Tamil
    (re.compile(r"[ఀ-౿]"), "te-IN"),  # Telugu
    (re.compile(r"[ಀ-೿]"), "kn-IN"),  # Kannada
    (re.compile(r"[ഀ-ൿ]"), "ml-IN"),  # Malayalam
    (re.compile(r"[؀-ۿݐ-ݿ]"), "ur-IN"),  # Arabic script (Urdu)
]


def detect_native_script_lang(text: str) -> str | None:
    """Returns the Sarvam source-language code for the first native Indic/
    Urdu script found in `text`, or None if `text` is pure Latin script
    (English or Romanized Hinglish — ml.detector's patterns cover both
    directly, no translation needed).

    Real bug this replaces (memory note, 2026-07-13): the previous check
    here keyed off *language* ("is this Hindi?" via a Devanagari-only regex,
    then treated Hindi as "already handled" because Prahari's classifier
    docs mention Hindi support) rather than *script* ("is ml.detector's
    Latin-script-only pattern set even capable of matching this text at
    all?"). ml.detector's patterns (including malware_attachment_delivery)
    are Romanized Hinglish/English only — zero native-script training data,
    per CLAUDE.md Section 6.2's documented gap — so ANY native-script input
    across all 12 target languages, not just Devanagari Hindi, never matched
    a single pattern. This function is script-based and general across all
    12: it does not special-case Hindi, and treating any one of these 12
    scripts as "already compatible" because it's technically the same
    language family as Hindi or loosely resembles a known keyword is exactly
    the bug being fixed.

    Real bug fixed 2026-07-15, traced live via the Android app's mirror of
    this function (SarvamLanguageCodes.kt::detectNativeScriptTag): checking
    patterns in a fixed priority order (Devanagari first) and returning on
    the first one with ANY match let a single stray misread character
    override the actual, overwhelmingly-dominant script of the real
    message -- confirmed live with a real OCR result that was genuinely
    all-Devanagari Hindi except for one stray misread Bengali glyph at the
    very start, which used to make this return "bn-IN" instead of "hi-IN"
    purely because Bengali's pattern happened to find a match too. Now
    counts total codepoint matches per script across the whole text and
    returns whichever script actually has the most characters, not
    whichever is checked first or appears earliest.
    """
    best_lang = None
    best_count = 0
    for pattern, sarvam_code in _SCRIPT_RANGES:
        count = len(pattern.findall(text))
        if count > best_count:
            best_count = count
            best_lang = sarvam_code
    return best_lang
