"""
Orchestration for the /chat endpoint (webhook/app.py's POST /chat handler
calls handle_chat() here). Legal/citizen-rights RAG over kb/legal_info.json —
entirely separate from bot/agent.py's chat() (WhatsApp scam-triage flow) and
rag/retriever.py (kb/scams.json). Session history is NOT a new store: it
reuses bot.agent.add_to_memory/get_history directly, per the /chat spec.

Deterministic parts (hybrid_search.py: dense cosine score, BM25, RRF fusion,
and the confidence-floor decision below) never involve the LLM. LLM calls
(query rewrite, rerank, generation, faithfulness judge) each follow the same
ThreadPoolExecutor + 6s-timeout + safe-fallback pattern already used by
bot/agent.py's intent router and rag/legal_retriever.py::_explain — an LLM
failure degrades the response, it never raises out to the HTTP layer.
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError

from bot.agent import add_to_memory, get_history
from llm.client import generate

from assistant.guardrails import DECLINE_MESSAGE, is_injection_attempt
from assistant.hybrid_search import hybrid_retrieve

logger = logging.getLogger(__name__)

_LLM_TIMEOUT_SECONDS = 6.0
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-assistant")

_KB_PATH = "kb/legal_info.json"

# Tuned against real dense-cosine scores measured on eval_chat_testset.json
# (BAAI/bge-m3, this 5-entry corpus): kb_question top-1 scores ranged
# 0.458-0.754, unanswerable/out-of-scope top-1 scores ranged 0.338-0.472 —
# these ranges OVERLAP (0.458-0.472), so no single threshold cleanly
# separates them. 0.44 was chosen to catch the clearest off-topic cases
# (2 of 4 in the eval set) without rejecting any genuine answerable
# question. Honest, disclosed consequence: some off-topic queries will pass
# this floor — verify_citations()/check_faithfulness() downstream are the
# real backstop for those, not this floor alone (same "real but imperfect,
# layered with something stronger" pattern as webhook/app.py's OCR
# confidence floor — see API_SPEC.md).
_CONFIDENCE_FLOOR = 0.44

_NO_INFO_ANSWER = (
    "I don't have verified information on that. Please check cybercrime.gov.in "
    "or call 1930 directly rather than relying on a guess here."
)

_ERROR_FALLBACK = "Something went wrong on our side. Please call 1930 directly or try again."

INTRO_MESSAGE = (
    "Namaste. This is PraHARI-AI's citizen information assistant. I can answer "
    "questions about reporting cybercrime (NCRP / 1930), your rights and "
    "protections as a bank customer and consumer, and how India's "
    "cybercrime-response agencies work — using only verified information from "
    "our knowledge base. If I don't have a confirmed answer to something, I "
    "will tell you plainly rather than guess. What would you like to know?"
)

_CITATION_RE = re.compile(r"\(Source:\s*([a-z0-9_]+)\)", re.IGNORECASE)


def _run_llm(prompt: str, timeout: float = _LLM_TIMEOUT_SECONDS, retries: int = 1, prefer_gemini: bool = False):
    future = _executor.submit(generate, prompt, retries, prefer_gemini=prefer_gemini)
    return future.result(timeout=timeout)


# Financial/legal nuance-dropping (a smaller/faster model stating a
# conditional rule as unconditional) is a real, higher-stakes failure mode
# than plain latency -- see API_SPEC.md 7.6/7.7. When the retrieved source
# text itself contains qualifying language a model could drop, force
# prefer_gemini=True for that specific generation call (same mechanism
# bot/agent.py::classify_intent() already uses), rather than reordering the
# engine chain globally again.
_CONDITIONAL_LANGUAGE_RE = re.compile(
    r"\b(provided that|unless|within \d+\s*(?:working\s+)?days?|subject to|"
    r"only if|as long as|conditional on|conditional upon)\b",
    re.IGNORECASE,
)


def _has_conditional_language(top_entries: list[dict]) -> bool:
    text = " ".join(f"{e['body']} {e['what_to_do']}" for e in top_entries)
    return bool(_CONDITIONAL_LANGUAGE_RE.search(text))


def _valid_ids() -> set[str]:
    with open(_KB_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["id"] for e in entries}


# ── Stage 1: query rewriting (LLM, times out to raw message) ──────────────────

_REWRITE_PROMPT = """\
You are helping search a small legal/citizen-rights knowledge base about \
Indian cybercrime reporting. Rewrite the user's message below into a single, \
clear search query: fix typos, resolve ambiguous pronouns using the \
conversation history, expand abbreviations. Output ONLY the rewritten query, \
nothing else — no explanation, no quotes.

Conversation history (most recent last):
{history}

User's message: "{message}"

Rewritten search query:\
"""


def rewrite_query(message: str, history: list[dict]) -> str:
    history_text = "\n".join(f"{h['role']}: {h['content']}" for h in history[-4:]) or "(none)"
    prompt = _REWRITE_PROMPT.format(history=history_text, message=message)
    try:
        response = _run_llm(prompt)
        rewritten = response.text.strip().strip('"')
        if rewritten:
            return rewritten
    except _FutureTimeoutError:
        logger.warning("Query rewrite TIMED OUT after %.1fs — using raw message.", _LLM_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Query rewrite FAILED (%s) — using raw message.", exc)
    return message


# ── Stage 2: hybrid retrieval + deterministic confidence floor ────────────────

def retrieve_candidates(query: str, top_n: int = 10) -> list[dict]:
    return hybrid_retrieve(query, top_n=top_n)


def confidence_floor_check(candidates: list[dict], threshold: float = _CONFIDENCE_FLOOR) -> bool:
    """Pure deterministic check on the top candidate's raw dense cosine
    similarity — never the LLM, never the RRF rank score. A candidate that
    only BM25 surfaced (no dense hit at all) is treated as below the floor,
    since dense cosine similarity is the one calibrated 0-1 confidence signal
    available here."""
    if not candidates:
        return False
    top_dense = candidates[0].get("dense_score")
    if top_dense is None:
        return False
    return top_dense >= threshold


# ── Stage 3: reranking (LLM, times out to RRF fusion order) ───────────────────

_RERANK_PROMPT = """\
A citizen asked (rewritten query): "{query}"

Here are candidate knowledge-base entries, each with an id and title. Order \
them from MOST to LEAST relevant to answering the query. Output ONLY a \
comma-separated list of ids in that order, nothing else.

{candidates}

Ordered ids:\
"""


def rerank(query: str, candidates: list[dict]) -> list[dict]:
    if len(candidates) <= 1:
        return candidates
    listing = "\n".join(f"- id: {c['id']} | title: {c['title']}" for c in candidates)
    prompt = _RERANK_PROMPT.format(query=query, candidates=listing)
    try:
        response = _run_llm(prompt)
        ids_in_order = [i.strip() for i in response.text.strip().split(",") if i.strip()]
        by_id = {c["id"]: c for c in candidates}
        reranked = [by_id[i] for i in ids_in_order if i in by_id]
        for c in candidates:
            if c["id"] not in ids_in_order:
                reranked.append(c)
        if reranked:
            return reranked
    except _FutureTimeoutError:
        logger.warning("Rerank TIMED OUT after %.1fs — keeping RRF fusion order.", _LLM_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Rerank FAILED (%s) — keeping RRF fusion order.", exc)
    return candidates


# ── Stage 4: generation, restricted to the retrieved chunks, cited by id ──────

_GENERATION_PROMPT = """\
You are PraHARI-AI's citizen information assistant. Answer the citizen's \
question using ONLY the knowledge-base entries given below — never use \
outside/general knowledge, never invent facts, section numbers, or figures \
not present in these entries.

Citizen's question: "{query}"

Knowledge-base entries:
{entries}

Write a plain-language answer in 2-5 sentences. After every factual claim, \
cite the entry it came from using this exact format: (Source: <id>). If the \
entries don't actually answer the question, say so plainly instead of \
guessing.\
"""


def _format_entries_for_prompt(entries: list[dict]) -> str:
    parts = []
    for e in entries:
        parts.append(
            f"id: {e['id']}\ntitle: {e['title']}\nbody: {e['body']}\n"
            f"what_to_do: {e['what_to_do']}\nsource: {e['source']['name']}"
        )
    return "\n\n".join(parts)


def generate_answer(
    query: str, top_entries: list[dict], strict: bool = False, prefer_gemini: bool = False
) -> tuple[str, str]:
    prompt = _GENERATION_PROMPT.format(query=query, entries=_format_entries_for_prompt(top_entries))
    if strict:
        valid = ", ".join(e["id"] for e in top_entries)
        prompt += f"\n\nReminder: the ONLY valid ids you may cite are: {valid}. Do not invent any other id."
    response = _run_llm(prompt, retries=1, prefer_gemini=prefer_gemini)
    return response.text.strip(), response.engine


# ── Stage 5: citation verification (deterministic) ────────────────────────────

def verify_citations(answer: str, valid_ids: set[str]) -> bool:
    cited = _CITATION_RE.findall(answer)
    if not cited:
        return False
    return all(c in valid_ids for c in cited)


def extract_sources(answer: str, top_entries: list[dict]) -> list[dict]:
    cited_ids = set(_CITATION_RE.findall(answer))
    return [
        {"id": e["id"], "title": e["title"], "url": e["source"]["url"]}
        for e in top_entries
        if e["id"] in cited_ids
    ]


# ── Stage 6: faithfulness check — separate skeptical LLM call, not the ────────
# ── generation call grading itself ─────────────────────────────────────────────

_FAITHFULNESS_PROMPT = """\
You are a strict, skeptical fact-checker. Below is source text and a drafted \
answer. Check whether EVERY factual claim in the answer is actually \
supported by the source text — no claim may go beyond what the source says.

Source text:
{sources}

Drafted answer:
{answer}

Respond with exactly one word first — APPROVED or REJECTED — followed by a \
colon and a one-sentence reason.\
"""


def check_faithfulness(answer: str, top_entries: list[dict]) -> tuple[bool, str]:
    # Must include what_to_do, not just body -- generate_answer()'s prompt
    # (_format_entries_for_prompt) hands the model both fields as legitimate
    # source material, so checking faithfulness against body alone falsely
    # rejects answers that correctly cited what_to_do content (real bug,
    # caught by eval_chat_harness.py's c3 case: "Keep your bank transaction
    # details, UPI ID, and screenshots ready" is real what_to_do text, not
    # a hallucination).
    sources_text = "\n\n".join(
        f"[{e['id']}] {e['body']} {e['what_to_do']}" for e in top_entries
    )
    prompt = _FAITHFULNESS_PROMPT.format(sources=sources_text, answer=answer)
    try:
        response = _run_llm(prompt, retries=1)
        verdict = response.text.strip()
        passed = verdict.upper().startswith("APPROVED")
        return passed, verdict
    except _FutureTimeoutError:
        return False, "faithfulness check timed out — failing closed"
    except Exception as exc:
        return False, f"faithfulness check failed ({exc}) — failing closed"


# ── Orchestrator ────────────────────────────────────────────────────────────

def _finalize(session_id: str, is_new_session: bool, reply: str, sources: list[dict], metrics: dict) -> dict:
    if is_new_session:
        reply = INTRO_MESSAGE + "\n\n" + reply
    add_to_memory(session_id, "assistant", reply, intent="legal_info_chat")
    return {"reply": reply, "sources": sources, "metrics": metrics}


def handle_chat(session_id: str, message: str) -> dict:
    metrics: dict = {}
    is_new_session = not get_history(session_id, last_n=1)

    try:
        if is_injection_attempt(message):
            add_to_memory(session_id, "user", message, intent="legal_info_chat")
            metrics["guardrail_triggered"] = "prompt_injection"
            return _finalize(session_id, is_new_session, DECLINE_MESSAGE, [], metrics)

        add_to_memory(session_id, "user", message, intent="legal_info_chat")

        history = get_history(session_id, last_n=6)[:-1]  # exclude the turn just added
        rewritten = rewrite_query(message, history)
        metrics["rewritten_query"] = rewritten

        candidates = retrieve_candidates(rewritten)
        if not confidence_floor_check(candidates):
            metrics["confidence_floor"] = "below_threshold"
            return _finalize(session_id, is_new_session, _NO_INFO_ANSWER, [], metrics)
        metrics["retrieval_top_dense_score"] = candidates[0].get("dense_score")

        reranked = rerank(rewritten, candidates)
        top5 = reranked[:5]
        valid_ids = _valid_ids()

        prefer_gemini_for_generation = _has_conditional_language(top5)
        metrics["conditional_language_detected"] = prefer_gemini_for_generation

        answer, engine = generate_answer(rewritten, top5, prefer_gemini=prefer_gemini_for_generation)
        metrics["engine"] = engine

        if not verify_citations(answer, valid_ids):
            logger.warning("Citation verification failed for session %s — retrying once.", session_id)
            answer, engine = generate_answer(
                rewritten, top5, strict=True, prefer_gemini=prefer_gemini_for_generation
            )
            metrics["engine"] = engine
            if not verify_citations(answer, valid_ids):
                metrics["citation_check"] = "failed_after_retry"
                return _finalize(session_id, is_new_session, _NO_INFO_ANSWER, [], metrics)
        metrics["citation_check"] = "passed"

        faithful, reason = check_faithfulness(answer, top5)
        metrics["faithfulness_check"] = "passed" if faithful else "failed"
        if not faithful:
            metrics["faithfulness_reason"] = reason
            return _finalize(session_id, is_new_session, _NO_INFO_ANSWER, [], metrics)

        sources = extract_sources(answer, top5)
        return _finalize(session_id, is_new_session, answer, sources, metrics)

    except Exception as exc:
        logger.exception("handle_chat failed unexpectedly for session %s", session_id)
        metrics["error"] = str(exc)
        return _finalize(session_id, is_new_session, _ERROR_FALLBACK, [], metrics)
