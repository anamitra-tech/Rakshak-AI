from llm.client import generate
from rag.store import retrieve

_REFUSAL = {
    "answer": (
        "I don't have specific information about this pattern. "
        "To be safe, do not share money or personal details. "
        "Report any suspicious contact to 1930 or cybercrime.gov.in."
    ),
    "source_name": "National Cybercrime Helpline",
    "source_url": "https://cybercrime.gov.in",
    "scam_type": "unknown",
    "confidence": 0.0,
    "engine": "refusal_gate",
}

_PROMPT_TEMPLATE = """\
You are Rakshak, a public safety assistant for Indian citizens.
A citizen has sent this message: "{user_message}"

Based on our intelligence database, this matches a known scam pattern:
Scam type: {scam_type}
What to do: {what_to_do}

Respond in 2-3 sentences maximum. Be direct and clear.
Always end with: "Report to 1930 or cybercrime.gov.in"
Do not add any information not provided above.\
"""


def retrieve_and_respond(user_message: str) -> dict:
    results = retrieve(user_message, n=3)

    if not results or results[0]["score"] < 0.5:
        return dict(_REFUSAL)

    top = results[0]
    prompt = _PROMPT_TEMPLATE.format(
        user_message=user_message,
        scam_type=top["scam_type"],
        what_to_do=top["what_to_do"],
    )

    llm_response = generate(prompt)

    return {
        "answer": llm_response.text,
        "source_name": top["source_name"],
        "source_url": top["source_url"],
        "scam_type": top["scam_type"],
        "confidence": top["score"],
        "engine": llm_response.engine,
    }
