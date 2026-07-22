"""
Evaluation harness for rakshak_eval_testset.json against the analyze_voice
pipeline (ml.detector.ScamDetector + voice.voice_fraud, the same code
api/server.py's /analyze_voice runs) — optionally with the LLM explanation
layer (ml/llm_explainer.py) applied on top, same as the live endpoint.

ml/llm_explainer.py only ever rewrites `reason`; it cannot touch risk_level,
score, or rule_categories. This harness proves that explicitly: it snapshots
risk_level/score right after analyze_transcript() (before the explainer runs)
and asserts they're byte-for-byte identical after llm_explainer.apply() runs,
for every case, every run — not just spot-checked.

Usage:
  python eval_testset.py            # with LLM explanation layer
  python eval_testset.py --no-llm   # baseline: classifier + rules only
"""
import json
import sys
import time
from collections import defaultdict

from ml.detector import ScamDetector
from voice.voice_fraud import analyze_transcript
from ml import llm_explainer
import check_pattern_parity

USE_LLM = "--no-llm" not in sys.argv

with open("rakshak_eval_testset.json", encoding="utf-8") as f:
    DATA = json.load(f)

CASES = DATA["cases"]
DETECTOR = ScamDetector()


def run():
    results = []
    t0 = time.time()
    for c in CASES:
        r = analyze_transcript(c["text"], DETECTOR)

        # Snapshot the decision BEFORE the explainer runs.
        pred_level = r["risk_level"]
        pred_score = r["score"]
        pred_rule_categories = list(r["rule_categories"])
        pred_scam = pred_level in ("SUSPICIOUS", "FRAUD")

        llm_explanation = None
        if USE_LLM:
            llm_explainer.apply(r, c["text"])
            llm_explanation = r.get("llm_explanation")
            # Hard assertion, every case, every run: the explainer must never
            # have touched the decision fields.
            assert r["risk_level"] == pred_level, (
                f"[{c['id']}] risk_level changed by LLM explainer: "
                f"{pred_level!r} -> {r['risk_level']!r}"
            )
            assert r["score"] == pred_score, (
                f"[{c['id']}] score changed by LLM explainer: {pred_score!r} -> {r['score']!r}"
            )
            assert list(r["rule_categories"]) == pred_rule_categories, (
                f"[{c['id']}] rule_categories changed by LLM explainer"
            )

        results.append({
            **c,
            "pred_level": pred_level,
            "pred_scam": pred_scam,
            "actual_scam": c["label"] == "scam",
            "llm_explanation": llm_explanation,
        })
    elapsed = time.time() - t0

    cat_stats = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0, "tn": 0})
    for r in results:
        s = cat_stats[r["category"]]
        if r["actual_scam"]:
            s["tp" if r["pred_scam"] else "fn"] += 1
        else:
            s["fp" if r["pred_scam"] else "tn"] += 1

    print(f"Mode: {'WITH LLM explanation layer' if USE_LLM else 'BASELINE (classifier + rules only)'}")
    print(f"Total wall time: {elapsed:.1f}s across {len(CASES)} cases")
    if USE_LLM:
        print("Decision-field assertions: PASSED for all cases (risk_level/score/rule_categories unchanged by LLM explainer)")
    print()

    for cat, s in sorted(cat_stats.items()):
        n_scam, n_safe = s["tp"] + s["fn"], s["fp"] + s["tn"]
        recall = f"{s['tp']/n_scam:.2f}" if n_scam else "n/a"
        fpr = f"{s['fp']/n_safe:.2f}" if n_safe else "n/a"
        print(f"  {cat:22s} n_scam={n_scam:2d} n_safe={n_safe:2d} recall={recall:>5s} FPR={fpr:>5s}")

    fp_bait = [r for r in results if r["category"] == "false_positive_bait"]
    fp_count = sum(1 for r in fp_bait if r["pred_scam"])
    print(f"\nfalse_positive_bait FPR: {fp_count}/{len(fp_bait)} = {fp_count/len(fp_bait):.3f}")

    misses = [r for r in results if r["actual_scam"] and not r["pred_scam"]]
    if misses:
        print("\nMissed scams (false negatives):")
        for r in misses:
            print(f"  [{r['id']}] {r['category']}: {r['text'][:80]}")
    else:
        print("\nNo missed scams (0 false negatives).")

    false_positives = [r for r in results if not r["actual_scam"] and r["pred_scam"]]
    if false_positives:
        print("\nFalse positives:")
        for r in false_positives:
            print(f"  [{r['id']}] pred={r['pred_level']}  {r['text'][:80]}")
    else:
        print("No false positives.")

    if USE_LLM:
        invoked = [r for r in results if r["llm_explanation"] and r["llm_explanation"]["used"]]
        if invoked:
            latencies = sorted(r["llm_explanation"]["latency_ms"] for r in invoked)
            n = len(latencies)
            p50 = latencies[n // 2]
            p95 = latencies[min(n - 1, int(n * 0.95))]
            print(f"\nLLM explanation generated for {len(invoked)}/{len(CASES)} cases "
                  f"(SUSPICIOUS/FRAUD verdicts only).")
            print(f"  latency ms: min={latencies[0]} p50={p50} p95={p95} max={latencies[-1]}")
            engine_counts = defaultdict(int)
            for r in invoked:
                engine_counts[r["llm_explanation"]["engine"]] += 1
            print(f"  engine breakdown: {dict(engine_counts)}")
        skipped_or_failed = [r for r in results if r["llm_explanation"] and not r["llm_explanation"]["used"]]
        failed = [r for r in skipped_or_failed if r["llm_explanation"]["error"]]
        if failed:
            print(f"  {len(failed)} LLM call(s) failed/timed out and kept the rule-based reason text:")
            for r in failed:
                print(f"    [{r['id']}] error={r['llm_explanation']['error']}")

    return results


if __name__ == "__main__":
    parity_ok, parity_report = check_pattern_parity.check()
    print(parity_report)
    if not parity_ok:
        print("\nAborting eval run: fix the Kotlin/Python pattern drift above before trusting these results.")
        sys.exit(1)
    print()
    run()
