from llm.client import generate
import json
import logging
import re

logger = logging.getLogger(__name__)

ENTITY_PROMPT = """\
Extract entities from this scam victim report.
Return JSON only. No markdown. No explanation.

{{
  "phone_numbers": [],
  "upi_ids": [],
  "urls": [],
  "bank_accounts": [],
  "amounts_inr": [],
  "officer_names": [],
  "agency_names": [],
  "locations_mentioned": [],
  "imei_numbers": [],
  "device_models": [],
  "app_names_mentioned": []
}}

Message: {message}"""

SCAMMER_SIGNATURES = {
    "wrong_legal_refs": [
        "section 420 it act", "section 302 cyber",
        "rbi arrest", "trai police", "sebi warrant",
        "uidai case", "cyber court summons"
    ],
    "pressure_phrases": [
        "last warning", "warrant issued", "2 ghante mein",
        "abhi ke abhi", "senior officer transfer",
        "court order hai", "arrest ho jayenge",
        "last chance", "non bailable"
    ],
    "script_tells": [
        "digital arrest", "video surveillance",
        "do not disconnect", "court is watching",
        "narcotics parcel", "money laundering",
        "suspicious transaction", "aadhaar linked crime",
        "stay on call", "do not tell family",
        "we are recording"
    ],
    "fake_designations": [
        "cyber crime inspector", "cbi joint director",
        "rbi vigilance officer", "trai nodal officer",
        "ed special officer", "ncb superintendent",
        "cyber cell head", "ib officer"
    ],
    "escalation_sequence": [
        "senior officer", "my senior", "transfer your call",
        "director sahab", "commissioner sahab",
        "headquarters se"
    ],
    "isolation_tactics": [
        "dont tell anyone", "family ko mat batana",
        "secret rahega", "confidential case",
        "agar bataya to arrest", "apne ghar mein raho"
    ]
}

SCRIPT_PHRASES = [
    "suspicious transaction mein use hua",
    "digital arrest",
    "your aadhaar is linked",
    "money laundering case",
    "do not tell anyone",
    "stay on the call",
    "we are recording this",
    "court order hai",
    "cbi headquarters",
    "narcotics control",
    "courier mein drugs",
    "fake kyc",
    "account freeze",
    "otp share karo",
    "qr code scan karo"
]

TIMING_SIGNALS = [
    "called multiple times",
    "call aata raha",
    "phir se call aaya",
    "doosre number se",
    "teesra call",
    "ek ghante se",
    "raat ko call",
    "subah se call"
]

BACKGROUND_SIGNALS = [
    "background mein awaaz",
    "office jaisa",
    "typing ki awaaz",
    "dusre log bol rahe",
    "phone pe baat",
    "echo tha",
    "recorded lagta tha"
]

# ADDITION 1 — remote-access app signals
DEVICE_SIGNALS = [
    "anydesk", "teamviewer", "quicksupport",
    "screen share", "remote access",
    "install karo", "app download karo",
    "apk bheja", "play store nahi"
]

# ADDITION 2 — linguistic tells survive voice changers
LINGUISTIC_TELLS = {
    "hindi_english_mix": [
        "aapka account", "aapka aadhaar",
        "aapke upar", "aap ko"
    ],
    "formal_hindi_errors": [
        "aap arrested hai",
        "aapko present hona",
        "case register hua hai aap par"
    ],
    "specific_mispronunciations": [
        "cybercrime sell",
        "money loundering",
        "digitel arrest",
        "warant"
    ]
}

_EMPTY_ENTITIES = {
    "phone_numbers": [], "upi_ids": [], "urls": [],
    "bank_accounts": [], "amounts_inr": [],
    "officer_names": [], "agency_names": [],
    "locations_mentioned": [], "imei_numbers": [],
    "device_models": [], "app_names_mentioned": []
}


def extract_entities(message: str) -> dict:
    try:
        resp = generate(ENTITY_PROMPT.format(message=message[:800]))
        text = resp.text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        return json.loads(text)
    except Exception as e:
        # 2026-07-17: this used to fail silently on EVERY call, before the
        # LLM was ever reached -- ENTITY_PROMPT's own JSON skeleton had
        # unescaped { } that collided with .format()'s substitution syntax
        # (fixed above). Logging here so a future regression is visible
        # instead of silently degrading to empty entities again.
        logger.warning("extract_entities failed, returning empty entities: %s", e)
        return dict(_EMPTY_ENTITIES)


def extract_scammer_signature(message: str) -> dict:
    lower = message.lower()
    found = {}
    for sig_type, phrases in SCAMMER_SIGNATURES.items():
        matches = [p for p in phrases if p in lower]
        if matches:
            found[sig_type] = matches
    return found


def extract_script_fingerprint(message: str) -> list:
    lower = message.lower()
    return [p for p in SCRIPT_PHRASES if p in lower]


def extract_timing_signals(message: str) -> list:
    lower = message.lower()
    return [s for s in TIMING_SIGNALS if s in lower]


def extract_background_signals(message: str) -> list:
    lower = message.lower()
    return [s for s in BACKGROUND_SIGNALS if s in lower]


def extract_device_signals(message: str) -> list:
    """Remote access apps are the strongest device signal — same app name never changes."""
    lower = message.lower()
    return [s for s in DEVICE_SIGNALS if s in lower]


def extract_linguistic_fingerprint(message: str) -> dict:
    """Operator speech errors survive voice changers completely."""
    lower = message.lower()
    found = {}
    for tell_type, phrases in LINGUISTIC_TELLS.items():
        matches = [p for p in phrases if p in lower]
        if matches:
            found[tell_type] = matches
    return found


def _score_fingerprint(message: str) -> str:
    lower = message.lower()
    score = 0
    score += sum(1 for p in SCRIPT_PHRASES if p in lower) * 3
    for phrases in SCAMMER_SIGNATURES.values():
        score += sum(1 for p in phrases if p in lower) * 2
    score += sum(1 for s in TIMING_SIGNALS if s in lower)
    score += sum(1 for s in BACKGROUND_SIGNALS if s in lower)
    score += sum(1 for s in DEVICE_SIGNALS if s in lower) * 2
    for phrases in LINGUISTIC_TELLS.values():
        score += sum(1 for p in phrases if p in lower)
    if score >= 10:
        return "HIGH"
    if score >= 5:
        return "MEDIUM"
    if score >= 2:
        return "LOW"
    return "INSUFFICIENT"


def extract_all(message: str) -> dict:
    return {
        "hard_entities": extract_entities(message),
        "scammer_signature": extract_scammer_signature(message),
        "script_fingerprint": extract_script_fingerprint(message),
        "timing_signals": extract_timing_signals(message),
        "background_signals": extract_background_signals(message),
        "device_signals": extract_device_signals(message),
        "linguistic_fingerprint": extract_linguistic_fingerprint(message),
        "fingerprint_strength": _score_fingerprint(message),
    }
