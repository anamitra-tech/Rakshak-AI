"""
Fails loudly if ml/detector.py's HIGH_RISK_PATTERNS for isolation_tactics /
otp_readout_request / card_collection_request / malware_attachment_delivery
drift from their Kotlin mirror in
android/app/src/main/java/com/rakshak/ai/intelligence/OfflineRuleEngine.kt.

The first three are NEAR_DETERMINISTIC_RULES (see ml/detector.py); the
fourth, malware_attachment_delivery (added 2026-07-12), is an explicit
exception ported for the same reason — see OfflineRuleEngine.kt's module doc
comment for why it's treated as deterministic-alone despite not being in
NEAR_DETERMINISTIC_RULES. These four are the only categories
OfflineRuleEngine.kt ports for the Prahari-unreachable offline fallback. The
two files are hand-maintained copies with no shared source of truth, so
nothing stops them from silently diverging except this check.

Reads Python's pattern lists directly out of the live ml.detector module.
Reads Kotlin's pattern lists by compiling the real OfflineRuleEngine.kt
against a small reflection-based dumper (never modifies the source file) and
running it on the JVM, so this compares actual compiled regex strings, not a
hand-transcribed copy of either side.

Requires a JDK + the Kotlin compiler (kotlin-compiler-embeddable and its
runtime deps) to compile the Kotlin side. Looks for a toolchain, in order:
  1. $RAKSHAK_ANDROID_TOOLCHAIN (a directory laid out like the one below)
  2. D:\\rakshak-android-toolchain (this project's known dev toolchain)
If no toolchain is found, this is reported as a distinct failure ("COULD NOT
VERIFY") rather than a silent pass or a false "DRIFT DETECTED" - the check
must never report parity when it didn't actually check.

Usage:
  python check_pattern_parity.py     # standalone, e.g. before any commit
                                      # touching either file
Also invoked automatically at the top of eval_testset.py.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
KOTLIN_FILE = os.path.join(
    REPO_ROOT, "android", "app", "src", "main", "java",
    "com", "rakshak", "ai", "intelligence", "OfflineRuleEngine.kt",
)
CATEGORIES = [
    "isolation_tactics", "otp_readout_request", "card_collection_request",
    "malware_attachment_delivery",
]
FIELD_NAMES = {
    "isolation_tactics": "ISOLATION_TACTICS_PATTERNS",
    "otp_readout_request": "OTP_READOUT_PATTERNS",
    "card_collection_request": "CARD_COLLECTION_PATTERNS",
    "malware_attachment_delivery": "MALWARE_ATTACHMENT_PATTERNS",
}

DUMPER_SOURCE = """
import com.rakshak.ai.intelligence.OfflineRuleEngine
import java.io.File

@Suppress("UNCHECKED_CAST")
fun main() {
    val klass = OfflineRuleEngine::class.java
    val fields = listOf(
        "isolation_tactics" to "ISOLATION_TACTICS_PATTERNS",
        "otp_readout_request" to "OTP_READOUT_PATTERNS",
        "card_collection_request" to "CARD_COLLECTION_PATTERNS",
        "malware_attachment_delivery" to "MALWARE_ATTACHMENT_PATTERNS",
    )

    fun jsonEscape(s: String): String {
        val out = StringBuilder()
        for (c in s) {
            when (c) {
                '\\\\' -> out.append("\\\\\\\\")
                '"' -> out.append("\\\\\\"")
                '\\n' -> out.append("\\\\n")
                '\\r' -> out.append("\\\\r")
                '\\t' -> out.append("\\\\t")
                else -> if (c.code < 0x20) out.append("\\\\u%04x".format(c.code)) else out.append(c)
            }
        }
        return out.toString()
    }

    val sb = StringBuilder("{\\n")
    for ((idx, pair) in fields.withIndex()) {
        val (jsonKey, fieldName) = pair
        val f = klass.getDeclaredField(fieldName)
        f.isAccessible = true
        val list = f.get(null) as List<Regex>
        sb.append("  \\"").append(jsonKey).append("\\": [\\n")
        for ((j, regex) in list.withIndex()) {
            sb.append("    \\"").append(jsonEscape(regex.pattern)).append("\\"")
            if (j != list.size - 1) sb.append(",")
            sb.append("\\n")
        }
        sb.append("  ]")
        if (idx != fields.size - 1) sb.append(",")
        sb.append("\\n")
    }
    sb.append("}\\n")
    File("kotlin_patterns.json").writeText(sb.toString(), Charsets.UTF_8)
}
"""


class ToolchainNotFound(Exception):
    pass


def _find_toolchain_root():
    candidates = []
    env_root = os.environ.get("RAKSHAK_ANDROID_TOOLCHAIN")
    if env_root:
        candidates.append(env_root)
    candidates.append(r"D:\rakshak-android-toolchain")
    for c in candidates:
        if os.path.isdir(c):
            return c
    raise ToolchainNotFound(
        "No Kotlin/JDK toolchain found. Checked: "
        + ", ".join(candidates)
        + ". Set RAKSHAK_ANDROID_TOOLCHAIN to a directory containing jdk/ "
        "and gradle-home/, or ensure the known dev toolchain path exists."
    )


def _find_jar(gradle_home, group, artifact):
    pattern = os.path.join(
        gradle_home, "caches", "modules-2", "files-2.1", group, artifact,
        "*", "*", f"{artifact}-*.jar",
    )
    matches = [m for m in glob.glob(pattern) if not m.endswith("-sources.jar")]
    if not matches:
        raise ToolchainNotFound(f"Could not find {group}:{artifact} jar under {gradle_home}")
    return matches[0]


def _find_java_bin(root):
    candidate_homes = []
    if os.environ.get("JAVA_HOME"):
        candidate_homes.append(os.environ["JAVA_HOME"])
    candidate_homes.append(os.path.join(root, "jdk"))
    candidate_homes.extend(sorted(glob.glob(os.path.join(root, "jdk_extract", "jdk-*"))))

    for home in candidate_homes:
        for name in ("java.exe", "java"):
            candidate = os.path.join(home, "bin", name)
            if os.path.isfile(candidate):
                return candidate

    import shutil
    which = shutil.which("java")
    if which:
        return which

    raise ToolchainNotFound(
        f"No java executable found. Checked JAVA_HOME, {root}/jdk, "
        f"{root}/jdk_extract/jdk-*, and PATH."
    )


def _locate_toolchain():
    root = _find_toolchain_root()
    java_bin = _find_java_bin(root)

    gradle_home = os.environ.get("GRADLE_USER_HOME") or os.path.join(root, "gradle-home")
    if not os.path.isdir(gradle_home):
        raise ToolchainNotFound(f"No gradle-home found at {gradle_home}")

    jars = {
        "compiler": _find_jar(gradle_home, "org.jetbrains.kotlin", "kotlin-compiler-embeddable"),
        "stdlib": _find_jar(gradle_home, "org.jetbrains.kotlin", "kotlin-stdlib"),
        "script_rt": _find_jar(gradle_home, "org.jetbrains.kotlin", "kotlin-script-runtime"),
        "daemon": _find_jar(gradle_home, "org.jetbrains.kotlin", "kotlin-daemon-embeddable"),
        "annotations": _find_jar(gradle_home, "org.jetbrains", "annotations"),
        "trove4j": _find_jar(gradle_home, "org.jetbrains.intellij.deps", "trove4j"),
    }
    return java_bin, jars


def _get_python_patterns():
    from ml.detector import HIGH_RISK_PATTERNS
    return {cat: list(HIGH_RISK_PATTERNS[cat]) for cat in CATEGORIES}


def _get_kotlin_patterns():
    """Compiles the real OfflineRuleEngine.kt (untouched) plus a throwaway
    reflection-based dumper, runs it on the JVM, and parses the result.
    Raises ToolchainNotFound if no usable Kotlin/JDK toolchain exists;
    raises RuntimeError if the toolchain exists but compilation/execution
    itself fails (a real problem, not silently swallowed either way)."""
    if not os.path.isfile(KOTLIN_FILE):
        raise RuntimeError(f"Kotlin source not found: {KOTLIN_FILE}")

    java_bin, jars = _locate_toolchain()
    runtime_cp = os.pathsep.join([
        jars["compiler"], jars["stdlib"], jars["script_rt"],
        jars["daemon"], jars["annotations"], jars["trove4j"],
    ])

    with tempfile.TemporaryDirectory(prefix="rakshak_pattern_parity_") as tmp:
        with open(KOTLIN_FILE, encoding="utf-8") as f:
            kotlin_source = f.read()
        with open(os.path.join(tmp, "OfflineRuleEngine.kt"), "w", encoding="utf-8") as f:
            f.write(kotlin_source)
        with open(os.path.join(tmp, "Dumper.kt"), "w", encoding="utf-8") as f:
            f.write(DUMPER_SOURCE)

        classes_dir = os.path.join(tmp, "classes")
        os.makedirs(classes_dir, exist_ok=True)

        compile_cmd = [
            java_bin, "-cp", runtime_cp,
            "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler",
            "-no-reflect", "-classpath", jars["stdlib"],
            "-d", classes_dir,
            os.path.join(tmp, "OfflineRuleEngine.kt"),
            os.path.join(tmp, "Dumper.kt"),
        ]
        result = subprocess.run(compile_cmd, cwd=tmp, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                "Kotlin compilation of OfflineRuleEngine.kt failed:\n"
                f"{result.stdout}\n{result.stderr}"
            )

        run_cp = os.pathsep.join([classes_dir, jars["stdlib"]])
        run_cmd = [java_bin, "-Dfile.encoding=UTF-8", "-cp", run_cp, "DumperKt"]
        result = subprocess.run(run_cmd, cwd=tmp, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(
                "Running the Kotlin pattern dumper failed:\n"
                f"{result.stdout}\n{result.stderr}"
            )

        out_path = os.path.join(tmp, "kotlin_patterns.json")
        if not os.path.isfile(out_path):
            raise RuntimeError("Kotlin dumper ran but produced no output file")
        with open(out_path, encoding="utf-8") as f:
            patterns = json.load(f)

    return {cat: patterns.get(cat, []) for cat in CATEGORIES}


def check():
    """Returns (ok: bool, report: str)."""
    lines = []
    try:
        py_patterns = _get_python_patterns()
    except Exception as e:
        return False, f"COULD NOT VERIFY: failed to read Python patterns from ml/detector.py: {e}"

    try:
        kt_patterns = _get_kotlin_patterns()
    except ToolchainNotFound as e:
        return False, (
            "COULD NOT VERIFY (not the same as passing): no Kotlin/JDK toolchain "
            f"available to compile OfflineRuleEngine.kt for comparison.\n{e}"
        )
    except RuntimeError as e:
        return False, f"COULD NOT VERIFY: {e}"

    ok = True
    for cat in CATEGORIES:
        p = py_patterns.get(cat, [])
        k = kt_patterns.get(cat, [])
        if len(p) != len(k):
            ok = False
            lines.append(
                f"[{cat}] COUNT MISMATCH: ml/detector.py has {len(p)} patterns, "
                f"OfflineRuleEngine.kt has {len(k)}"
            )
            continue
        for i, (a, b) in enumerate(zip(p, k)):
            if a != b:
                ok = False
                lines.append(f"[{cat}] pattern #{i} differs:")
                lines.append(f"    python : {a!r}")
                lines.append(f"    kotlin : {b!r}")

    if ok:
        total = sum(len(py_patterns[c]) for c in CATEGORIES)
        return True, (
            f"Pattern parity OK: all {total} patterns across "
            f"{', '.join(CATEGORIES)} are identical between "
            "ml/detector.py and OfflineRuleEngine.kt."
        )
    return False, (
        "PATTERN DRIFT DETECTED between ml/detector.py's HIGH_RISK_PATTERNS "
        "and android/.../OfflineRuleEngine.kt:\n\n" + "\n".join(lines) + "\n\n"
        "These four categories are near-deterministic-alone rules the offline "
        "fallback relies on being an exact mirror of the online path (see both "
        "files' module docs). Fix the drift before committing."
    )


def main():
    ok, report = check()
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
