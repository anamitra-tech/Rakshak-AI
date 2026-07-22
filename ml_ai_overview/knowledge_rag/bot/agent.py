import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError
from datetime import datetime, timezone

from llm.client import generate
from rag.retriever import retrieve_and_respond, _DETECTOR as _SCAM_DETECTOR
from rag.legal_retriever import answer_legal_query
from graph.entity_extractor import extract_all
from ml.detector import _rule_signals
from bot.calm_guidance import is_conversational_followup, CONVERSATIONAL_FOLLOWUP_EN
from bot.languages import english_name_to_tag, english_name_for_tag

logger = logging.getLogger(__name__)

# ── Personality strings ───────────────────────────────────────────────────────
# Used only as the LAST-RESORT fallback if the direct-reply LLM call below
# times out or fails entirely (see _direct_reply) — under normal operation
# GREETING/GENERAL_CHAT now get a live, context-aware LLM reply instead of
# always returning one of these fixed strings verbatim.

GREETING_FALLBACK = """🛡️ *Namaste! I'm PraHARI-AI.*

I help citizens identify scams — digital arrest calls, fake bank alerts, suspicious links, QR code fraud, and more.

Just tell me:
- What did the caller say?
- Forward me a suspicious message
- Share a link you're unsure about

I'll tell you if it's a scam and exactly what to do. 🔴🟢"""

GENERAL_CHAT_FALLBACK = """I didn't quite understand that. You can:
- Describe a suspicious call you received
- Forward a message you're unsure about
- Ask me what I do

I'm here to help. 🛡️"""

_DIRECT_REPLY_SYSTEM_CONTEXT = """\
You are PraHARI-AI, a public safety assistant for Indian citizens that detects \
scams (digital arrest calls, fake bank/KYC alerts, investment fraud, lottery \
scams, QR code fraud, suspicious links, malware attachments). You are free, \
powered by MHA/I4C intelligence. Emergency: 1930. Report: cybercrime.gov.in.

Reply to the user's message below in 1-3 sentences, warm and direct, plain \
language. If they're greeting you or making small talk, respond naturally \
and briefly mention you can check a suspicious call/message/link if they \
have one. Do not diagnose or discuss any scam here — that only happens when \
the user actually describes or pastes a suspicious call/message.

Conversation so far:
{history}

User: "{message}"\
"""

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


# ── Intent classification (LLM-based, replaces keyword/.startswith() routing) ─
#
# One LLM call per message, given the last few turns of history plus the new
# message, classifying into exactly one of 6 intents. This is the router
# item 1 of the rebuild asked for. It NEVER decides a scam verdict — that
# stays entirely with ml.detector.ScamDetector, called only from the
# SCAM_CHECK branch (or its ACTIVE_SESSION_FOLLOWUP fallback) below.
#
# MANDATORY SAFETY BACKSTOP (see chat()): before this classifier ever runs,
# a message is force-routed to SCAM_CHECK regardless of what the LLM would
# say if either (a) ml.detector's deterministic rule layer fires on it
# (_rule_signals), or (b) the full ScamDetector.predict() verdict (rules +
# trained ML score) is non-SAFE. Without this, an LLM misreading a live scam
# message as GENERAL_CHAT or INFORMATIONAL_QUERY (plausible — scam scripts
# often arrive phrased as questions, "what happens if I don't pay?") would
# silently skip ScamDetector.predict() entirely, which is the one regression
# the mandatory eval gate (see eval_rag_testset.py) can't catch after the
# fact once a message has already been routed away from the detector. This
# backstop is what makes "zero change to scam-detection behavior" enforceable
# rather than just hoped-for.
#
# (b) was added 2026-07-21 after a real miss traced via eval_rag_testset.py's
# iso3 case ("Sir, just hand the phone to me for two minutes, I'll do all the
# steps myself..."): _rule_signals() returned {} for that exact phrasing (no
# isolation_tactics regex literally matches "hand the phone to me"/"do all
# the steps myself"), yet ScamDetector.predict() still scored it SUSPICIOUS
# (0.613) purely off the trained ML component, with rule_categories: []. The
# LLM router then misclassified it as GENERAL_CHAT, and (a) alone had no way
# to catch a purely ML-driven verdict, so the message never reached
# ScamDetector.predict() via the SCAM_CHECK path at all. Checking the real
# verdict directly (not just whether a rule fired) closes that gap for any
# future paraphrase that only the trained model, not a regex, catches.

_VALID_INTENTS = {
    "greeting", "language_change", "scam_check",
    "active_session_followup", "informational_query", "general_chat",
}

_INTENT_PROMPT = """\
Classify the user's NEW message below into exactly one intent, using the \
conversation history for context (e.g. a short reactive reply like "what \
should I do?" is ACTIVE_SESSION_FOLLOWUP if the history shows an ongoing \
scam situation, but SCAM_CHECK if this is the first message in the session).

Intents:
- GREETING: a hello/how-are-you with no other content.
- LANGUAGE_CHANGE: the user is asking to switch the language you reply in \
(e.g. "reply to me in Tamil", "switch to Hindi"). If so, also extract the \
language name in English.
- SCAM_CHECK: the user is describing, quoting, or pasting a call/message/link \
they received and want checked — OR asking a hypothetical/general question \
about a scam pattern that could plausibly be describing something that \
happened to them. When in doubt between SCAM_CHECK and any other intent, \
choose SCAM_CHECK — never let ambiguity route a possible real scam away \
from checking.
- ACTIVE_SESSION_FOLLOWUP: a short, first-person, reactive message about an \
ONGOING situation already established in the conversation history (e.g. "he \
says he'll arrest me", "what do I do now") — not a new script/message being \
submitted for checking.
- INFORMATIONAL_QUERY: a general legal/factual question NOT about a specific \
incident — e.g. "is filing a police complaint free?", "will my bank refund \
me?", "what does Chakshu do?", "what are my data rights?".
- GENERAL_CHAT: anything else — small talk, "what do you do", thanks, etc.

Conversation history (may be empty):
{history}

New message: "{message}"

Reply with ONLY a JSON object, nothing else, in this exact shape:
{{"intent": "<ONE_OF_THE_6_ABOVE>", "language": "<English language name, or null>"}}\
"""

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="intent-router")
_INTENT_TIMEOUT_SECONDS = 6.0


def _format_history(session_id: str) -> str:
    turns = get_history(session_id, last_n=8)
    if not turns:
        return "(none — this is the first message)"
    lines = []
    for e in turns:
        role = "User" if e["role"] == "user" else "PraHARI-AI"
        lines.append(f"{role}: {e['content']}")
    return "\n".join(lines)


def _parse_intent_response(text: str) -> tuple[str, str | None]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    data = json.loads(cleaned[start:end + 1])
    intent = str(data.get("intent", "")).strip().lower()
    if intent not in _VALID_INTENTS:
        raise ValueError(f"unrecognized intent {intent!r}")
    language = data.get("language")
    language = str(language).strip() if language else None
    return intent, language


def classify_intent(session_id: str, message: str) -> tuple[str, str | None]:
    """Returns (intent, language_name_or_None). On any classifier failure
    (timeout, malformed JSON, LLM chain fully down), defaults to
    "scam_check" — the safest failure mode, since that path still runs
    ScamDetector.predict() and can itself return SAFE; every other intent
    risks silently never checking a message that might be a real scam."""
    # prefer_gemini=True: this call decides which intent branch fires (i.e.
    # whether ScamDetector even runs for a message the deterministic rule
    # backstop doesn't catch) -- keep Gemini as primary here specifically,
    # even while llm/client.py's default order is temporarily Groq-first
    # elsewhere. See llm/client.py::generate()'s docstring/comment for why.
    prompt = _INTENT_PROMPT.format(history=_format_history(session_id), message=message)
    future = _executor.submit(generate, prompt, retries=1, prefer_gemini=True)
    try:
        response = future.result(timeout=_INTENT_TIMEOUT_SECONDS)
        return _parse_intent_response(response.text)
    except _FutureTimeoutError:
        logger.warning("Intent classification TIMED OUT after %.1fs — defaulting to scam_check.", _INTENT_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Intent classification FAILED (%s) — defaulting to scam_check.", exc)
    return "scam_check", None


# ── Direct LLM reply for GREETING / GENERAL_CHAT ──────────────────────────────

def _direct_reply(session_id: str, message: str, fallback: str) -> tuple[str, str]:
    prompt = _DIRECT_REPLY_SYSTEM_CONTEXT.format(history=_format_history(session_id), message=message)
    future = _executor.submit(generate, prompt, retries=1)
    try:
        response = future.result(timeout=_INTENT_TIMEOUT_SECONDS)
        if response.text and len(response.text.strip()) > 0:
            return response.text.strip(), response.engine
    except _FutureTimeoutError:
        logger.warning("Direct-reply LLM call TIMED OUT — using fallback copy.")
    except Exception as exc:
        logger.warning("Direct-reply LLM call FAILED (%s) — using fallback copy.", exc)
    return fallback, "personality_fallback"


# ── Scam-check (shared by SCAM_CHECK and ACTIVE_SESSION_FOLLOWUP's fallback) ──

def _run_scam_check(session_id: str, message: str, lure_detected: bool) -> dict:
    """Unchanged verdict logic: ml.detector.ScamDetector via
    rag.retriever.retrieve_and_respond() is the ONLY thing that decides
    risk_level/scam_type — the intent router above never does."""
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

    pattern_note = compare_with_history(session_id, result)
    if pattern_note:
        result["answer"] = result["answer"] + "\n\n" + pattern_note

    profile = detect_profile(session_id, message)
    if profile == "elderly" and result.get("scam_type"):
        result["answer"] = format_elderly(result)
    elif profile == "farmer" and result.get("scam_type"):
        result["answer"] = format_farmer(result)

    if lure_detected:
        result["answer"] = _VERIFICATION_LURE_WARNING + "\n\n" + result["answer"]

    result["profile"] = profile
    return result


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
    # MANDATORY SAFETY BACKSTOP — see the doc comment above classify_intent().
    rule_hit = bool(_rule_signals(message))
    classifier_hit = _SCAM_DETECTOR.predict(message)["risk_level"] != "SAFE"
    language_name = None
    if lure_detected or rule_hit or classifier_hit:
        intent = "scam_check"
    else:
        intent, language_name = classify_intent(session_id, message)

    add_to_memory(session_id, "user", message, intent=intent)

    if intent == "greeting":
        answer, engine = _direct_reply(session_id, message, GREETING_FALLBACK)
        result = {
            "answer": answer,
            "scam_type": None,
            "confidence": None,
            "engine": engine,
            "profile": "default",
        }
    elif intent == "general_chat":
        answer, engine = _direct_reply(session_id, message, GENERAL_CHAT_FALLBACK)
        result = {
            "answer": answer,
            "scam_type": None,
            "confidence": None,
            "engine": engine,
            "profile": "default",
        }
    elif intent == "language_change":
        tag = english_name_to_tag(language_name) if language_name else None
        if tag:
            english_name = english_name_for_tag(tag)
            result = {
                "answer": f"Language preference noted: {english_name}.",
                "scam_type": None,
                "confidence": None,
                "engine": "language_change",
                "profile": "default",
                "lang_tag": tag,
            }
        else:
            result = {
                "answer": "Which language would you like me to reply in?",
                "scam_type": None,
                "confidence": None,
                "engine": "language_change_unclear",
                "profile": "default",
                "lang_tag": None,
            }
    elif intent == "informational_query":
        legal_result = answer_legal_query(message)
        result = {
            "answer": legal_result["answer"],
            "scam_type": None,
            "confidence": None,
            "engine": legal_result["engine"],
            "profile": "default",
            "source_name": legal_result.get("source_name"),
            "source_url": legal_result.get("source_url"),
        }
    elif intent == "active_session_followup":
        already_active = bool(get_scam_history(session_id))
        if already_active and is_conversational_followup(message):
            result = {
                "answer": CONVERSATIONAL_FOLLOWUP_EN,
                "scam_type": None,
                "confidence": None,
                "engine": "calm_guidance",
                "profile": detect_profile(session_id, message),
            }
        else:
            # The precondition ACTIVE_SESSION_FOLLOWUP depends on (an
            # already-flagged session + genuinely reactive phrasing) doesn't
            # actually hold -- never trust the LLM's label alone here. Falls
            # through to the full scam-check path rather than silently
            # dropping a message that might be a fresh scam ask.
            result = _run_scam_check(session_id, message, lure_detected)
    else:  # scam_check
        result = _run_scam_check(session_id, message, lure_detected)

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
