"""
Evaluation harness for eval_chat_testset.json against the /chat endpoint's
assistant.pipeline.handle_chat() -- a separate corpus (kb/legal_info.json)
and a separate pipeline from eval_testset.py (voice/voice_fraud.py) and
eval_rag_testset.py (bot.agent.chat()), neither of which this script touches
or depends on.

Each case runs with a fresh, unique session_id (same isolation reasoning as
eval_rag_testset.py), which also means every case is a "new session" and gets
assistant.pipeline.INTRO_MESSAGE prepended to its reply -- this is expected,
not a bug: it's a real per-case test of the intro-message behavior, not just
of retrieval/generation.

Computes real numbers, one LLM-judge call per metric (never the generation
call grading itself):
  - Recall@5 / Precision@5: retrieval quality, measured directly off
    assistant.pipeline.retrieve_candidates()+rerank(), independent of
    generation.
  - Faithfulness: read off handle_chat()'s own metrics["faithfulness_check"]
    -- pipeline.py already runs a separate skeptical LLM-judge call for this
    on every real request; not duplicated here.
  - Answer relevance / Correctness: two further separate LLM-judge calls.
  - Unanswerable handling: reply contains the safe "don't have information"
    fallback text, not a fabricated answer.
  - Injection handling: reply is the guardrail decline message -- since
    assistant/guardrails.py is a deterministic rule check (no LLM), a
    triggered case's reply is always this exact fixed string, so this line
    is not flaky the way an LLM-graded check would be.

Honest caveat, reported here rather than hidden: kb/legal_info.json has only
5 entries, and retrieve_candidates()'s default top_n=10 retrieves the entire
corpus every time -- so Recall@5 is closer to a "retrieval index isn't
broken" sanity check than a real ranking test, and Precision@5 is
mechanically ~0.2 (1 relevant / 5 total) for every kb_question case. Reported
as specified anyway, not silently reinterpreted -- same honesty standard as
eval_testset.py's fp24 note.

Usage: python eval_chat_harness.py
"""
import json
import sys
import time

# Windows' console defaults to cp1252, which can't encode characters like the
# rupee sign (Rs.) that real LLM-judge reasons and generated answers routinely
# contain -- without this, a print() mid-report raises UnicodeEncodeError and
# silently truncates the rest of the failing-cases output (a real crash hit
# 2026-07-21, discovered because it hid whether specific cases had passed).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from assistant.pipeline import (
    confidence_floor_check,
    handle_chat,
    handle_chat_multilang,
    rerank,
    retrieve_candidates,
    rewrite_query,
)
from bot.sarvam_translate import detect_native_script_lang
from llm.client import generate

with open("eval_chat_testset.json", encoding="utf-8") as f:
    DATA = json.load(f)

CASES = DATA["cases"]

with open("kb/legal_info.json", encoding="utf-8") as f:
    _KB_BY_ID = {e["id"]: e for e in json.load(f)}


_RELEVANCE_JUDGE_PROMPT = """\
Question: "{question}"
Answer: "{answer}"

Does the answer directly address what was asked, rather than talking past it \
or answering a different question? Respond with exactly one word first -- \
YES or NO -- followed by a colon and a one-sentence reason.\
"""

_CORRECTNESS_JUDGE_PROMPT = """\
Source text: "{source}"

Answer given to a citizen: "{answer}"

Is the answer's conclusion factually accurate given the source text -- no \
contradictions, no invented facts? Respond with exactly one word first -- \
YES or NO -- followed by a colon and a one-sentence reason.\
"""

# Same two judge questions, but the answer may be in a different language
# than the source/question (assistant.pipeline.handle_chat_multilang
# translates the final reply into the caller's own script) -- explicitly
# told this up front so the judge doesn't mark a correct, non-English answer
# wrong just for not matching the source's language.
_RELEVANCE_JUDGE_PROMPT_MULTILANG = """\
Question (English): "{question}"
Answer (may be in a different language -- read it in its own language, \
that is expected and correct): "{answer}"

Does the answer directly address what was asked, rather than talking past it \
or answering a different question? Judge the answer's MEANING, not its \
language. Respond with exactly one word first -- YES or NO -- followed by a \
colon and a one-sentence reason.\
"""

_CORRECTNESS_JUDGE_PROMPT_MULTILANG = """\
Source text (English): "{source}"

Answer given to a citizen (may be in a different language -- read it in its \
own language, that is expected and correct): "{answer}"

Is the answer's conclusion factually accurate given the source text -- no \
contradictions, no invented facts? Judge the answer's MEANING, not its \
language. Respond with exactly one word first -- YES or NO -- followed by a \
colon and a one-sentence reason.\
"""


_FALLBACK_MARKERS = (
    "don't have verified information",
    "something went wrong on our side",
)


def _is_safe_fallback(reply: str) -> bool:
    """True if the pipeline degraded to a fixed safe-fallback string (confidence
    floor, citation failure, faithfulness rejection, or the generic exception
    fallback) rather than returning a real generated answer. Judging relevance/
    correctness of a fixed fallback sentence against the source isn't a
    meaningful test of generation quality -- it just re-tests whatever caused
    the fallback, which metrics/error already capture more precisely."""
    lower = reply.lower()
    return any(marker in lower for marker in _FALLBACK_MARKERS)


def _judge(prompt: str) -> tuple[bool, str]:
    try:
        response = generate(prompt, retries=1)
        text = response.text.strip()
        return text.upper().startswith("YES"), text
    except Exception as exc:
        return False, f"judge call failed: {exc}"


def _eval_retrieval(case: dict) -> dict:
    rewritten = rewrite_query(case["text"], [])
    candidates = retrieve_candidates(rewritten)
    floor_passed = confidence_floor_check(candidates)
    reranked = rerank(rewritten, candidates) if candidates else []
    top5_ids = [e["id"] for e in reranked[:5]]

    expected = case["expected_source_id"]
    recall_hit = expected in top5_ids
    relevant_in_top5 = sum(1 for i in top5_ids if i == expected)
    precision = relevant_in_top5 / len(top5_ids) if top5_ids else 0.0

    return {
        "rewritten_query": rewritten,
        "top5_ids": top5_ids,
        "floor_passed": floor_passed,
        "recall_hit": recall_hit,
        "precision_at_5": precision,
    }


def run():
    results = []
    t0 = time.time()

    for i, c in enumerate(CASES):
        session_id = f"eval_chat_{c['id']}"
        t_case = time.time()
        is_multilang = c["category"] == "kb_question_multilang"
        try:
            r = handle_chat_multilang(session_id, c["text"]) if is_multilang else handle_chat(session_id, c["text"])
            error = None
        except Exception as e:
            r = {"reply": "", "sources": [], "metrics": {}}
            error = f"{type(e).__name__}: {e}"
        elapsed = time.time() - t_case

        row = {
            **c,
            "reply": r.get("reply", ""),
            "metrics": r.get("metrics", {}),
            "elapsed_s": round(elapsed, 2),
            "error": error,
        }

        if c["category"] == "kb_question":
            row.update(_eval_retrieval(c))
            row["degraded_to_fallback"] = _is_safe_fallback(row["reply"])

            if row["degraded_to_fallback"]:
                row["answer_relevant"] = None
                row["relevance_reason"] = "N/A -- pipeline degraded to safe fallback, not a real generated answer"
                row["correct"] = None
                row["correctness_reason"] = row["relevance_reason"]
                row["faithful"] = None
            else:
                source = _KB_BY_ID[c["expected_source_id"]]["body"]
                relevant, relevance_reason = _judge(
                    _RELEVANCE_JUDGE_PROMPT.format(question=c["text"], answer=row["reply"])
                )
                correct, correctness_reason = _judge(
                    _CORRECTNESS_JUDGE_PROMPT.format(source=source, answer=row["reply"])
                )
                row["answer_relevant"] = relevant
                row["relevance_reason"] = relevance_reason
                row["correct"] = correct
                row["correctness_reason"] = correctness_reason
                row["faithful"] = row["metrics"].get("faithfulness_check") == "passed"

        elif c["category"] == "unanswerable":
            row["correctly_declined"] = "don't have verified information" in row["reply"].lower()

        elif c["category"] == "injection":
            row["correctly_declined"] = "can't follow instructions" in row["reply"].lower()
            row["never_reached_retrieval"] = "rewritten_query" not in row["metrics"]

        elif c["category"] == "kb_question_multilang":
            # Real pipeline signals, not a side computation: degraded-to-
            # fallback is read off handle_chat()'s own metrics (surfaced
            # unchanged through handle_chat_multilang) rather than string-
            # matching the reply, since a translated fallback no longer
            # contains the English marker text _is_safe_fallback() looks for.
            # "error" in metrics, not row["metrics"].get("error") -- a bare
            # `raise TimeoutError()` (no message arg) stringifies to "",
            # which is falsy and would silently un-flag a real degraded-to-
            # fallback case (caught live: 2026-07-22, all 4 ml* cases hit
            # handle_chat's internal exception fallback under concurrent LLM
            # load from other scripts running at the same time, but str(exc)
            # was "" for a TimeoutError, so `.get("error")` truthiness missed
            # every one of them).
            row["degraded_to_fallback"] = bool(
                row["metrics"].get("confidence_floor") == "below_threshold"
                or row["metrics"].get("citation_check") == "failed_after_retry"
                or row["metrics"].get("faithfulness_check") == "failed"
                or "error" in row["metrics"]
            )
            row["translated_in"] = row["metrics"].get("translated_in")
            row["translated_out"] = row["metrics"].get("translated_out")
            row["sources"] = r.get("sources", [])
            row["source_correct"] = c["expected_source_id"] in [s["id"] for s in row["sources"]]
            row["reply_script_detected"] = detect_native_script_lang(row["reply"])
            row["reply_in_correct_script"] = row["reply_script_detected"] == c["lang_tag"]

            if row["degraded_to_fallback"]:
                row["answer_relevant"] = None
                row["relevance_reason"] = "N/A -- pipeline degraded to safe fallback, not a real generated answer"
                row["correct"] = None
                row["correctness_reason"] = row["relevance_reason"]
            else:
                base_case = next(bc for bc in CASES if bc["id"] == c["base_case_id"])
                source = _KB_BY_ID[c["expected_source_id"]]["body"]
                relevant, relevance_reason = _judge(
                    _RELEVANCE_JUDGE_PROMPT_MULTILANG.format(question=base_case["text"], answer=row["reply"])
                )
                correct, correctness_reason = _judge(
                    _CORRECTNESS_JUDGE_PROMPT_MULTILANG.format(source=source, answer=row["reply"])
                )
                row["answer_relevant"] = relevant
                row["relevance_reason"] = relevance_reason
                row["correct"] = correct
                row["correctness_reason"] = correctness_reason

        results.append(row)
        status = f"ERROR: {error}" if error else row["reply"][:60].replace("\n", " ")
        print(f"  [{i+1}/{len(CASES)}] {c['id']:6s} ({elapsed:5.1f}s) {c['category']:12s} {status}")

    elapsed_total = time.time() - t0
    print(f"\nTotal wall time: {elapsed_total:.1f}s across {len(CASES)} cases\n")

    kb_rows = [r for r in results if r["category"] == "kb_question"]
    unans_rows = [r for r in results if r["category"] == "unanswerable"]
    inj_rows = [r for r in results if r["category"] == "injection"]
    multilang_rows = [r for r in results if r["category"] == "kb_question_multilang"]

    if kb_rows:
        answered_rows = [r for r in kb_rows if not r["degraded_to_fallback"]]
        degraded_rows = [r for r in kb_rows if r["degraded_to_fallback"]]
        recall = sum(1 for r in kb_rows if r["recall_hit"]) / len(kb_rows)
        precision = sum(r["precision_at_5"] for r in kb_rows) / len(kb_rows)
        print(f"KB questions (n={len(kb_rows)}, {len(answered_rows)} answered / "
              f"{len(degraded_rows)} degraded to safe fallback):")
        print(f"  Recall@5:               {recall:.3f}")
        print(f"  Precision@5:            {precision:.3f}  (mechanically ~0.2/case -- see module "
              f"docstring: 5-doc corpus, top_n=10 retrieves everything)")
        if answered_rows:
            faithful = sum(1 for r in answered_rows if r["faithful"]) / len(answered_rows)
            relevant = sum(1 for r in answered_rows if r["answer_relevant"]) / len(answered_rows)
            correct = sum(1 for r in answered_rows if r["correct"]) / len(answered_rows)
            print(f"  Faithfulness pass-rate: {faithful:.3f}  (of {len(answered_rows)} answered cases)")
            print(f"  Answer relevance:       {relevant:.3f}  (of {len(answered_rows)} answered cases)")
            print(f"  Correctness:            {correct:.3f}  (of {len(answered_rows)} answered cases)")
        else:
            print("  Faithfulness/relevance/correctness: n/a -- every case degraded to fallback")

    if unans_rows:
        acc = sum(1 for r in unans_rows if r["correctly_declined"]) / len(unans_rows)
        print(f"\nUnanswerable handling (n={len(unans_rows)}): {acc:.3f} correctly returned safe fallback")

    if inj_rows:
        acc = sum(1 for r in inj_rows if r["correctly_declined"]) / len(inj_rows)
        print(f"Injection handling (n={len(inj_rows)}): {acc:.3f} correctly declined")

    if multilang_rows:
        answered_ml = [r for r in multilang_rows if not r["degraded_to_fallback"]]
        print(f"\nMulti-language /chat (n={len(multilang_rows)}, {len(answered_ml)} answered / "
              f"{len(multilang_rows) - len(answered_ml)} degraded to safe fallback):")
        for r in multilang_rows:
            tag = " [degraded]" if r["degraded_to_fallback"] else ""
            print(f"  [{r['id']}] lang={r['lang_tag']}{tag} translated_in={r['translated_in']} "
                  f"translated_out={r['translated_out']} source_correct={r['source_correct']} "
                  f"reply_in_correct_script={r['reply_in_correct_script']} "
                  f"relevant={r.get('answer_relevant')} correct={r.get('correct')}")
        source_acc = sum(1 for r in multilang_rows if r["source_correct"]) / len(multilang_rows)
        script_acc = sum(1 for r in multilang_rows if r["reply_in_correct_script"]) / len(multilang_rows)
        print(f"  Correct citation:       {source_acc:.3f}")
        print(f"  Reply in correct script:{script_acc:.3f}")
        if answered_ml:
            relevant = sum(1 for r in answered_ml if r["answer_relevant"]) / len(answered_ml)
            correct = sum(1 for r in answered_ml if r["correct"]) / len(answered_ml)
            print(f"  Answer relevance:       {relevant:.3f}  (of {len(answered_ml)} answered cases)")
            print(f"  Correctness:            {correct:.3f}  (of {len(answered_ml)} answered cases)")

    print("\nFailing cases (any check failed; a degraded-to-fallback case is not itself a "
          "failure unless recall_hit also failed -- see metrics for why it fell back):")
    any_failure = False
    for r in kb_rows:
        checks = ("recall_hit",) if r["degraded_to_fallback"] else ("recall_hit", "answer_relevant", "correct", "faithful")
        fails = [k for k in checks if r.get(k) is False]
        if fails or r["error"]:
            any_failure = True
            tag = " [degraded_to_fallback]" if r["degraded_to_fallback"] else ""
            print(f"  [{r['id']}]{tag} failed={fails} error={r['error']} text={r['text'][:60]!r}")
            if "recall_hit" in fails:
                print(f"      expected={r['expected_source_id']} got_top5={r.get('top5_ids')}")
            if "answer_relevant" in fails:
                print(f"      relevance_reason={r.get('relevance_reason')}")
            if "correct" in fails:
                print(f"      correctness_reason={r.get('correctness_reason')}")
            if "faithful" in fails:
                print(f"      faithfulness metrics={r['metrics']}")
        elif r["degraded_to_fallback"]:
            print(f"  [{r['id']}] degraded to safe fallback (not a failure): metrics={r['metrics']}")
    for r in unans_rows + inj_rows:
        if not r["correctly_declined"] or r["error"]:
            any_failure = True
            print(f"  [{r['id']}] category={r['category']} error={r['error']} reply={r['reply'][:80]!r}")
    for r in multilang_rows:
        checks = ("source_correct",) if r["degraded_to_fallback"] else ("source_correct", "reply_in_correct_script", "answer_relevant", "correct")
        fails = [k for k in checks if r.get(k) is False]
        if fails or r["error"]:
            any_failure = True
            tag = " [degraded_to_fallback]" if r["degraded_to_fallback"] else ""
            print(f"  [{r['id']}]{tag} lang={r['lang_tag']} failed={fails} error={r['error']} text={r['text'][:60]!r}")
            if "source_correct" in fails:
                print(f"      expected={r['expected_source_id']} got_sources={r['sources']}")
            if "reply_in_correct_script" in fails:
                print(f"      reply_script_detected={r['reply_script_detected']} reply={r['reply'][:100]!r}")
            if "answer_relevant" in fails:
                print(f"      relevance_reason={r.get('relevance_reason')}")
            if "correct" in fails:
                print(f"      correctness_reason={r.get('correctness_reason')}")
        elif r["degraded_to_fallback"]:
            print(f"  [{r['id']}] degraded to safe fallback (not a failure): metrics={r['metrics']}")
    if not any_failure:
        print("  none")

    return results


if __name__ == "__main__":
    run()
