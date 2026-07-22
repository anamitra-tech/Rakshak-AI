"""
Real classifier — replaces classifier_placeholder.py.

Delegates entirely to this repo's existing AI/ML pipeline (ml/detector.py,
ml/llm_explainer.py) rather than reimplementing any detection logic here.
See classifier_placeholder.py's original docstring for the drop-in contract
this satisfies: classify(text, mode) -> dict with risk_score/verdict/
categories/reason.
"""
from ml.detector import ScamDetector
from ml import llm_explainer

# Built once at import time: ScamDetector() trains a small sklearn model on
# construction (see ml/detector.py::_train), so this must not be
# reconstructed per-request. Mirrors api/server.py's own DETECTOR = ScamDetector().
_DETECTOR = ScamDetector()

# ml/detector.py's risk_level vocabulary is SAFE/SUSPICIOUS/FRAUD; the
# schemas.AnalyzeResponse.verdict contract (fixed before this file existed,
# per the frontend already reading result.verdict) uses SAFE/SUSPICIOUS/SCAM.
_VERDICT_MAP = {"SAFE": "SAFE", "SUSPICIOUS": "SUSPICIOUS", "FRAUD": "SCAM"}


def classify(text: str, mode: str) -> dict:
    result = _DETECTOR.predict(text)
    if mode == "online":
        # Only rewrites result["reason"] for SUSPICIOUS/FRAUD via Gemini ->
        # Groq -> Ollama; never touches risk_level/score/rule_categories.
        llm_explainer.apply(result, text)
    return {
        "risk_score": result["score"],
        "verdict": _VERDICT_MAP[result["risk_level"]],
        "categories": result["rule_categories"],
        "reason": result["reason"],
    }
