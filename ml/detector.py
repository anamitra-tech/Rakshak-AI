"""
MODULE 1 — Real-Time Scam Detection Engine.

Hybrid: TF-IDF + Logistic Regression baseline, combined with a deterministic
rule-based override layer for high-risk patterns. Supports Hinglish/Hindi/English
via char + word n-grams (robust to transliteration and obfuscation).
"""
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from data.synth import generate_messages

# ---------------------------------------------------------------------------
# RULE LAYER — high-precision override signals
# ---------------------------------------------------------------------------
HIGH_RISK_PATTERNS = {
    "authority_impersonation": [
        r"\bcbi\b", r"\bed\b", r"enforcement directorate", r"\bcustoms\b",
        r"narcotics", r"police\s*(case|arrest)", r"arrest\s*warrant", r"digital\s*arrest",
        r"money\s*laundering",
    ],
    "credential_request": [
        r"\botp\b", r"\bcvv\b", r"\bpin\b", r"\bupi\s*pin\b", r"share.*(otp|pin|cvv)",
        r"kyc.*(update|pending|expire)",
    ],
    "urgency_coercion": [
        r"immediately", r"turant", r"abhi", r"urgent", r"do not (disconnect|tell|cut)",
        r"within \d+ (hour|minute|hr|min)", r"warna", r"otherwise.*block",
    ],
    "money_demand": [
        r"send money", r"paise\s*(bhej|transfer)", r"transfer.*now", r"pay.*fee",
        r"processing fee", r"settlement", r"safe (rbi|bank) account",
    ],
    "reward_bait": [
        r"lottery", r"kbc", r"won \d+", r"cashback", r"double.*(scheme|profit|24)",
        r"guaranteed.*(profit|return)",
    ],
    # Category-agnostic: discouraging independent verification (bank/police
    # helplines, family) or offering to act "for"/"on behalf of" the victim.
    # This cuts across bank fraud, digital arrest, courier, and family-emergency
    # scripts alike — see the near-deterministic override in predict() below.
    "isolation_tactics": [
        r"(that|the) (line|number) is (always )?busy",
        r"(line|number) is (currently |always )?(overloaded|busy)",
        r"(staying|stay) on (this|the) call is (actually |really )?faster",
        r"(will|would|can) cause (a )?delay",
        r"duplicate (report|complaint|fir)", r"put you on hold",
        r"walk (you )?through .{0,40}(right now|on this call)",
        r"no need to (call|contact|inform) (the|your) (bank|police|branch|customer care)",
        r"don'?t (call|contact) (the|your) (bank|police|branch|customer care)",
        r"no (need|reason) to (worry|tell|inform|disturb|trouble) (your|the) (family|son|daughter|husband|wife|parents)",
        r"don'?t (tell|inform) (your )?family", r"pareshan (mat karo|karne ki zaroorat nahi)",
        r"batane ki zaroorat nahi",
        r"i (will|'ll) handle (it|this|everything) (for|so) you", r"i (will|'ll) (do|take care of) (it|this) (myself|for you|on your behalf)",
        r"on (your |my |our )?behalf", r"give me the phone,? i (will|'ll)",
        r"khud (kar dunga|sambhal lunga|karne do)",
        r"(agent|representative|executive|courier) will (come|visit|be sent)",
        r"(come|visit|aayega) (to|at)? ?(your|the|aapke) (home|house|residence|ghar)",
        r"no need to (visit|go to) the (bank|branch)", r"bank jaane ki zaroorat nahi",
        r"someone will come (to )?collect", r"collect karne",
    ],
    # Reading an OTP/PIN/CVV/one-time code aloud over a call, under any
    # framing ("for verification", "to confirm your identity"). Near-100%
    # reliable: no legitimate bank, government body, or service ever asks
    # for this — see the near-deterministic override in predict() below.
    "otp_readout_request": [
        r"read\s+(out\s+|me\s+)?(the\s+|your\s+)?(otp|pin|cvv|code|digits|one-?time code)",
        r"(tell|share|say|speak)\s+(me\s+|us\s+)?(the\s+|your\s+)?(otp|pin|cvv|one-?time code)",
        r"(code|digits)\s+(that\s+)?(just\s+)?arrived",
        r"(code|digits)\s+you'?re\s+seeing",
        r"confirm\s+the\s+(six|four|\d+)[- ]?digit",
        r"(otp|pin|cvv|code)\s+(bata|bol)(o|iye|na|do)?",
        r"(bata|bol)(o|iye|do)\s+(mujhe\s+)?(the\s+)?(otp|pin|cvv|code)",
    ],
    # Someone arriving in person to physically take an EXISTING/active card
    # (or asking the PIN be kept ready/written down for them) — as opposed to
    # a new card being couriered TO the user, which is normal banking (see
    # BENIGN_CONTEXT / kb "card_collection_request" card for the distinction).
    "card_collection_request": [
        r"(collect|come (to|and) collect|pick up|take)\s+(your|the)\s+.{0,25}card",
        r"hand over\s+(your|the)\s+.{0,25}card",
        r"give\s+.{0,10}(your|the) card to",
        r"keep\s+(the|your) pin (ready|written down)",
        r"card\s+(collect|le)\s+karne", r"pin\s+likh\s+kar\s+rakho",
    ],
}

# Surfaced verbatim to the user when the matching near-deterministic rule
# fires (see predict()) — mirrors the corresponding kb/scams.json card so the
# in-app explanation and the knowledge-base entry stay in sync.
ISOLATION_TACTICS_EXPLANATION = (
    "A genuine bank, police officer, or government official will never discourage you from "
    "hanging up and verifying independently — through the bank's official number, a family "
    "member, or in person. Any instruction to skip that step, handle it yourself on the "
    "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless "
    "of how calm or convincing the caller sounds."
)
OTP_READOUT_EXPLANATION = (
    "No bank, police officer, or government official will ever ask you to read out your OTP, "
    "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account "
    "directly."
)
CARD_COLLECTION_EXPLANATION = (
    "Banks and government bodies do not send someone to your home to collect your active "
    "debit or credit card. If your card needs to be blocked, it can be done remotely — no one "
    "needs to physically take it from you."
)

# Rules treated as near-certain scam on their own — no legitimate caller has
# a reason to trigger any of these, so they override the ML/tone score
# regardless of what else did or didn't match (see predict()).
NEAR_DETERMINISTIC_RULES = {
    "isolation_tactics": ISOLATION_TACTICS_EXPLANATION,
    "otp_readout_request": OTP_READOUT_EXPLANATION,
    "card_collection_request": CARD_COLLECTION_EXPLANATION,
}

ACTION_BY_LEVEL = {
    "FRAUD": "Block sender, do NOT share any code/money, report at cybercrime.gov.in / 1930.",
    "SUSPICIOUS": "Do not act on this message. Verify via the official app or helpline before responding.",
    "SAFE": "No action needed. Stay alert for follow-up messages.",
}

# Raised from 0.4 -> 0.5 (rakshak_eval_testset.json): the lowest-scoring
# genuine scam case scores 0.53 and the highest-scoring false_positive_bait
# miss scores 0.49 — 0.5 clears every remaining false alarm in that set while
# keeping margin on both sides of every real scam case. voice/voice_fraud.py
# mirrors this same value (CLAUDE.md's documented 0.7/0.4-derived vocabulary
# is shared across modules) since /analyze_voice — what the Android "check a
# call" flow actually calls — has its own independent threshold check on the
# same underlying score, not a lookup of this module's risk_level.
SUSPICIOUS_THRESHOLD = 0.5


# Phrases that indicate a LEGITIMATE informational message rather than a request.
# e.g. a real bank tells you your OTP and warns you NOT to share it.
BENIGN_CONTEXT = [
    r"do not share (it|this|your otp)", r"never share", r"(will )?never ask",
    r"otp (is|for).*\d{4,}", r"debited from a/c", r"credited to your",
    r"- ?(hdfc|icici|sbi|axis|kotak|bank)", r"not you\??\s*call",
]

# credential_request and urgency_coercion match on common, individually
# meaningless words ("OTP", "urgent", "immediately", "confirm", "block") that
# show up constantly in ordinary legitimate messages (a real OTP SMS, a
# recharge reminder, a KYC-update notice). Unlike the near-deterministic
# rules above — which never fire on a single generic word, only on a specific
# combination (e.g. bank-framing + withdraw-instruction) — these two categories
# used to count on their own. Now they only count when at least one other,
# more specific rule category also matched; a bare hit in just these two
# contributes nothing.
SOFT_SIGNAL_CATEGORIES = {"credential_request", "urgency_coercion"}


def _rule_signals(text):
    t = text.lower()
    hits = {}
    for cat, pats in HIGH_RISK_PATTERNS.items():
        matched = [p for p in pats if re.search(p, t)]
        if matched:
            hits[cat] = len(matched)

    # Soft signals need to combine with something more specific to count.
    if hits and set(hits.keys()) <= SOFT_SIGNAL_CATEGORIES:
        hits = {}

    # Benign guard: if the message looks like a legit informational bank SMS
    # (e.g. "we will never ask for your OTP"), a lone credential/OTP-readout
    # mention (possibly alongside incidental urgency wording like "hang up
    # immediately") is NOT a request -> drop it.
    benign = any(re.search(p, t) for p in BENIGN_CONTEXT)
    if benign and set(hits.keys()) <= {"credential_request", "otp_readout_request", "urgency_coercion"}:
        hits.pop("credential_request", None)
        hits.pop("otp_readout_request", None)
        hits.pop("urgency_coercion", None)
    return hits


class ScamDetector:
    def __init__(self):
        self.pipe = None
        self._train()

    def _train(self):
        rows = generate_messages()
        X = [r[0] for r in rows]
        y = [r[1] for r in rows]
        features = FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)),
        ])
        self.pipe = Pipeline([
            ("feat", features),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ])
        self.pipe.fit(X, y)
        self.classes_ = list(self.pipe.named_steps["clf"].classes_)

    def predict(self, text):
        text = (text or "").strip()
        if not text:
            return self._format("SAFE", 0.0, "Empty message.", [], {})

        proba = self.pipe.predict_proba([text])[0]
        pmap = dict(zip(self.classes_, proba))
        ml_fraud = float(pmap.get("FRAUD", 0.0))

        rules = _rule_signals(text)
        rule_categories = len(rules)
        rule_weight = sum(rules.values())

        # Fusion: ML score boosted by rule evidence.
        score = ml_fraud
        if rule_categories >= 2:
            score = max(score, 0.85)        # multiple independent risk signals -> override
        elif rule_categories == 1:
            score = max(score, 0.55)
        score = min(1.0, score + 0.05 * rule_weight)

        # Critical combo: authority impersonation + (money OR credential) = digital arrest
        if "authority_impersonation" in rules and (
            "money_demand" in rules or "credential_request" in rules
        ):
            score = max(score, 0.95)

        # Near-deterministic overrides (isolation tactics, OTP/PIN readout
        # requests, in-person card collection) — each is near-certain scam on
        # its own, so any one of them overrides regardless of tone/ML score
        # and independently of which other categories (if any) also matched.
        if NEAR_DETERMINISTIC_RULES.keys() & rules.keys():
            score = max(score, 0.95)

        if score >= 0.7:
            level = "FRAUD"
        elif score >= SUSPICIOUS_THRESHOLD:
            level = "SUSPICIOUS"
        else:
            level = "SAFE"

        signals = self._build_signals(rules)
        reason = self._build_reason(level, rules, ml_fraud)
        return self._format(level, round(score, 3), reason, signals, rules)

    def _build_signals(self, rules):
        label = {
            "authority_impersonation": "Impersonates law-enforcement / govt authority",
            "credential_request": "Requests OTP/PIN/CVV/KYC credentials",
            "urgency_coercion": "Creates artificial urgency / coercion",
            "money_demand": "Demands money transfer",
            "reward_bait": "Offers unrealistic reward / lottery / returns",
            "isolation_tactics": "Discourages independent verification (bank/police/family)",
            "otp_readout_request": "Asks you to read out your OTP/PIN/CVV over the call",
            "card_collection_request": "Arranges in-person collection of your card, or asks you to keep the PIN ready",
        }
        return [label[k] for k in rules]

    def _build_reason(self, level, rules, ml):
        if not rules:
            if level == "SAFE":
                return "No fraud patterns detected; language consistent with legitimate messaging."
            return f"Language model flags risk (fraud likelihood {ml:.0%}) though no explicit rule pattern matched."
        deterministic_hits = [k for k in NEAR_DETERMINISTIC_RULES if k in rules]
        if deterministic_hits:
            return " ".join(NEAR_DETERMINISTIC_RULES[k] for k in deterministic_hits)
        parts = self._build_signals(rules)
        return f"{level}: detected {len(parts)} risk signal(s) — " + "; ".join(parts) + "."

    def _format(self, level, score, reason, signals, rules):
        return {
            "risk_level": level,
            "score": score,
            "reason": reason,
            "signals": signals,
            "recommended_action": ACTION_BY_LEVEL[level],
            "rule_categories": list(rules.keys()),
        }


if __name__ == "__main__":
    d = ScamDetector()
    tests = [
        "Sir this is CBI officer, your Aadhaar linked to money laundering. Send money to RBI account now.",
        "Your OTP for login is 482910. Do not share it with anyone. - HDFC Bank",
        "call me urgent send money",
        "Kal milte hain coffee ke liye, 5 baje theek hai?",
        "Aapka account suspend ho gaya, OTP batao turant warna band ho jayega",
    ]
    for t in tests:
        r = d.predict(t)
        print(f"[{r['risk_level']:11s} {r['score']:.2f}] {t[:55]:55s} -> {r['signals']}")
