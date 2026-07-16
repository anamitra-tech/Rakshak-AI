"""
Shared calm-guidance detector + reply copy for an ongoing, already-flagged
scam session's first-person reactive follow-up ("he says he'll arrest me",
"usne kaha ki...", "what should I do") — as opposed to a scam script/message
being newly submitted for checking.

Originally built only inside webhook/app.py for the /whatsapp/webhook
pipeline (ml.detector + ml.session — see that module's real 2026-07-16 bug
fix). Extracted here so bot.agent.chat()'s ACTIVE_SESSION_FOLLOWUP intent
(a different pipeline, with its own separate session store — see
bot/agent.py's _was_already_active) can reuse the exact same detection
regex and reply copy instead of forking a second copy that could silently
drift from this one.

No dependency on webhook/app.py or Sarvam here on purpose: translation of
the English reply below into the user's preferred language is each caller's
own responsibility (webhook/app.py's /whatsapp/webhook has its own
Sarvam-translate wrapper for hi-IN passthrough + everything else; /webhook's
_process_webhook_message already translates every chat() answer uniformly
via _translate_reply_to_preference, so bot.agent.chat() just returns the
English text below and lets that existing call site handle it).
"""
import re

_CONVERSATIONAL_FOLLOWUP_PATTERNS = [
    r"\bhe\s+says\b", r"\bhe\s+told\s+me\b", r"\bhe'?s\s+(saying|asking|telling)\b",
    r"\bhe\s+is\s+(saying|asking|telling)\b", r"\bhe\s+wants\s+me\s+to\b",
    r"\bshe\s+says\b", r"\bshe\s+told\s+me\b", r"\bshe'?s\s+(saying|asking|telling)\b",
    r"\bthey'?re\s+saying\b", r"\bthey\s+are\s+saying\b", r"\bthey\s+told\s+me\b",
    r"\bthey\s+want\s+me\s+to\b",
    r"\bwhat\s+should\s+i\s+do\b", r"\bwhat\s+do\s+i\s+do\b",
    r"usne\s+kaha", r"usne\s+bola", r"unhone\s+kaha", r"vo\s+bol\s+raha",
    r"vo\s+keh\s+raha", r"voh\s+bol\s+raha", r"kya\s+kar[uü]\b",
    r"mujhe\s+kya\s+karna\s+chahiye",
    r"उसने\s+कहा", r"उन्होंने\s+कहा", r"वह\s+बोल\s+रहा", r"क्या\s+करूं",
]
_CONVERSATIONAL_FOLLOWUP_RE = re.compile(
    "|".join(_CONVERSATIONAL_FOLLOWUP_PATTERNS), re.IGNORECASE,
)


def is_conversational_followup(*texts: str) -> bool:
    """First-person reactive framing describing an ongoing situation, as
    opposed to a scam script/message being submitted for checking. Accepts
    one or more text variants (e.g. original + translated) — True if any
    of them match."""
    return any(_CONVERSATIONAL_FOLLOWUP_RE.search(t) for t in texts if t)


CONVERSATIONAL_FOLLOWUP_EN = (
    "I understand what you're describing. Please listen carefully:\n\n"
    "• Hang up the call right now, or stop replying if it's over message.\n"
    "• Do NOT share any OTP, PIN, or code — ever.\n"
    "• Do NOT send any money, no matter what they threaten.\n"
    "• Do NOT stay on the call out of fear — this is a known scam tactic.\n\n"
    "Report this at cybercrime.gov.in or call 1930."
)
CONVERSATIONAL_FOLLOWUP_HI = (
    "मैं समझ रहा/रही हूं कि क्या हो रहा है। कृपया ध्यान से सुनें:\n\n"
    "• अभी कॉल काट दें, या मैसेज का जवाब देना बंद कर दें।\n"
    "• कभी भी OTP, पिन या कोड साझा न करें।\n"
    "• डर के कारण पैसे बिल्कुल न भेजें।\n"
    "• डर की वजह से कॉल पर बने न रहें — यह एक जाना-पहचाना धोखाधड़ी तरीका है।\n\n"
    "cybercrime.gov.in पर रिपोर्ट करें या 1930 पर कॉल करें।"
)
