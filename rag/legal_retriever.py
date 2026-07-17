"""
Answers INFORMATIONAL_QUERY intent messages (consumer/citizen rights,
NCRP/1930 process, RBI liability rules, DPDP Act basics, I4C/Chakshu's
actual role) — retrieves the most relevant kb/legal_info.json entry via
rag/legal_store.py's separate FAISS index, then has the LLM synthesize an
answer that names which entry/source it drew from, in the same
timeout-then-fallback shape as rag/retriever.py::_explain (per
CLAUDE.md Section 5: the RAG/LLM path is the most likely thing to fail to
start or time out, and must degrade gracefully rather than block).
"""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError

from llm.client import generate
from rag.legal_store import retrieve

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 6.0
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="legal-explainer")

_NO_MATCH_ANSWER = (
    "I don't have a specific, sourced answer for that — please check "
    "cybercrime.gov.in or call 1930 directly rather than relying on a guess here."
)

_FALLBACK_TEMPLATE = "{body}\n\nWhat to do: {what_to_do}\n\nSource: {source_name}"

_PROMPT_TEMPLATE = """\
You are PraHARI-AI, a public safety assistant for Indian citizens.
A citizen asked: "{user_message}"

Here is a sourced knowledge-base entry to answer from — use ONLY this \
information, do not add any fact not present here:

Title: {title}
Body: {body}
What to do: {what_to_do}
Source: {source_name}

Answer in 2-4 sentences, plain language, English only. You MUST end your \
answer by naming the source, in this exact form: "Source: {source_name}"
Do not invent section numbers, dates, or figures not given above.\
"""


def answer_legal_query(user_message: str) -> dict:
    results = retrieve(user_message, n=1)
    if not results:
        return {
            "answer": _NO_MATCH_ANSWER,
            "source_name": None,
            "source_url": None,
            "category": None,
            "engine": "legal_no_match",
        }

    top = results[0]
    answer, engine = _explain(user_message, top)
    return {
        "answer": answer,
        "source_name": top["source"]["name"],
        "source_url": top["source"]["url"],
        "category": top.get("category"),
        "engine": engine,
    }


def _explain(user_message: str, entry: dict) -> tuple[str, str]:
    prompt = _PROMPT_TEMPLATE.format(
        user_message=user_message,
        title=entry["title"],
        body=entry["body"],
        what_to_do=entry["what_to_do"],
        source_name=entry["source"]["name"],
    )
    future = _executor.submit(generate, prompt, retries=1)
    try:
        llm_response = future.result(timeout=_LLM_TIMEOUT_SECONDS)
        return llm_response.text, llm_response.engine
    except _FutureTimeoutError:
        logger.warning(
            "Legal-info explanation TIMED OUT after %.1fs — falling back to entry text.",
            _LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Legal-info explanation FAILED (%s) — falling back to entry text.", exc)

    fallback = _FALLBACK_TEMPLATE.format(
        body=entry["body"],
        what_to_do=entry["what_to_do"],
        source_name=entry["source"]["name"],
    )
    return fallback, "legal_fallback"
