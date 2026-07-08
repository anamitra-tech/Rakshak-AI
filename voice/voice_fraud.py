"""
MODULE 6 — Voice Fraud Detection (transcript-based simulation).

Classifies a call transcript as REAL / SUSPICIOUS / FRAUD. Score is voice-
aware: on top of Module 1's classifier score, this module adds a numeric
nudge when transcript-level manipulation cues combine (authority + fear +
payment coercion + isolation — the 'digital arrest' playbook shape).

The reason/signals shown to the user are NOT derived from those cues. They
always come from ml.detector.ScamDetector's own rule_categories, via its
build_signals()/build_reason() — the same single source of truth used by
the message path (ml/detector.py) and the RAG chat path (rag/retriever.py).
This used to be two independent regex layers: this module had its own
MANIPULATION_CUES-derived labels shown as "the reason", disconnected from
what rule_categories actually found. That let a bare, untightened cue (e.g.
"case (register|file)" under "fear_induction") surface a fabricated
"Fear induction (arrest/jail threats)" explanation for messages that
matched zero real fraud rules — see rakshak_eval_testset.json's otp3 case
for the traced example. Cues are now an internal score input only; they can
make the app more cautious (raise `score`), but can never be the reason the
user is shown.
"""
import re

from ml.detector import SUSPICIOUS_THRESHOLD

# Internal score-input only — see module docstring. A false/loose match here
# can at most nudge `score` upward; it is never surfaced as a displayed
# signal or reason.
MANIPULATION_CUES = {
    "isolation": [r"do not (tell|inform) (anyone|family|police)",
                  r"kisi ko mat batao", r"stay on the (call|line)",
                  r"do not disconnect", r"camera (on|band mat)"],
    "fear_induction": [r"arrest", r"jail", r"warrant", r"case (register|file)",
                       r"your (son|daughter|family) (is|will)"],
    "authority": [r"\bcbi\b", r"\bed\b", r"police", r"customs", r"court",
                  r"supreme court", r"officer", r"department"],
    "payment_coercion": [r"transfer", r"pay", r"settlement", r"fine",
                         r"safe account", r"rbi account", r"upi"],
    "verification_theatre": [r"verify your", r"confirm your", r"id proof",
                             r"badge number", r"case number", r"fir number"],
}


def analyze_transcript(transcript, detector=None):
    text = (transcript or "").strip()
    if not text:
        return _fmt("REAL", 0.0, "Empty transcript.", [], [])
    t = text.lower()

    cues = {cat for cat, pats in MANIPULATION_CUES.items() if any(re.search(p, t) for p in pats)}

    base_result = detector.predict(text) if detector else None
    base = base_result["score"] if base_result else 0.0
    rule_categories = base_result["rule_categories"] if base_result else []

    # voice-specific: the dangerous combo is authority + fear + payment +
    # isolation. This only ever adjusts the numeric score, per the module
    # docstring — it never contributes to what's shown as the reason.
    combo = sum(k in cues for k in ("authority", "fear_induction",
                                    "payment_coercion", "isolation"))
    score = max(base, min(1.0, 0.25 * combo))
    if {"isolation", "authority", "payment_coercion"} <= cues:
        score = max(score, 0.92)

    if score >= 0.7:
        level = "FRAUD"
    elif score >= SUSPICIOUS_THRESHOLD:
        level = "SUSPICIOUS"
    else:
        level = "REAL"

    if detector is not None:
        rules = {k: 1 for k in rule_categories}
        signals = detector.build_signals(rules)
        # ScamDetector's build_reason() only knows the "SAFE" spelling for
        # its lowest tier; this module's lowest tier is spelled "REAL" —
        # translate so the correct ("no fraud patterns detected") branch is
        # picked instead of the "language model flags risk" one.
        reason = detector.build_reason("SAFE" if level == "REAL" else level, rules, score)
    else:
        signals = []
        reason = ("No classifier available; unable to evaluate transcript."
                  if score < SUSPICIOUS_THRESHOLD else
                  f"Voice-pattern score {score:.0%}; no classifier available for detailed explanation.")

    return _fmt(level, round(score, 3), reason, signals, rule_categories)


def _fmt(level, score, reason, signals, rule_categories=None):
    action = {
        "FRAUD": "Hang up. No real officer arrests over a call/UPI. Report to 1930.",
        "SUSPICIOUS": "Be cautious. End call and verify via official department number.",
        "REAL": "No manipulation detected. Stay alert anyway.",
    }[level]
    return {"risk_level": level, "score": score, "reason": reason,
            "signals": signals, "recommended_action": action,
            "rule_categories": rule_categories or []}


if __name__ == "__main__":
    from ml.detector import ScamDetector
    d = ScamDetector()
    t = ("This is officer Sharma from CBI. There is an arrest warrant in your name. "
         "Do not disconnect the call and do not tell your family. To clear the case "
         "transfer the settlement amount to this RBI safe account immediately.")
    print(analyze_transcript(t, d))
