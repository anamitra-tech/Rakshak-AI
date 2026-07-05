"""
MODULE 6 — Voice Fraud Detection (transcript-based simulation).

Classifies a call transcript as REAL / SUSPICIOUS / FRAUD by detecting scam
*script* structure: authority impersonation, emotional manipulation,
isolation tactics, and urgency+payment coercion that characterise the
'digital arrest' playbook. Reuses Module 1 for base scoring and adds
voice-specific manipulation cues.
"""
import re

from ml.detector import SUSPICIOUS_THRESHOLD

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
        return _fmt("REAL", 0.0, "Empty transcript.", [])
    t = text.lower()

    cues = {}
    for cat, pats in MANIPULATION_CUES.items():
        if any(re.search(p, t) for p in pats):
            cues[cat] = True

    base_result = detector.predict(text) if detector else None
    base = base_result["score"] if base_result else 0.0
    rule_categories = base_result["rule_categories"] if base_result else []

    # voice-specific: the dangerous combo is authority + fear + payment + isolation
    combo = sum(k in cues for k in ("authority", "fear_induction",
                                    "payment_coercion", "isolation"))
    score = max(base, min(1.0, 0.25 * combo))
    if "isolation" in cues and "authority" in cues and "payment_coercion" in cues:
        score = max(score, 0.92)

    if score >= 0.7:
        level = "FRAUD"
    elif score >= SUSPICIOUS_THRESHOLD:
        level = "SUSPICIOUS"
    else:
        level = "REAL"

    labels = {
        "isolation": "Isolation tactic (keep victim on call, hide from family)",
        "fear_induction": "Fear induction (arrest/jail threats)",
        "authority": "Authority impersonation",
        "payment_coercion": "Payment coercion",
        "verification_theatre": "Fake verification ritual (badge/case numbers)",
    }
    signals = [labels[k] for k in cues]
    reason = (f"{level}: call exhibits {len(signals)} manipulation pattern(s) — "
              + "; ".join(signals) + ".") if signals else \
             "No scam-script manipulation patterns detected."
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
