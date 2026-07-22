import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError

from llm.client import generate
from ml.detector import ScamDetector
from rag.store import retrieve

logger = logging.getLogger(__name__)

# Single source of truth for risk_level/score — the same classifier proven at
# 0% FPR / 100% recall on the phone app's pipeline (see eval_testset.py).
# FAISS retrieval below is used ONLY to pull the most relevant kb/scams.json
# card(s) to ground the LLM's explanation text; it no longer decides SCAM/SAFE
# on its own.
_DETECTOR = ScamDetector()

# Bounds how long we wait for the LLM explanation chain (Gemini -> Groq ->
# Ollama) before falling back to the classifier's own built-in reason text —
# mirrors ml/llm_explainer.py's timeout pattern for the phone-app pipeline.
_LLM_TIMEOUT_SECONDS = 6.0
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-explainer")

_REFUSAL_ANSWER = (
    "This doesn't match any scam pattern I know.\n\n"
    "If you received a call and feel uncertain, the safest check is always: "
    "hang up, look up the official number yourself, and call back.\n\n"
    "1930 is available if you need help."
)

_SCAM_AUTHORITY = {
    "digital_arrest": "CBI/ED/Police",
    "bank_otp_kyc": "banks",
    "aadhaar_biometric_freeze": "UIDAI",
    "sanchar_saathi_sim_swap": "telecom authorities",
    "fake_job_offer_apk": "legitimate companies",
    "corporate_malware_bec": "financial institutions",
    "investment_fraud": "SEBI-registered advisors",
    "qr_code_fraud": "payment services",
    "lottery_prize_fraud": "prize authorities",
    "smishing_link": "delivery companies",
    "location_lure": "government agencies",
    "multi_call_escalation": "government agencies",
    "isolation_tactics": "banks, police, or government agencies",
    "otp_readout_request": "banks, police, or government agencies",
    "card_collection_request": "banks or government agencies",
}

_CONFIRM_KW = {
    "sure", "confirm", "pakka", "sach mein", "real hai kya", "genuine hai",
    "they say they are real", "real hai", "genuine", "real don't worry",
    "woh bol rahe hain", "real hain",
}

_PROMPT_TEMPLATE = """\
You are PraHARI-AI, a public safety assistant for Indian citizens.
A citizen has sent this message: "{user_message}"

Our fraud classifier has already assessed this as {risk_level} risk, matching a known scam pattern:
Scam type: {scam_type}
What to do: {what_to_do}

Respond in English only. 2-3 sentences maximum. Be direct and clear.
Always end with: "Report to 1930 or cybercrime.gov.in"
Do not add any information not provided above.\
"""

_POST_OPEN_SIGNALS = [
    "already opened", "khol diya", "khol di", "open kar liya",
    "download kar liya", "file run", "clicked", "extracted",
]

_POST_OPEN_APPEND = (
    "\n\nIf you have already clicked or opened the link/file — "
    "disconnect from the internet immediately and call 1930."
)


def _is_post_open(message: str) -> bool:
    m = message.lower()
    return any(sig in m for sig in _POST_OPEN_SIGNALS)


def _is_confirmation(message: str) -> bool:
    m = message.lower()
    return any(kw in m for kw in _CONFIRM_KW)


def retrieve_and_respond(
    user_message: str,
    prior_scam_type: str | None = None,
) -> dict:
    if prior_scam_type and _is_confirmation(user_message):
        authority = _SCAM_AUTHORITY.get(prior_scam_type, "CBI/banks/UIDAI")
        return {
            "answer": (
                f"Real {authority} never contact citizens via WhatsApp or demand payment over phone. "
                "This is a confirmed scam pattern. "
                "Hang up immediately. Call 1930."
            ),
            "source_name": "National Cybercrime Helpline",
            "source_url": "https://cybercrime.gov.in",
            "scam_type": prior_scam_type,
            "confidence": 1.0,
            "engine": "confirmation_gate",
            "severity": "",
        }

    post_open = _is_post_open(user_message)
    det = _DETECTOR.predict(user_message)
    risk_level = det["risk_level"]

    if risk_level == "SAFE":
        return {
            "answer": _REFUSAL_ANSWER,
            "source_name": "National Cybercrime Helpline",
            "source_url": "https://cybercrime.gov.in",
            "scam_type": None,
            "confidence": det["score"],
            "engine": "classifier_safe",
            "severity": "",
        }

    results = retrieve(user_message, n=3)
    top = results[0] if results else None
    scam_type = top["scam_type"] if top else None
    what_to_do = top["what_to_do"] if top else det["recommended_action"]
    source_name = top["source_name"] if top else "National Cybercrime Helpline"
    source_url = top["source_url"] if top else "https://cybercrime.gov.in"
    severity = top.get("severity", "") if top else ""

    if post_open and top and top["scam_type"] == "corporate_malware_bec":
        return {
            "answer": top["if_already_opened"],
            "source_name": source_name,
            "source_url": source_url,
            "scam_type": scam_type,
            "confidence": det["score"],
            "engine": "post_open_gate",
            "severity": "CRITICAL",
        }

    answer, engine = _explain(user_message, risk_level, scam_type, what_to_do, det)

    if post_open:
        answer += _POST_OPEN_APPEND

    return {
        "answer": answer,
        "source_name": source_name,
        "source_url": source_url,
        "scam_type": scam_type,
        "confidence": det["score"],
        "engine": engine,
        "severity": severity,
    }


def _explain(
    user_message: str,
    risk_level: str,
    scam_type: str | None,
    what_to_do: str,
    det: dict,
) -> tuple[str, str]:
    """Ask the LLM chain to narrate the classifier's already-final verdict,
    grounded in the retrieved kb card. Never influences risk_level/scam_type —
    on failure or timeout, falls back to the classifier's own built-in reason
    text (self.build_reason()), same as the phone-app pipeline."""
    prompt = _PROMPT_TEMPLATE.format(
        user_message=user_message,
        risk_level=risk_level,
        scam_type=scam_type or "suspicious activity",
        what_to_do=what_to_do,
    )
    future = _executor.submit(generate, prompt, retries=1)
    try:
        llm_response = future.result(timeout=_LLM_TIMEOUT_SECONDS)
        return llm_response.text, llm_response.engine
    except _FutureTimeoutError:
        logger.warning(
            "RAG explanation TIMED OUT after %.1fs — falling back to classifier reason.",
            _LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("RAG explanation FAILED (%s) — falling back to classifier reason.", exc)

    return f"{det['reason']}\n\n{det['recommended_action']}", "classifier_reason_fallback"
