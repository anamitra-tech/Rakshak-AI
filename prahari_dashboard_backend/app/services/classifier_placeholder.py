"""
PLACEHOLDER — awaiting AI/ML integration.

This file exists ONLY so api/analyze.py has something to import while
the real classifier is being built by the AI/ML developer. Nothing in
here does real fraud detection: no rules, no scoring heuristics, no LLM
calls. It always returns the same fixed (fake) result, clearly labeled,
so it can never be mistaken for a working classifier.

--------------------------------------------------------------------
DROP-IN REPLACEMENT CONTRACT — read this before wiring in the real file
--------------------------------------------------------------------
The real implementation must expose a function with this exact
signature:

    def classify(text: str, mode: str) -> dict

Args:
    text: raw message/transcript text (already plain text — any STT/OCR
          happens on-device, before this function ever sees it).
    mode: "offline" (fast, ~6-10ms, rule/ML only) or "online" (slower,
          ~3-5s, LLM-generated `reason` via Gemini with Groq fallback).

Returns a dict with EXACTLY these keys (matching schemas.AnalyzeResponse):
    {
        "risk_score": float,        # 0.0-1.0
        "verdict": str,              # "SAFE" | "SUSPICIOUS" | "SCAM"
        "categories": list[str],     # zero or more of the 13 RuleCategory
                                      # values in models/schemas.py — [] is valid
        "reason": str,               # single string, never a list
    }

Contract notes from the handoff:
    - Empty input (text.strip() == "") must always return a fixed SAFE
      result — never null/error, in either mode.
    - Non-empty input must always return a real result — never null/error.

Once this function exists in the real file, api/analyze.py only needs
its import line changed (see the comment at the top of that file) —
no other code should need to change.
--------------------------------------------------------------------
"""

_PLACEHOLDER_REASON = (
    "[PLACEHOLDER — awaiting AI/ML integration] This is a fixed fake "
    "response from classifier_placeholder.py, not a real classification."
)

_FIXED_EMPTY_RESULT = {
    "risk_score": 0.0,
    "verdict": "SAFE",
    "categories": [],
    "reason": (
        "[PLACEHOLDER — awaiting AI/ML integration] Fixed SAFE result for "
        "empty input, per contract."
    ),
}

_FIXED_NONEMPTY_RESULT = {
    "risk_score": 0.42,
    "verdict": "SUSPICIOUS",
    "categories": ["urgency_coercion"],
    "reason": _PLACEHOLDER_REASON,
}


def classify(text: str, mode: str) -> dict:
    if not text.strip():
        return dict(_FIXED_EMPTY_RESULT)
    return dict(_FIXED_NONEMPTY_RESULT)
