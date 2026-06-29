from llm.client import generate
from rag.store import retrieve

_UNCERTAIN_ANSWER = (
    "I'm not certain about this one. Some signals match known scam patterns "
    "but not strongly enough for me to confirm.\n\n"
    "Do NOT share OTP, Aadhaar, or make any payment until you verify independently.\n\n"
    "To verify a real bank call: hang up and call the number on the back of your card.\n"
    "To verify a real government notice: visit the official portal directly — "
    "no real CBI/ED case is communicated via WhatsApp or phone.\n\n"
    "If anything feels wrong, call 1930."
)

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
}

_CONFIRM_KW = {"sure", "confirm", "pakka", "sach mein", "real hai kya", "genuine hai"}

_PROMPT_TEMPLATE = """\
You are Rakshak, a public safety assistant for Indian citizens.
A citizen has sent this message: "{user_message}"

Based on our intelligence database, this matches a known scam pattern:
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
                f"Yes, I'm confident. Real {authority} never contact citizens via "
                "WhatsApp call or ask for OTP/payment over phone. The pattern matches "
                "known fraud. Call 1930 to report — don't engage further with the caller."
            ),
            "source_name": "National Cybercrime Helpline",
            "source_url": "https://cybercrime.gov.in",
            "scam_type": prior_scam_type,
            "confidence": 1.0,
            "engine": "confirmation_gate",
            "severity": "",
        }

    post_open = _is_post_open(user_message)
    results = retrieve(user_message, n=3)
    score = results[0]["score"] if results else 0.0

    if score < 0.35:
        return {
            "answer": _REFUSAL_ANSWER,
            "source_name": "National Cybercrime Helpline",
            "source_url": "https://cybercrime.gov.in",
            "scam_type": None,
            "confidence": score,
            "engine": "refusal_gate",
            "severity": "",
        }

    if score < 0.5:
        return {
            "answer": _UNCERTAIN_ANSWER,
            "source_name": "National Cybercrime Helpline",
            "source_url": "https://cybercrime.gov.in",
            "scam_type": None,
            "confidence": score,
            "engine": "uncertain_gate",
            "severity": "",
        }

    top = results[0]

    if post_open and top["scam_type"] == "corporate_malware_bec":
        return {
            "answer": top["if_already_opened"],
            "source_name": top["source_name"],
            "source_url": top["source_url"],
            "scam_type": top["scam_type"],
            "confidence": top["score"],
            "engine": "post_open_gate",
            "severity": "CRITICAL",
        }

    prompt = _PROMPT_TEMPLATE.format(
        user_message=user_message,
        scam_type=top["scam_type"],
        what_to_do=top["what_to_do"],
    )
    llm_response = generate(prompt)
    answer = llm_response.text

    if post_open:
        answer += _POST_OPEN_APPEND

    return {
        "answer": answer,
        "source_name": top["source_name"],
        "source_url": top["source_url"],
        "scam_type": top["scam_type"],
        "confidence": top["score"],
        "engine": llm_response.engine,
        "severity": top.get("severity", ""),
    }
