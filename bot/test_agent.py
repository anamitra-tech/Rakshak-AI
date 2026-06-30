import sys
sys.stdout.reconfigure(encoding="utf-8")

from bot.agent import chat

SESSION = "farmer_001"

MESSAGES = [
    "Hello",
    "What do you do?",
    "CBI ne call kiya arrest warrant hai mere naam pe",
    "Good morning",
    "Phir se CBI ka call aaya alag number se",
    "Ek aur call aaya lottery ka — KBC mein jeeta hai",
    "Maine woh zip file khol di jo HR ne bheji thi",
]

DIVIDER = "─" * 45

for i, msg in enumerate(MESSAGES, 1):
    r = chat(SESSION, msg)
    conf = f"{r['confidence']:.2f}" if r.get("confidence") is not None else "None"
    scam = r.get("scam_type") or "None"
    severity = r.get("severity", "")

    header = (
        f"Turn {i} | Intent: {r.get('intent', '?')} | "
        f"Engine: {r.get('engine')} | "
        f"Scam: {scam} | "
        f"Confidence: {conf} | "
        f"History: {r['history_length']} msgs"
    )
    if severity:
        header += f" | Severity: {severity}"

    print(header)
    print(r["answer"])
    print(DIVIDER)

# ── Profile detection tests ───────────────────────────────────────────────────

PROFILE_TESTS = [
    (
        "profile_test",
        "Mere dadaji ko ek call aaya CBI ka, paise maang rahe the",
    ),
    (
        "profile_test_2",
        "Kisan credit card ke liye ek call aaya, OTP maang raha tha bank wala",
    ),
    (
        "profile_test_3",
        "I got a call from someone claiming to be from CBI",
    ),
]

for i, (sess_id, msg) in enumerate(PROFILE_TESTS, 8):
    r = chat(sess_id, msg)
    profile = r.get("profile", "default")
    scam = r.get("scam_type") or "None"
    word_count = len(r["answer"].split())

    print(
        f"Turn {i} | Profile: {profile} | Scam: {scam} | "
        f"Words in answer: {word_count}"
    )
    print(r["answer"])
    print(DIVIDER)

# ── Pushback gate test ────────────────────────────────────────────────────────

chat("pushback_test", "CBI ne call kiya arrest warrant hai")
r = chat("pushback_test", "But they say they are real don't worry")
engine = r.get("engine", "?")
word_count = len(r["answer"].split())
print(
    f"Turn 11 | Engine: {engine} | "
    f"Words in answer: {word_count}"
)
print(r["answer"])
print(DIVIDER)
assert engine == "pushback_gate", f"Expected pushback_gate, got {engine}"
assert "1930" in r["answer"], "Answer must contain 1930"
print("Turn 11 PASS")

# ── In-person verification lure test ─────────────────────────────────────────

r12 = chat("building_test", "They said come to this building floor 3, is it safe to go?")
engine12 = r12.get("engine", "?")
word_count12 = len(r12["answer"].split())
print(
    f"Turn 12 | Engine: {engine12} | "
    f"Scam: {r12.get('scam_type') or 'None'} | "
    f"Words in answer: {word_count12}"
)
print(r12["answer"])
print(DIVIDER)
assert "Do not travel" in r12["answer"], "Turn 12: 'Do not travel' not in answer"
assert "1930" in r12["answer"], "Turn 12: '1930' not in answer"
print("Turn 12 PASS")
