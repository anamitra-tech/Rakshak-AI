"""
LLM explanation layer for scam-classification results.

Unlike the earlier design this replaces (ml/llm_second_opinion.py, now
deleted), this module NEVER influences risk_level, score, rule_categories,
or signals. Those are decided entirely by ml/detector.py's rules + ML
classifier, upstream of anything in this file, and are verified (see
eval_testset.py) to be byte-for-byte identical whether or not this module
is invoked, succeeds, or fails.

This module's only job: once a verdict is already final, ask the existing
Gemini -> Groq -> Ollama chain (llm/client.py) to put that verdict into
plain language for the specific message at hand, instead of the generic
templated sentence ml/detector.py/voice/voice_fraud.py build by default.
If the chain fails, times out, or is skipped, the caller's original
templated `reason` string is left completely untouched.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeoutError

from llm.client import generate

logger = logging.getLogger(__name__)

# Only bother calling the LLM when there's something non-trivial to explain —
# a plain SAFE/REAL verdict with no signals already has a clear, correct
# canned reason ("no fraud patterns detected"); enriching that adds latency
# and quota spend for zero benefit.
EXPLAIN_LEVELS = {"SUSPICIOUS", "FRAUD"}

# Generous budget relative to the earlier second-opinion layer's 4s: a slow
# or failed explanation can never affect the verdict itself, only whether the
# richer text shows up in the response, so there's less to lose by waiting a
# little longer for it. Measured real Gemini 2.5 Flash latency on this setup
# is ~3.5-5s for a prompt this size (see llm_explainer latency notes / eval
# output) — this budget is sized to usually let a real answer land rather
# than reflexively falling back.
EXPLAIN_TIMEOUT_SECONDS = 6.0

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="llm-explainer")

_PROMPT_TEMPLATE = """You are writing the plain-language "why" shown to a user of a scam-call/message screening app. A classifier has ALREADY decided this message is {level} risk. Do not question, second-guess, or restate a different risk level — your only job is to explain, in 2-3 short sentences a non-technical user can follow, why THIS specific message matches THAT verdict.

Message:
\"\"\"{text}\"\"\"

Signals the classifier detected: {signals}

Write a 2-3 sentence explanation of why this message is {level} risk, referring to specifics in the message itself (not generic boilerplate). Do not mention "classifier", "score", "rule", or that you are an AI. Respond with ONLY the explanation text, nothing else — no preamble, no quotes, no markdown."""


def should_explain(risk_level):
    return risk_level in EXPLAIN_LEVELS


def _generate_explanation(text, risk_level, signals):
    signals_str = "; ".join(signals) if signals else "general risk language in the message"
    prompt = _PROMPT_TEMPLATE.format(level=risk_level, text=text, signals=signals_str)
    return generate(prompt, retries=1)


def explain(text, risk_level, signals):
    """Never raises. Returns a dict describing what happened; never touches
    risk_level/score/rule_categories — those are the caller's business,
    decided before this function is ever called."""
    if not should_explain(risk_level):
        return {"used": False, "explanation": None, "engine": None, "latency_ms": 0, "error": None}

    t0 = time.monotonic()
    future = _executor.submit(_generate_explanation, text, risk_level, signals)
    try:
        response = future.result(timeout=EXPLAIN_TIMEOUT_SECONDS)
        latency_ms = round((time.monotonic() - t0) * 1000)
        explanation = response.text.strip()
        logger.info("LLM explanation generated: engine=%s latency_ms=%d", response.engine, latency_ms)
        return {"used": True, "explanation": explanation, "engine": response.engine,
                 "latency_ms": latency_ms, "error": None}
    except _FutureTimeoutError:
        latency_ms = round((time.monotonic() - t0) * 1000)
        logger.warning(
            "LLM explanation TIMED OUT after %d ms (budget %.1fs) — keeping rule-based reason text.",
            latency_ms, EXPLAIN_TIMEOUT_SECONDS,
        )
        return {"used": False, "explanation": None, "engine": None,
                 "latency_ms": latency_ms, "error": f"timeout after {EXPLAIN_TIMEOUT_SECONDS}s"}
    except Exception as e:
        latency_ms = round((time.monotonic() - t0) * 1000)
        logger.warning(
            "LLM explanation FAILED after %d ms: %s — keeping rule-based reason text.",
            latency_ms, e,
        )
        return {"used": False, "explanation": None, "engine": None,
                 "latency_ms": latency_ms, "error": str(e)}


def apply(result, text):
    """Mutates and returns `result`: on success, replaces result["reason"]
    with the richer LLM text and attaches result["llm_explanation"] metadata.
    On skip/failure/timeout, result["reason"] is left exactly as the caller
    computed it — risk_level/score/rule_categories/signals are never read or
    written here beyond passing risk_level/signals into the prompt."""
    outcome = explain(text, result["risk_level"], result.get("signals"))
    result["llm_explanation"] = outcome
    if outcome["used"] and outcome["explanation"]:
        result["reason"] = outcome["explanation"]
    return result
