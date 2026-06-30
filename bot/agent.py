from datetime import datetime, timezone

from llm.client import generate
from rag.retriever import retrieve_and_respond
from graph.entity_extractor import extract_all

# ── Intent keyword sets ───────────────────────────────────────────────────────

_GREET_KW = {
    "hi", "hello", "hey", "hola", "namaste", "namaskar",
    "good morning", "good evening", "good afternoon",
    "goodmorning", "howdy", "salam",
}

_ABOUT_KW = {
    "what do you do", "who are you", "your purpose",
    "kya karti", "aapka kaam", "tumhara kaam",
    "what can you do", "tell me about yourself",
}

_FOLLOWUP_KW = {
    "same call", "again", "phir se", "ek aur", "dobara",
    "same number", "similar", "last time", "pehle bhi",
    "ek aur call",
    "they say", "they say they are real", "bol rahe hain",
    "real hai", "sach mein", "pakka", "sure hai", "sure",
    "genuine", "real don't worry", "woh bol rahe hain",
    "real hain", "woh real hain", "actually real", "trust kar",
}

_SCAM_KW = {
    "cbi", "ed", "police", "arrest", "warrant", "court",
    "otp", "kyc", "bank", "account", "zip", "apk", "file",
    "investment", "profit", "return", "trading", "crypto",
    "qr", "scan", "payment", "upi", "lottery", "prize",
    "won", "winner", "gift", "call aaya", "message aaya",
    "aadhaar", "biometric", "sim", "sanchar", "hr ne bheja",
}

_INTENT_PROMPT = (
    'Classify this message into exactly one intent: '
    'greeting, about, scam_report, followup, unclear.\n'
    'Message: "{message}"\n'
    'Reply with only the intent word, nothing else.'
)

# ── Personality strings ───────────────────────────────────────────────────────

GREETING = """🛡️ *Namaste! I'm Rakshak.*

I help citizens identify scams — digital arrest calls, fake bank alerts, suspicious links, QR code fraud, and more.

Just tell me:
- What did the caller say?
- Forward me a suspicious message
- Share a link you're unsure about

I'll tell you if it's a scam and exactly what to do. 🔴🟢"""

ABOUT = """🛡️ *Rakshak — Digital Public Safety Assistant*

I can detect:
✓ Digital arrest scams (fake CBI/ED/Police)
✓ Bank KYC/OTP fraud
✓ Fake investment schemes
✓ QR code payment scams
✓ Lottery/prize fraud
✓ Suspicious links
✓ ZIP/APK malware delivery
✓ Multi-call coordinated pressure

Powered by MHA/I4C intelligence. Always free.
Emergency: Call *1930* | Report: cybercrime.gov.in"""

UNCLEAR = """I didn't quite understand that. You can:
- Describe a suspicious call you received
- Forward a message you're unsure about
- Ask me what I do

I'm here to help. 🛡️"""

# ── Session memory ────────────────────────────────────────────────────────────

_sessions: dict[str, list] = {}


def add_to_memory(
    session_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    scam_type: str | None = None,
    fingerprint: dict | None = None,
) -> None:
    _sessions.setdefault(session_id, []).append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intent": intent,
        "scam_type": scam_type,
        "fingerprint": fingerprint or {},
    })


def get_history(session_id: str, last_n: int = 5) -> list:
    return _sessions.get(session_id, [])[-last_n:]


def get_scam_history(session_id: str) -> list:
    return [e for e in _sessions.get(session_id, []) if e.get("scam_type") is not None]


# ── Profile detection ─────────────────────────────────────────────────────────

ELDERLY_KW = {
    "budhape", "retirement", "pension", "60 saal", "70 saal",
    "dadi", "nani", "dadaji", "nanaji", "mere papa", "meri maa",
    "parents", "bade", "elderly", "old", "senior",
}

FARMER_KW = {
    "kisan", "farmer", "kheti", "fasal", "pm kisan", "pmkisan",
    "kcc", "kisan credit", "mandi", "grain", "gaon", "village",
    "rural", "krishi", "bhoomi", "jameen",
}


def detect_profile(session_id: str, message: str) -> str:
    history = get_history(session_id, last_n=10)
    all_text = (
        message + " " + " ".join(e["content"] for e in history)
    ).lower()
    if any(kw in all_text for kw in ELDERLY_KW):
        return "elderly"
    if any(kw in all_text for kw in FARMER_KW):
        return "farmer"
    return "default"


# ── Profile-aware formatters ──────────────────────────────────────────────────

def format_default(result: dict) -> str:
    return result["answer"]


def format_elderly(result: dict) -> str:
    scam = result.get("scam_type") or "scam"
    scam_label = scam.replace("_", " ")
    return (
        f"Yeh ek {scam_label} hai.\n\n"
        f"Paise bilkul mat dijiye.\n"
        f"Phone band kar dijiye.\n\n"
        f"Abhi 1930 par call karein.\n"
        f"Yeh sarkar ka helpline hai. Free hai."
    )


def format_farmer(result: dict) -> str:
    scam = result.get("scam_type") or "dhokha"
    scam_label = scam.replace("_", " ")
    return (
        f"Yeh call galat hai.\n"
        f"Yeh {scam_label} hai.\n\n"
        f"Phone band kar dijiye.\n"
        f"Koi bhi paisa mat dijiye.\n"
        f"Koi bhi OTP mat dijiye.\n\n"
        f"1930 pe call karein."
    )


# ── Pattern detection ─────────────────────────────────────────────────────────

def compare_with_history(session_id: str, current_result: dict) -> str | None:
    current_type = current_result.get("scam_type")
    if not current_type or current_type == "unknown":
        return None

    prior = [
        e for e in get_scam_history(session_id)
        if e["role"] == "assistant" and e.get("scam_type")
    ]
    if not prior:
        return None

    prior_type = prior[-1]["scam_type"]
    if current_type == prior_type:
        return (
            "⚠️ This matches a scam pattern you reported earlier. "
            "These may be coordinated calls from the same network."
        )
    return (
        "This appears to be a different scam type from your earlier report "
        "— you may be targeted by multiple actors."
    )


# ── Pushback detection ───────────────────────────────────────────────────────

PUSHBACK_KW = {
    "they say", "bol rahe hain", "real hai",
    "sach mein", "pakka", "sure hai", "genuine",
    "real don't worry", "trust kar",
}


def is_pushback(message: str, session_id: str) -> bool:
    lower = message.lower()
    has_pushback = any(kw in lower for kw in PUSHBACK_KW)
    prior_scam = get_scam_history(session_id)
    return has_pushback and len(prior_scam) > 0


# ── Verification lure detection ───────────────────────────────────────────────

VERIFICATION_LURE_KW = {
    "come verify", "come to office", "in person",
    "is it safe to go", "should i go", "they said come",
    "verify in person", "this floor", "this building",
    "real building", "real office",
}

_VERIFICATION_LURE_WARNING = (
    "IMPORTANT: Being asked to verify in person during a call "
    "is itself a scam tactic — real government agencies never "
    "require this. Do not travel anywhere right now."
)


def is_verification_lure(message: str) -> bool:
    m = message.lower()
    return any(kw in m for kw in VERIFICATION_LURE_KW)


# ── Intent detection ──────────────────────────────────────────────────────────

def detect_intent(message: str) -> str:
    msg = message.strip().lower()

    if any(msg == kw or msg.startswith(kw) for kw in _GREET_KW):
        return "greeting"

    if any(kw in msg for kw in _ABOUT_KW):
        return "about"

    if any(kw in msg for kw in _FOLLOWUP_KW):
        return "followup"

    if any(kw in msg for kw in _SCAM_KW):
        return "scam_report"

    try:
        prompt = _INTENT_PROMPT.format(message=message)
        response = generate(prompt)
        first_word = response.text.strip().split()[0].lower().rstrip(".,")
        if first_word in ("greeting", "about", "scam_report", "followup", "unclear"):
            return first_word
    except Exception:
        pass

    return "unclear"


# ── Main entry ────────────────────────────────────────────────────────────────

def chat(session_id: str, message: str) -> dict:
    if is_pushback(message, session_id):
        reply = (
            "Real CBI, police, aur banks kabhi bhi:\n"
            "• WhatsApp pe arrest nahi karte\n"
            "• Phone pe paisa nahi maangte\n"
            "• OTP nahi maangte\n\n"
            "Yeh ek confirmed scam hai.\n"
            "Abhi phone band karein.\n"
            "1930 pe call karein."
        )
        result = {
            "answer": reply,
            "scam_type": None,
            "confidence": None,
            "engine": "pushback_gate",
            "profile": detect_profile(session_id, message),
        }
        add_to_memory(session_id, "user", message, intent="pushback")
        add_to_memory(session_id, "assistant", reply)
        result["intent"] = "pushback"
        result["session_id"] = session_id
        result["history_length"] = len(_sessions.get(session_id, []))
        return result

    lure_detected = is_verification_lure(message)
    intent = "scam_report" if lure_detected else detect_intent(message)
    add_to_memory(session_id, "user", message, intent=intent)

    if intent == "greeting":
        result = {
            "answer": GREETING,
            "scam_type": None,
            "confidence": None,
            "engine": "personality",
            "profile": "default",
        }
    elif intent == "about":
        result = {
            "answer": ABOUT,
            "scam_type": None,
            "confidence": None,
            "engine": "personality",
            "profile": "default",
        }
    elif intent == "unclear":
        result = {
            "answer": UNCLEAR,
            "scam_type": None,
            "confidence": None,
            "engine": "personality",
            "profile": "default",
        }
    else:
        prior_scam = None
        prior_scam_hist = [
            e for e in get_scam_history(session_id)
            if e["role"] == "assistant" and e.get("scam_type")
        ]
        if prior_scam_hist:
            prior_scam = prior_scam_hist[-1]["scam_type"]
        result = retrieve_and_respond(message, prior_scam_type=prior_scam)

        if result.get("scam_type"):
            fingerprint = extract_all(message)
            result["fingerprint"] = fingerprint

        # pattern detection
        pattern_note = compare_with_history(session_id, result)
        if pattern_note:
            result["answer"] = result["answer"] + "\n\n" + pattern_note

        # profile-aware formatting
        profile = detect_profile(session_id, message)
        if profile == "elderly" and result.get("scam_type"):
            result["answer"] = format_elderly(result)
        elif profile == "farmer" and result.get("scam_type"):
            result["answer"] = format_farmer(result)

        if lure_detected:
            result["answer"] = _VERIFICATION_LURE_WARNING + "\n\n" + result["answer"]

        result["profile"] = profile

    add_to_memory(
        session_id,
        "assistant",
        result["answer"],
        scam_type=result.get("scam_type"),
        fingerprint=result.get("fingerprint"),
    )

    result["intent"] = intent
    result["session_id"] = session_id
    result["history_length"] = len(_sessions.get(session_id, []))
    return result
