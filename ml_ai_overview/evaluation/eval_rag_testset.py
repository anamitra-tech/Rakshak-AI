"""
Evaluation harness for rakshak_eval_testset.json against the CONVERSATIONAL
bot.agent.chat() -> detect_intent() -> rag.retriever.retrieve_and_respond()
pipeline -- the same code path /webhook (Twilio's "WHEN A MESSAGE COMES IN")
actually runs. rag.retriever.retrieve_and_respond() now delegates its
risk_level/scam_type decision to the SAME ml.detector.ScamDetector instance
eval_testset.py measures (0% FPR / 100% recall on the phone-app pipeline) --
FAISS retrieval against kb/scams.json is used only to ground the LLM
explanation text, not to decide SCAM/SAFE.

Each case runs with a fresh, unique session_id so per-case results are
independent: chat() keys profile detection, pushback gating, and
pattern-comparison notes off session history, so reusing one session_id
across cases would let earlier cases contaminate later ones.

"predicted scam" is read off result["scam_type"] being non-None, which is now
set whenever ScamDetector.predict() returns SUSPICIOUS or FRAUD -- independent
of which LLM engine happened to write the human-readable `answer` text. A case
can land in the correct bucket even if Gemini's quota was exhausted and Groq
wrote the prose, or even if the LLM chain fails entirely and the classifier's
own reason text is used instead; this harness measures classification, not
answer quality.

Usage: python eval_rag_testset.py
"""
import json
import time
from collections import defaultdict

from bot.agent import chat

with open("rakshak_eval_testset.json", encoding="utf-8") as f:
    DATA = json.load(f)

CASES = DATA["cases"]


def run():
    results = []
    t0 = time.time()
    for i, c in enumerate(CASES):
        session_id = f"eval_{c['id']}"
        t_case = time.time()
        try:
            r = chat(session_id, c["text"])
            error = None
        except Exception as e:
            r = {}
            error = f"{type(e).__name__}: {e}"
        elapsed = time.time() - t_case

        pred_scam = (r.get("scam_type") is not None) if error is None else False
        results.append({
            **c,
            "pred_scam": pred_scam,
            "scam_type": r.get("scam_type"),
            "intent": r.get("intent"),
            "engine": r.get("engine"),
            "confidence": r.get("confidence"),
            "actual_scam": c["label"] == "scam",
            "elapsed_s": round(elapsed, 2),
            "error": error,
        })
        status = f"ERROR: {error}" if error else f"intent={r.get('intent')} scam_type={r.get('scam_type')} engine={r.get('engine')}"
        print(f"  [{i+1}/{len(CASES)}] {c['id']:6s} ({elapsed:5.1f}s) {status}")

    elapsed_total = time.time() - t0

    cat_stats = defaultdict(lambda: {"tp": 0, "fn": 0, "fp": 0, "tn": 0})
    for r in results:
        s = cat_stats[r["category"]]
        if r["actual_scam"]:
            s["tp" if r["pred_scam"] else "fn"] += 1
        else:
            s["fp" if r["pred_scam"] else "tn"] += 1

    print("\nMode: bot.agent.chat() -> detect_intent() -> RAG path (/webhook pipeline)")
    print(f"Total wall time: {elapsed_total:.1f}s across {len(CASES)} cases\n")

    for cat, s in sorted(cat_stats.items()):
        n_scam, n_safe = s["tp"] + s["fn"], s["fp"] + s["tn"]
        recall = f"{s['tp']/n_scam:.2f}" if n_scam else "n/a"
        fpr = f"{s['fp']/n_safe:.2f}" if n_safe else "n/a"
        print(f"  {cat:22s} n_scam={n_scam:2d} n_safe={n_safe:2d} recall={recall:>5s} FPR={fpr:>5s}")

    fp_bait = [r for r in results if r["category"] == "false_positive_bait"]
    fp_count = sum(1 for r in fp_bait if r["pred_scam"])
    print(f"\nfalse_positive_bait FPR: {fp_count}/{len(fp_bait)} = {fp_count/len(fp_bait):.3f}")

    errors = [r for r in results if r["error"]]
    if errors:
        print(f"\n{len(errors)} case(s) raised an unhandled exception (counted as predicted-safe/miss above):")
        for r in errors:
            print(f"  [{r['id']}] {r['error']}")

    misses = [r for r in results if r["actual_scam"] and not r["pred_scam"]]
    if misses:
        print("\nMissed scams (false negatives):")
        for r in misses:
            print(f"  [{r['id']}] {r['category']} intent={r['intent']}: {r['text'][:70]}")
    else:
        print("\nNo missed scams (0 false negatives).")

    false_positives = [r for r in results if not r["actual_scam"] and r["pred_scam"]]
    if false_positives:
        print("\nFalse positives:")
        for r in false_positives:
            conf = r["confidence"]
            conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else str(conf)
            print(f"  [{r['id']}] scam_type={r['scam_type']} confidence={conf_str} intent={r['intent']}: {r['text'][:70]}")
    else:
        print("No false positives.")

    engine_counts = defaultdict(int)
    for r in results:
        engine_counts[r["engine"]] += 1
    print(f"\nEngine/path breakdown: {dict(engine_counts)}")

    return results


if __name__ == "__main__":
    run()
