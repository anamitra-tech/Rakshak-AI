"""
Fails loudly if MlScamScorer.kt (the Kotlin reimplementation of
ml.detector.ScamDetector's trained TF-IDF + LogisticRegression pipeline) no
longer agrees with the real Python model -- e.g. because ml/detector.py's
ScamDetector was retrained/retuned (different vectorizer settings, more
training data, a different min_df) and android/app/src/main/assets/
scam_model.txt was never re-exported via `python -m ml.export_offline_model`.

This is the ML-score analogue of check_pattern_parity.py: same idea (compile
the real Kotlin file, run it, diff against Python's ground truth, fail
loudly with the exact mismatches rather than a summary), applied to the
continuous P(FRAUD) score instead of the three discrete regex categories.

Compares, for every rakshak_eval_testset.json case: the real
pipe.predict_proba(text) P(FRAUD) vs. MlScamScorer.scoreFraudProbability()
run against the CURRENTLY-committed scam_model.txt asset. Tolerance 0.01,
same as ml/check_offline_ml_scorer.py's one-off validation harness this
reuses the same comparison logic from.

Usage:
  python check_ml_scorer_parity.py     # standalone, e.g. before any commit
                                        # touching ml/detector.py, the export
                                        # script, scam_model.txt, or
                                        # MlScamScorer.kt
"""
import os
import subprocess
import sys
import tempfile

from check_pattern_parity import ToolchainNotFound, _locate_toolchain

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
KOTLIN_FILE = os.path.join(
    REPO_ROOT, "android", "app", "src", "main", "java",
    "com", "rakshak", "ai", "intelligence", "MlScamScorer.kt",
)
MODEL_ASSET_PATH = os.path.join(
    REPO_ROOT, "android", "app", "src", "main", "assets", "scam_model.txt"
)
TESTSET_PATH = os.path.join(REPO_ROOT, "rakshak_eval_testset.json")
TOLERANCE = 0.01

KOTLIN_HARNESS_SOURCE = """
import com.rakshak.ai.intelligence.MlScamScorer
import java.io.File

fun main() {
    val model = MlScamScorer.parseModel(File("scam_model.txt").readText(Charsets.UTF_8))
    val out = StringBuilder()
    File("input.tsv").forEachLine { line ->
        if (line.isBlank()) return@forEachLine
        val tabIdx = line.indexOf('\\t')
        val id = line.substring(0, tabIdx)
        val text = line.substring(tabIdx + 1)
        val pFraud = MlScamScorer.scoreFraudProbability(model, text)
        out.append(id).append('\\t').append(pFraud).append('\\n')
    }
    File("output.tsv").writeText(out.toString(), Charsets.UTF_8)
}
"""


def _get_python_ground_truth():
    import json
    from ml.detector import ScamDetector

    with open(TESTSET_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    detector = ScamDetector()
    pipe = detector.pipe
    classes = list(pipe.named_steps["clf"].classes_)
    fraud_idx = classes.index("FRAUD")

    ground_truth = {}
    inputs = {}
    for c in cases:
        proba = pipe.predict_proba([c["text"]])[0]
        ground_truth[c["id"]] = float(proba[fraud_idx])
        inputs[c["id"]] = c["text"]
    return ground_truth, inputs


def _get_kotlin_scores(inputs):
    if not os.path.isfile(KOTLIN_FILE):
        raise RuntimeError(f"Kotlin source not found: {KOTLIN_FILE}")
    if not os.path.isfile(MODEL_ASSET_PATH):
        raise RuntimeError(f"Model asset not found: {MODEL_ASSET_PATH}")

    java_bin, jars = _locate_toolchain()
    runtime_cp = os.pathsep.join([
        jars["compiler"], jars["stdlib"], jars["script_rt"],
        jars["daemon"], jars["annotations"], jars["trove4j"],
    ])

    with tempfile.TemporaryDirectory(prefix="rakshak_ml_parity_") as tmp:
        with open(KOTLIN_FILE, encoding="utf-8") as f:
            kotlin_source = f.read()
        with open(os.path.join(tmp, "MlScamScorer.kt"), "w", encoding="utf-8") as f:
            f.write(kotlin_source)
        with open(os.path.join(tmp, "Harness.kt"), "w", encoding="utf-8") as f:
            f.write(KOTLIN_HARNESS_SOURCE)
        with open(MODEL_ASSET_PATH, encoding="utf-8") as f:
            model_text = f.read()
        with open(os.path.join(tmp, "scam_model.txt"), "w", encoding="utf-8") as f:
            f.write(model_text)
        with open(os.path.join(tmp, "input.tsv"), "w", encoding="utf-8") as f:
            for cid, text in inputs.items():
                f.write(f"{cid}\t{text}\n")

        classes_dir = os.path.join(tmp, "classes")
        os.makedirs(classes_dir, exist_ok=True)

        compile_cmd = [
            java_bin, "-cp", runtime_cp,
            "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
            "-no-reflect", "-classpath", jars["stdlib"],
            "-d", classes_dir,
            os.path.join(tmp, "MlScamScorer.kt"),
            os.path.join(tmp, "Harness.kt"),
        ]
        result = subprocess.run(compile_cmd, cwd=tmp, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"Kotlin compilation of MlScamScorer.kt failed:\n{result.stdout}\n{result.stderr}"
            )

        run_cp = os.pathsep.join([classes_dir, jars["stdlib"]])
        run_cmd = [java_bin, "-Dfile.encoding=UTF-8", "-cp", run_cp, "HarnessKt"]
        result = subprocess.run(run_cmd, cwd=tmp, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"Running the Kotlin ML-scorer harness failed:\n{result.stdout}\n{result.stderr}"
            )

        out_path = os.path.join(tmp, "output.tsv")
        if not os.path.isfile(out_path):
            raise RuntimeError("Kotlin harness ran but produced no output file")
        scores = {}
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                cid, val = line.split("\t")
                scores[cid] = float(val)
        return scores


def check():
    """Returns (ok: bool, report: str)."""
    try:
        ground_truth, inputs = _get_python_ground_truth()
    except Exception as e:
        return False, f"COULD NOT VERIFY: failed to compute Python ground truth: {e}"

    try:
        kotlin_scores = _get_kotlin_scores(inputs)
    except ToolchainNotFound as e:
        return False, (
            "COULD NOT VERIFY (not the same as passing): no Kotlin/JDK toolchain "
            f"available to compile MlScamScorer.kt for comparison.\n{e}"
        )
    except RuntimeError as e:
        return False, f"COULD NOT VERIFY: {e}"

    missing = set(ground_truth) - set(kotlin_scores)
    if missing:
        return False, f"COULD NOT VERIFY: Kotlin harness produced no score for cases: {sorted(missing)}"

    mismatches = []
    for cid in sorted(ground_truth):
        py_val = ground_truth[cid]
        kt_val = kotlin_scores[cid]
        diff = abs(py_val - kt_val)
        if diff > TOLERANCE:
            mismatches.append((cid, py_val, kt_val, diff))

    if mismatches:
        lines = [
            f"[{cid}] python={py_val:.6f} kotlin={kt_val:.6f} diff={diff:.6f}"
            for cid, py_val, kt_val, diff in mismatches
        ]
        return False, (
            f"ML SCORER DRIFT DETECTED: {len(mismatches)}/{len(ground_truth)} case(s) "
            f"differ by more than {TOLERANCE} between the real Python model and "
            "MlScamScorer.kt:\n\n" + "\n".join(lines) + "\n\n"
            "This means scam_model.txt is stale relative to ml/detector.py's trained "
            "pipeline, or MlScamScorer.kt's math has drifted from what "
            "ml/export_offline_model.py exports. Re-run "
            "`python -m ml.export_offline_model` and re-check before committing."
        )

    return True, (
        f"ML scorer parity OK: all {len(ground_truth)} cases match within "
        f"tolerance {TOLERANCE} between the real Python model and MlScamScorer.kt."
    )


def main():
    ok, report = check()
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
