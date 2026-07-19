"""
Deterministic prompt-injection screen for the /chat endpoint. Checked before
any retrieval or LLM call in assistant/pipeline.py::handle_chat.

Deliberately rule-based, not an LLM classification call — same "rule layer
first" philosophy already used elsewhere in this repo for safety-critical
gates (bot/agent.py's is_pushback/is_verification_lure, ml/detector.py's
HIGH_RISK_PATTERNS): a regex/keyword check is fast, free, and never flaky,
which matters for a gate an eval harness scores pass/fail on.

Scope, per the /chat spec: decline politely and redirect to what the bot can
actually help with. No reporting/blocking/NCRP-involvement mechanism — that
would be fabricated capability for a citizen-protection tool, not a real one.
"""
import re

_INJECTION_PATTERNS = [
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|your\s+|the\s+)*(previous|prior|above|earlier)?\s*instructions",
    r"(reveal|show|print|output|repeat) (your |the )?(system prompt|instructions|prompt)",
    r"what (is|are) your (system prompt|instructions)",
    r"you are now[ ,]",
    r"act as (a|an) (?!.{0,3}legal|.{0,3}citizen)",
    r"pretend (you are|to be)",
    r"roleplay as",
    r"jailbreak",
    r"dan mode",
    r"developer mode",
    r"\bsystem:\s",
    r"\[system\]",
    r"override (your |the )?(rules|instructions|guidelines)",
    r"new instructions?:",
    r"your new (task|role|instructions?) (is|are)",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

DECLINE_MESSAGE = (
    "I can't follow instructions that try to change how I work — I'm only able "
    "to help with questions about cybercrime reporting, consumer rights, and "
    "related citizen-protection information. Please ask me something in that "
    "area and I'll do my best to help."
)


def is_injection_attempt(message: str) -> bool:
    return any(pattern.search(message) for pattern in _COMPILED)
