"""
MODULE 1 — Real-Time Scam Detection Engine.

Hybrid: TF-IDF + Logistic Regression baseline, combined with a deterministic
rule-based override layer for high-risk patterns. Supports Hinglish/Hindi/English
via char + word n-grams (robust to transliteration and obfuscation).

2026-09-11 multilingual/subtle-scam upgrade: this module now also (1)
translates any of the other 10 target-language native scripts to English via
Sarvam before scoring (Hindi/English/Hinglish already work directly on this
module's own patterns, so they're excluded the same way
bot.sarvam_translate.detect_native_script_lang already treats Latin script as
translation-exempt) and classifies both the original and translated text,
keeping whichever score is higher; and (2) asks an LLM for a second opinion
when the rule+ML score lands in the genuinely uncertain 0.3-0.7 band, since
neither the rules nor the small prototype classifier (see CLAUDE.md Section 6
on its training-data limits) can be trusted alone in that band. See
predict()/_score_text()/_llm_second_opinion() below.
"""
import hashlib
import json
import logging
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from bot.sarvam_translate import detect_native_script_lang, translate_text_sarvam
from data.synth import generate_messages
from rag.store import retrieve as rag_retrieve, store_exists as rag_store_exists

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 2026-09-11 THREE-TIER REDESIGN
#
# Tier 1 (deterministic rules+ML, below): resolves immediately at the
# extremes. Tier 2 online (Groq) and Tier 2 offline (semantic similarity)
# only run for the genuinely uncertain middle band. See predict() for the
# full flow and ScamDetector's other _tier2_* methods.
#
# Two components were requested by name that do not exist anywhere in this
# repo (confirmed live, not assumed): "gemma2-9b-it" -- Groq itself returns
# `model_decommissioned` for this id, verified with a real API call, not
# account-specific -- and "ChromaDB"/"nomic-embed-text" -- neither package
# is installed, in requirements.txt, or referenced anywhere in this
# codebase. The real substitutes used below: rag/store.py's FAISS index
# (built from kb/scams.json's 78 cards) + rag/embedder.py's BAAI/bge-m3
# model for the semantic tier (same substitution already made and
# disclosed for the semantic layer earlier this session), and
# GROQ_TIER2_MODEL for the LLM tier -- chosen live against this account's
# real /v1/models list (`groq/compound[-mini]` are agentic tool-
# orchestration wrappers, `canopylabs/orpheus-*` are TTS, `whisper-*` are
# ASR, `meta-llama/llama-prompt-guard-2-*` are binary jailbreak
# classifiers, `allam-2-7b` is Arabic-focused -- none of those are usable
# chat classifiers here) among the real candidates:
#   openai/gpt-oss-20b  : ~1000ms, correctly read Odia natively, is_scam
#                         confidence 0.7 on a genuinely benign bill message
#                         (a real miscalibration, but the smaller of the two)
#   openai/gpt-oss-120b : ~1400ms, same accuracy as the 20b, no speed benefit
#   qwen/qwen3.8-27b    : ~400-700ms (fastest), correctly read Odia
#                         natively, but confidence 0.85-0.92 on the same
#                         benign bill message -- MORE confidently wrong
#                         than gpt-oss-20b on that case; one 4.4s outlier
#                         seen in a 7-call burst (falls through to Tier 2
#                         offline under the 3s timeout below -- intended
#                         degradation, not a bug)
#   qwen/qwen3.6-27b    : hard 429 on the very first call -- this account's
#                         tier caps it at 1000 output-tokens/minute,
#                         unusable for real-time regardless of accuracy
# qwen/qwen3.8-27b initially won on the three requested criteria (fastest,
# correct Odia handling, active) and was wired in first -- but further
# testing (a handful more calls, well short of eval_testset.py's 72 cases)
# hit the SAME hard 429 qwen3.6-27b hit on its very first call: this
# account's tier caps `qwen/qwen3.8-27b` at 1000 output-tokens/minute too,
# and its replies run long enough (visible chain-of-thought-style prose
# before the JSON) to blow through that within single-digit calls. A model
# that rate-limits after ~7 calls is not "fast enough for real-time" in
# practice, whatever its per-call latency looks like when it succeeds --
# switched to openai/gpt-oss-20b instead: slower per call (~1s vs
# qwen3.8-27b's ~0.4-0.7s) but hit zero rate limits across all testing,
# including the full 72-case eval run below, and is already this
# codebase's own proven default (llm/client.py's GROQ_MODEL).
# ---------------------------------------------------------------------------
TIER1_FRAUD_THRESHOLD = 0.7
TIER1_SAFE_THRESHOLD = 0.2
TIER2_ONLINE_TIMEOUT_S = 3
GROQ_TIER2_MODEL = "openai/gpt-oss-20b"
# Requested threshold, kept as specified (see _tier2_offline).
TIER2_OFFLINE_SEMANTIC_THRESHOLD = 0.72

# ---------------------------------------------------------------------------
# RULE LAYER — high-precision override signals
# ---------------------------------------------------------------------------
HIGH_RISK_PATTERNS = {
    "authority_impersonation": [
        r"\bcbi\b", r"\bed\b", r"enforcement directorate", r"\bcustoms\b",
        r"narcotics", r"police\s*(case|arrest)", r"arrest\s*warrant", r"digital\s*arrest",
        r"money\s*laundering",
        # Batch-expanded 2026-07-06 (see HIGH_RISK_PATTERNS expansion notes):
        # legal-jeopardy framing that doesn't use the literal cbi/ed/police words.
        r"case (has been |is )?registered against (you|tumhe|aapko)",
        r"investigat(ing|ion).{0,20}(your|aapke|aapka) case",
        r"court (appearance|mein sunwai|sunwaayi)",
        r"arrest (ki )?notification",
        # Added 2026-07-16: real, live-observed false negative (SAFE, 0.49)
        # on an actual translated Gujarati digital-arrest scam
        # ("From the Jasi Cyber Crime Cell... your Aadhaar card... illegal
        # financial transactions... do not inform anyone... confirm your
        # identity within 30 minutes") -- generic institutional phrasing for
        # a police cyber-fraud unit, distinct from CBI/ED/customs (already
        # covered above) but the same authority-impersonation pattern.
        # Chakshu/Sanchar Saathi tracks this as its own impersonation
        # variant (see CLAUDE.md Section 6.3's cross-reference), same
        # justification as telecom_impersonation being split out from this
        # category rather than folded in as a synonym list of one sentence.
        #
        # \W* (not \s*) between the words -- real bug caught live re-testing
        # this exact scam via a typed/pasted message rather than OCR:
        # Sarvam's translation of the same Gujarati source sometimes renders
        # this as "Cyber ‐ Crime Cell", using U+2010 HYPHEN as a stray
        # separator between "Cyber" and "Crime" rather than plain
        # whitespace. \s* silently missed it (scored SAFE 0.393, rule_
        # categories=[] again); \W* matches whitespace, ASCII hyphens, and
        # any Unicode dash/punctuation variant alike.
        r"cyber\W*crime\W*(cell|branch|police|wing|department)",
    ],
    "credential_request": [
        r"\botp\b", r"\bcvv\b", r"\bpin\b", r"\bupi\s*pin\b", r"share.*(otp|pin|cvv)",
        r"kyc.*(update|pending|expire)",
        # Batch-expanded 2026-07-06: soft-signal category (only counts combined
        # with another category — see SOFT_SIGNAL_CATEGORIES), so covering
        # synonyms for otp/pin/cvv liberally here is low-risk.
        r"(security|verification|authentication|transaction|confirmation) (code|password|number|pin)",
        r"one-?time (password|security number|key)",
        r"kyc.{0,20}(confirm|complete|karna|jaankari|details|प्रक्रिया|विवरण)",
        r"(सुरक्षा|सत्यापन|गोपनीय|गुप्त) (कोड|नंबर|संख्या)",
        r"(अपना|आपका) .{0,15}(पासवर्ड|कोड|पिन|नंबर|संख्या) .{0,15}(बताएं|दें|डालिए|बताइए)",
        r"कार्ड.{0,10}पीछे.{0,15}(अंक|नंबर)",
    ],
    "urgency_coercion": [
        r"immediately", r"turant", r"abhi", r"urgent", r"do not (disconnect|tell|cut)",
        r"within \d+ (hour|minute|hr|min)", r"warna", r"otherwise.*block",
    ],
    "money_demand": [
        r"send money", r"paise\s*(bhej|transfer)", r"transfer.*now", r"pay.*fee",
        r"processing fee", r"settlement", r"safe (rbi|bank) account",
        # Batch-expanded 2026-07-06: kept demand-framed (imperative/mandatory)
        # AND tied to a vague/unusual destination, not bare finance nouns —
        # "clear pending charges", "pay the processing/service charge", and
        # "transfer the required amount" (alone) were tried and dropped: all
        # three false-flagged ordinary gym/passport/loan-EMI fee language in
        # manual testing before the eval run.
        r"(deposit|remit|credit|disburse|allocate|forward|transfer) the (required|necessary|mentioned|entire) (sum|amount|funds?|balance) to (this|the (provided|designated|given)|our)",
        r"(amount|paisa|fund|balance) ko (deposit|pay|bhej|daalo|shift) (karo|karna|kijiye|do)",
        r"(राशि|धन|फंड) (जमा करें|हस्तांतरण करें|ट्रांसफर करें)",
        r"(शुल्क|सेवा शुल्क) (जमा करें|भुगतान करना होगा)",
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
        # Tightened 2026-07-06: the bare "visiting your home" clause used to
        # fire on its own — matched a technician appointment, a courier
        # delivery, a scheduled inspection, etc. Now requires the visit be
        # tied to collecting something sensitive (card/documents/cash/PIN),
        # in either clause order, not just any mention of someone coming home.
        r"((come|visit|aayega) (to|at)? ?(your|the|aapke) (home|house|residence|ghar).{0,60}"
        r"(collect|take|le jaane|lene|surrender|hand over).{0,20}(card|documents?|papers?|cash|pin|cheque))"
        r"|"
        r"((collect|take|le jaane|lene|surrender|hand over).{0,20}(card|documents?|papers?|cash|pin|cheque).{0,60}"
        r"(come|visit|aayega) (to|at)? ?(your|the|aapke) (home|house|residence|ghar))",
        r"no need to (visit|go to) the (bank|branch)", r"bank jaane ki zaroorat nahi",
        r"someone will come (to )?collect", r"collect karne",
        # Batch-expanded 2026-07-06: near-deterministic override category —
        # kept each pattern tied to an explicit discouragement/self-handling
        # framing, not bare topic words, to avoid flagging ordinary chatter.
        r"(don'?t|do not) hang up", r"stay on the line",
        r"disconnect.{0,20}(reset|invalidate|restart)",
        r"(shouldn'?t|should not|don'?t|avoid).{0,15}(involve|discuss|contact).{0,15}(third part|anyone else|others)",
        r"(main|hum) (khud |sab (kuch )?)?(kar dunga|karwa dunga|kar lunga|dekh lunga|manage kar (lenge|lunga))",
        r"(call cut|phone rakh(a|o)|disconnect kiya) (kiya |toh)",
        r"(parivaar|family) ko.{0,15}mat (laiye|batao|bataiye)",
        r"kisi (ko|se).{0,20}mat (kariyega|karna|bolna|batana)",
        r"(sensitive|confidential|gopniya|गोपनीय) (mamla|matter|मामला)",
        r"batane ki (zaroorat|permission) nahi",
        r"(kahin|police station|thane) jane ki (koi )?zar[ou]rat nahi",
        r"contact karne ki (koi )?need nahi",
    ],
    # Reading an OTP/PIN/CVV/one-time code aloud over a call, under any
    # framing ("for verification", "to confirm your identity"). Near-100%
    # reliable: no legitimate bank, government body, or service ever asks
    # for this — see the near-deterministic override in predict() below.
    "otp_readout_request": [
        r"read\s+(out\s+|me\s+)?(the\s+|your\s+)?(otp|pin|cvv|code|digits|one-?time code)",
        # Real miss traced live 2026-07-22: "Send me the codes here directly"
        # (Apple Gift Card codes, not an OTP) matched this pattern's bare
        # "code" alternative and got tagged otp_readout_request -- wrong
        # category (though the message was still correctly flagged FRAUD
        # overall via urgency_coercion + the ML score). This pattern's own
        # design principle, documented on the paraphrased-readout patterns
        # below, is "not a bare code/number word" -- this one predates that
        # discipline and violated it. Requiring "otp"/"verification code"/
        # "one-time code" etc. explicitly (never bare "code") brings it in
        # line with every pattern added since.
        # "spell" added 2026-09-11: real gap found live -- "Just spell the 6
        # digit OTP on your phone to claim" scored FRAUD only via the
        # nondeterministic LLM second-opinion path (rule_categories=[]),
        # since none of tell/share/say/speak/send covers "spell it out"
        # readout phrasing. Same near-deterministic confidence as the other
        # readout verbs here -- no legitimate caller asks you to spell out
        # a one-time code either.
        #
        # "confirmation code" added 2026-09-11: real miss reported live via
        # a genuine Odia scam script ("...ଆପଣଙ୍କ ମୋବାଇଲକୁ ଆସିଥିବା
        # ନିଶ୍ଚିତକରଣ କୋଡ୍ ଆମକୁ କୁହନ୍ତୁ" -- "please tell us the confirmation
        # code sent to your mobile"). Sarvam's translation was accurate and
        # detect_native_script_lang correctly identified od-IN -- the gap was
        # purely lexical: "confirmation code" is an extremely common
        # legitimate synonym for a one-time verification code (used by
        # banks/e-commerce themselves), and neither this pattern nor the
        # provide/give one below it covered it, so the message scored on ML
        # alone (0.46, rules={}) with no deterministic rule backing it, on
        # both the original Odia and the translated English text. Not
        # Odia-specific -- any language's translation, or English/Hinglish
        # input directly, can produce this exact common phrasing.
        r"(tell|share|say|speak|send|spell)\s+(me\s+|us\s+)?(the\s+|your\s+)?(otp|pin|cvv|verification code|confirmation code|one-?time code)",
        r"(code|digits)\s+(that\s+)?(just\s+)?arrived",
        r"(code|digits)\s+you'?re\s+seeing",
        r"(confirm|send|share|tell)\s+the\s+(six|four|\d+)[- ]?digit",
        r"(otp|pin|cvv|code)\s+(bata|bol|bhej|de\s?do)(o|iye|na|do)?",
        # "de do"/"dedo" ("give [it]") added 2026-07-13: bata/bol/bhej (tell/
        # say/send) were covered but not the "give" verb itself in Hinglish
        # Latin script, even though both the English ("give me the otp",
        # line below) and Devanagari ("otp ... दें") forms already were —
        # found via a real "otp dedo pls" test message that neither this nor
        # the offline rule engine's verbatim copy caught.
        r"((bata|bol|bhej)(o|iye|do)|de\s?do)\s+(mujhe\s+)?(the\s+)?(otp|pin|cvv|code)",
        # Batch-expanded 2026-07-06: paraphrased readout requests that avoid
        # the literal otp/pin/cvv words. Each pattern requires an explicit
        # request/reference verb (provide/give/showing/displaying/bataen),
        # not a bare code/number word, since this category overrides the
        # score to 0.95 on its own — see NEAR_DETERMINISTIC_RULES below.
        r"(provide|give|share|state|relay|pass on) (us |me )?(the |your )?(otp|one-time password|verification code|confirmation code|security code|authentication code|one-time key)",
        r"(code|digits|number|figures|password|key) (that |which )?(is |are )?(showing|displaying|received|got so far|came|mila)",
        r"what('s| is) the (code|number|digits|figures) (that |you )?(received|got|showing|displaying)",
        r"(aapke|aapka) (mobile|phone|number) par (aaya|aayi|mila) hua",
        r"(chh|chaar|char)-?ankiya (number|pin|code)",
        r"ओटीपी.{0,12}(बताएं|बताइए|दें|सूचित करें|चाहिए)",
        # Added: "confirm the verification code" / "confirm the code on your
        # screen" style phrasing — a "confirm" framing rather than the
        # read/tell/share verbs above, and with no digit-count word, which
        # let it slip past every existing pattern (see the "case file ...
        # confirm the verification code" trace this was found from). This is
        # a common real-world readout framing: the caller isn't asking you to
        # "read out" anything by name, just to "confirm" what's already on
        # your screen — but the effect (getting the code spoken aloud) is
        # identical.
        r"confirm\s+the\s+(verification|security|authentication|transaction)\s+code",
        r"confirm\s+the\s+code\s+(that'?s\s+|currently\s+|showing\s+)?on\s+(your|the)\s+screen",
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
        # Batch-expanded 2026-07-06: broader verbs/roles for the same
        # in-person-card-collection intent, plus PIN-note-down phrasing not
        # already covered by "keep the pin ready/written down".
        r"(representative|executive|agent|associate|staff member|individual).{0,20}(collect|receive|obtain|acquire|procure).{0,15}card",
        r"(dispatch|send|bhej rahe).{0,15}(executive|agent|representative|banda|aadmi|ladka|kisi ko).{0,20}card",
        r"surrender (your |the )?.{0,15}card",
        r"present your card to",
        r"card.{0,10}(jama|deposit|surrender).{0,10}(karna|karana) hoga",
        r"(hamara|humara) (banda|aadmi) .{0,15}card",
        r"pin.{0,15}(jot(ted)? down|note(d)? (down|on)|likh (lo|lena|kar))",
        r"pin.{0,10}(kagaz|paper|diary) par",
        r"कार्ड.{0,15}(लेने आएगा|लेने आएंगे|सुपुर्द|जमा|दें)",
        r"पिन.{0,10}(नोट कर|लिख)",
    ],
    # Added 2026-07-07, cross-referenced against Sanchar Saathi/Chakshu's
    # official fraud-report categories (see CLAUDE.md Section 6.3) — three
    # gaps not previously covered by any HIGH_RISK_PATTERNS category:
    #
    # Caller claims to BE a relative/friend in sudden distress (accident,
    # arrest, lost phone/new number) and asks the victim to send money —
    # the "digital arrest"-adjacent family-emergency script. Deliberately
    # requires the distress claim to co-occur with a money-transfer verb (or
    # the secrecy framing) within one message, not bare presence of a
    # relative word — "beta"/"mom" alone is ordinary family chat (see fp10).
    # The secrecy variant ("don't tell dad") is intentionally narrower than
    # isolation_tactics' generic "don't tell family" patterns: this ties the
    # secrecy explicitly to the distress/money ask, so the two categories
    # reinforce rather than duplicate each other when they co-occur (see the
    # explicit score bump in predict() below).
    "relative_impersonation": [
        r"(trouble|musibat|mushkil|accident|emergency|problem).{0,100}(transfer|send money|bhej(o)?|jama karo|paisa|paise|chahiye|money|urgently need)",
        r"(transfer|send money|bhej(o)?|jama karo|paisa|paise|chahiye|money|urgently need).{0,100}(trouble|musibat|mushkil|accident|emergency|problem)",
        r"(lost my phone|phone kho gaya|this is (a friend'?s|my new) number|naya number hai).{0,100}(transfer|send|bhej|paisa|paise|money|urgent(ly)?)",
        r"(don'?t tell (dad|papa|mom|mummy|anyone|family)|kisi ko mat batana|mat batana).{0,100}(trouble|transfer|send|bhej|paise|money)",
        r"(trouble|transfer|send|bhej|paise|money).{0,100}(don'?t tell (dad|papa|mom|mummy|anyone|family)|kisi ko mat batana|mat batana)",
        r"(friend|dost|colleague).{0,60}(call|contact|milega|baat karega).{0,80}(send|bhej|transfer|paise|money|kuch bhejne)",
    ],
    # A specific variant of authority_impersonation: caller poses as
    # DoT/TRAI/the telecom operator itself rather than police/CBI/ED —
    # "your SIM/number will be disconnected", "unauthorized documents were
    # used to issue a connection in your name" (real Sanchar Saathi SIM-swap
    # / fraudulent-connection advisory categories). Kept as its own category
    # rather than folded into authority_impersonation so the two can be
    # told apart in signals/telemetry, but treated identically to
    # authority_impersonation in the critical-combo check below. The
    # disconnect pattern requires an explicit sim/mobile/telecom qualifier —
    # bare "connection" alone also matches ordinary electricity/gas
    # disconnection notices (caught against es8 in rakshak_eval_testset.json
    # during manual testing before this was tightened).
    "telecom_impersonation": [
        r"\btrai\b",
        r"department of telecommunications",
        r"\bdot\b.{0,30}(notice|department|officer)",
        r"(sim( card)?|mobile number|telecom (number|connection)|mobile connection).{0,40}(band|disconnect(ed)?|block(ed)?|deactivat(ed|e)?|suspend(ed)?)",
        r"(unauthorized|fraudulent|illegal).{0,30}(sim|document|connection).{0,30}(your name|aapke naam|issued|activate)",
    ],
    # Structural, not script-based by design: fires only when a threat of
    # exposure/leak (video/photo/recording) co-occurs with a payment demand
    # in the same message — the sextortion/blackmail category Sanchar
    # Saathi/Chakshu tracks separately from bank/authority impersonation.
    # Each pattern requires both the threat clause and the demand clause
    # together (either order); no legitimate context pairs "we'll leak your
    # video" with "pay now", so this stays a plain contributing category
    # rather than NEAR_DETERMINISTIC_RULES for now — that override is also
    # mirrored in Android's DecisionAgent.NEAR_DETERMINISTIC_RULE_CATEGORIES
    # for Tier 3b gating, and extending that cross-platform contract wasn't
    # part of this change.
    "extortion_threat": [
        r"(leak|expose|share|send|upload|release|publish|viral)\w*.{0,60}(video|photo|picture|recording|screenshot|clip|image).{0,80}(pay|transfer|send (money|payment)|bitcoin|crypto|\bupi\b)",
        r"(pay|transfer|send (money|payment)|bitcoin|crypto|\bupi\b).{0,80}(otherwise|warna|or (we|i) will|nahi to).{0,40}(leak|expose|share|send|upload|release|publish|viral)\w*.{0,20}(video|photo|picture|recording|screenshot|clip|image)",
        r"(video|photo|tasveer(ein)?).{0,60}(viral|leak|bhej denge|share kar denge|de denge).{0,80}(paisa|paise|payment|rupya|bhugtan|upi)",
        r"(video|photo|tasveer(ein)?).{0,80}(payment|paisa|paise|rupya|bhugtan|upi).{0,80}(bhej denge|share kar denge|de denge|viral|leak)",
        r"(recorded|record kar liya|access to your (device|phone|camera)|hacked your).{0,80}(pay|transfer|bitcoin|paisa|paise|payment|upi)",
    ],
    # Added 2026-07-12: text-classification coverage for link/URL-bait scam
    # framing only — deliberately does NOT analyze what a URL actually points
    # to or anything about post-click device state (that's link/url_safety.py,
    # Module 5's separate analyze_url() engine, exposed at /analyze_url; it
    # only ever runs on a URL a caller has already extracted and passed in,
    # never auto-invoked from this text path — a structurally different
    # problem: this module classifies the *message text*, not the link
    # target). "Click here" alone is far too common in ordinary, legitimate
    # messages (order tracking, bill payment, appointment confirmation — see
    # the false_positive_bait cases this was tuned against) to fire on its
    # own, so every pattern below requires the click/tap/open instruction to
    # co-occur with account/KYC/card suspension-threat framing, parcel/
    # delivery-hold framing, or prize/reward-claim framing, in either clause
    # order — the same near-deterministic-only-with-combination principle as
    # extortion_threat above, not a bare keyword match.
    "malicious_link_bait": [
        r"(account|kyc|card|profile) (will be |has been |has |is )?(suspend|block|deactivat|expir|freez|restrict)(ed|e)?.{0,80}(click|tap|open).{0,15}(link|url|button|claim|here)",
        r"(click|tap|open).{0,15}(link|url|button|claim|here).{0,80}(account|kyc|card|profile) (will be |has been |has |is )?(suspend|block|deactivat|expir|freez|restrict)(ed|e)?",
        r"(parcel|package|courier|shipment|delivery).{0,40}(hold|pending|customs|fee|undelivered|failed|reschedul\w*|could not be delivered|not delivered|unable to deliver).{0,80}(click|tap|open).{0,15}(link|url|button|claim|here)",
        r"(click|tap|open).{0,15}(link|url|button|claim|here).{0,80}(parcel|package|courier|shipment|delivery).{0,40}(hold|pending|customs|fee|undelivered|failed|reschedul\w*|could not be delivered|not delivered|unable to deliver)",
        r"(won|selected|eligible|congratulations).{0,40}(prize|reward|gift|lottery|lucky draw|cashback).{0,80}(click|tap|open).{0,15}(link|url|button|claim|here)",
        r"(click|tap|open).{0,15}(link|url|button|claim|here).{0,80}(won|selected|eligible|congratulations).{0,40}(prize|reward|gift|lottery|lucky draw|cashback)",
        r"(khaata|account|kyc|sim).{0,20}(band|block|suspend).{0,60}(is|us) link (pe|par) click kar(o|ke|iye|ein)?",
        r"(is|us) link (pe|par) click kar(o|ke|iye|ein)?.{0,60}(khaata|account|kyc|sim).{0,20}(band|block|suspend)",
    ],
    # Added 2026-07-12: caught a real miss — "Statement of Account6.25.zip
    # ... forward kar dijiye apni company ke finance manager ko ... computer
    # par open kijiye" scored SAFE, since no existing category covers
    # malware-delivery social engineering (this isn't impersonation, isn't a
    # credential request — it's convincing the victim to relay a malicious
    # attachment to whoever will open it on a real desktop, the classic
    # business-email-compromise/trojan-delivery pattern). Same combination
    # discipline as every other non-trivial category here: a bare "forward
    # this" or a bare ".zip" mention is far too common in ordinary work chat
    # to fire alone (see the "forward this invoice PDF to accounts for
    # payment" false_positive_bait case this was tuned against) — every
    # pattern requires a forward-to-someone instruction to combine with
    # EITHER an explicit desktop/laptop/PC-specific open instruction
    # (deliberately excludes phone/mobile — opening on a real computer is
    # what actually lets a .zip/.exe payload execute) OR a literal risky
    # attachment extension in the text. The open-on-computer pairing also
    # requires a finance/accounts/manager/boss-framed recipient, since
    # "forward + open on computer" alone is ordinary business chat; the
    # risky-extension pairing does not require a role, since an
    # executable/archive/macro-enabled extension is already a strong,
    # rare-in-legitimate-chat signal on its own.
    #
    # "email" added 2026-07-15: traced live via the WhatsApp/Twilio pipeline
    # test across all 12 languages — Sarvam's Hindi->English translation of
    # a genuine malware-attachment scam sentence ("...अग्रेषित करें...")
    # consistently (3/3) rendered the forward verb as "email", a legitimate
    # English synonym for "forward this as an attachment" that the
    # forward|send alternation didn't cover, so an otherwise-correct
    # translation scored REAL instead of FRAUD. Only added to the
    # English-language forward|send alternation, not the Hinglish
    # "forward kar" patterns, since Sarvam only ever produces English output
    # here.
    "malware_attachment_delivery": [
        r"(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,60}(finance (manager|team|department)|accounts (team|department|manager)|(your |the )?(manager|boss|supervisor|hr( team)?)).{0,120}open.{0,20}(on|in).{0,10}(your |the )?(computer|pc|laptop|desktop)",
        r"open.{0,20}(on|in).{0,10}(your |the )?(computer|pc|laptop|desktop).{0,120}(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,60}(finance (manager|team|department)|accounts (team|department|manager)|(your |the )?(manager|boss|supervisor|hr( team)?))",
        r"(finance manager|accounts (team|department|manager)|(company|apni company) ke (finance|accounts)).{0,50}(ko|ke liye)?.{0,25}forward kar ?(dijiye|do|kijiye|karein|ke)?.{0,120}(computer|pc|laptop|desktop) (par|pe) open ?(kijiye|karo|kariye|kar dijiye|karein)?",
        r"(computer|pc|laptop|desktop) (par|pe) open ?(kijiye|karo|kariye|kar dijiye|karein)?.{0,120}(finance manager|accounts (team|department|manager)|(company|apni company) ke (finance|accounts)).{0,50}(ko|ke liye)?.{0,25}forward kar ?(dijiye|do|kijiye|karein|ke)?",
        r"(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,150}\.(zip|exe|scr|js|docm|xlsm|bat)\b",
        r"\.(zip|exe|scr|js|docm|xlsm|bat)\b.{0,150}(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip))",
        r"forward kar ?(dijiye|do|kijiye|karein|ke)?.{0,150}\.(zip|exe|scr|js|docm|xlsm|bat)\b",
        r"\.(zip|exe|scr|js|docm|xlsm|bat)\b.{0,150}forward kar ?(dijiye|do|kijiye|karein|ke)?",
    ],
    # Added 2026-07-22: real miss reported live — "Congratulations, you've
    # cleared the initial screening for the part-time data entry role...
    # just a small refundable deposit is required to reserve your slot on
    # the training batch" scored SUSPICIOUS 0.556 with rule_categories=[],
    # falling back to the generic "language model flags risk... though no
    # explicit rule pattern matched" reason — no category explained *why*,
    # and the response never told the user to report at 1930. None of the
    # existing categories cover it: money_demand requires an explicit send/
    # transfer/pay-fee verb or a named destination account, neither of which
    # this message has ("a small refundable deposit is required" names no
    # verb or destination). This is the advance-fee job/training scam
    # already anticipated in the ScamType vocabulary (see report.py's
    # scam_type mapping, "job_fraud" -> "Job Fraud") but never covered by a
    # HIGH_RISK_PATTERNS category. Near-deterministic in the same sense as
    # otp_readout_request/card_collection_request: no legitimate employer,
    # recruiter, or training program ever requires a candidate to pay
    # anything — refundable or not — to secure an offer, interview slot, or
    # training seat, regardless of how the payment is framed. Every pattern
    # below requires the job/interview/training/onboarding framing to
    # co-occur with a payment-to-secure-a-slot framing, not bare presence of
    # either alone (a real job posting mentioning "training" or a real
    # e-commerce "reserve your slot" deal are both far too common to flag on
    # one half alone).
    "job_fraud": [
        r"(job|role|position|vacancy|hiring|interview|onboarding|training|internship|placement)"
        r".{0,100}(refundable|nominal|small|minimal|token|registration|security|processing)?"
        r"\s*(deposit|fee|amount|payment|charges?)"
        r".{0,10}(is |are |will be )?(required|needed|mandatory|must be paid|has to be paid)"
        r".{0,80}(reserve|secure|confirm|book|hold|lock|guarantee)\s*(your\s+)?"
        r"(slot|seat|position|spot|batch|offer)",
        r"(reserve|secure|confirm|book|hold|lock|guarantee)\s*(your\s+)?(slot|seat|position|spot|batch|offer)"
        r".{0,80}(refundable|nominal|small|minimal|token|registration|security|processing)?"
        r"\s*(deposit|fee|amount|payment|charges?)"
        r".{0,10}(is |are |will be )?(required|needed|mandatory|must be paid|has to be paid)"
        r".{0,100}(job|role|position|vacancy|hiring|interview|onboarding|training|internship|placement)",
        r"(pay|deposit|transfer).{0,30}(to|for).{0,20}(confirm|secure|reserve).{0,20}(your\s+)?"
        r"(job|offer|selection|placement|position|interview)",
        r"(training|joining|welcome|starter)\s*kit.{0,40}(pay|deposit|charges?|fee)",
        r"(job|naukri|training|seat|slot).{0,40}(confirm|book|reserve|pakka)\s*karne\s*ke\s*liye"
        r".{0,40}(deposit|fee|paise|rupaye|advance|shulk)",
        r"(deposit|fee|paise|rupaye|advance|shulk).{0,40}(job|naukri|training|seat|slot)"
        r".{0,40}(confirm|book|reserve|pakka)\s*karna\s*(hoga|padega)",
    ],
    # Added 2026-09-11 (multilingual/subtle-scam upgrade). Matched against the
    # same whitespace-collapsed, lowercased copy every other category uses,
    # AFTER translation to English for any of the 10 non-English/Hindi target
    # languages — so these are written as plain English phrasing only, no
    # Hinglish/Devanagari variants needed (translate_text_sarvam already
    # produces English before this ever runs). Lookaheads (not sequential
    # `.{0,N}` chains) are used deliberately so each combo fires regardless of
    # which order the phrases appear in — translation output doesn't
    # guarantee the same clause order as the source.
    #
    # First four patterns are the exact combos requested: bank-details +
    # verification + government-scheme; account-will-be-blocked + urgency;
    # confirm-your-details + before-amount-released; apply-now + bank-
    # information-required. The fifth generalizes the real shape behind all
    # of them — a "good news" benefit/payment trigger (approved/sanctioned/
    # payment pending/selected/eligible) paired with an instruction to
    # verify/confirm/update bank or account details — the "verify your
    # details to receive this benefit" phishing script used for fake
    # government-scheme, loan, subsidy, and welfare-payment (e.g. NREGA)
    # lures. Traced live against three real tricky cases that don't use the
    # literal combo wording at all ("Bank verification needed before
    # release" has no "details" word; "verify account details to proceed"
    # names no government scheme; "Update bank details ... to receive
    # amount" names no scheme either) — neither job_fraud (requires job/
    # interview framing) nor malicious_link_bait (requires an explicit
    # click/tap/open instruction tied to a suspension/parcel/prize threat)
    # covers this distinct "you're getting money, just confirm your details
    # first" shape.
    "universal_scam_pattern": [
        r"(?=.*\bbank\b)(?=.*verif)(?=.*government scheme)",
        r"(?=.*account will be blocked)(?=.*\b(immediately|within \d+|urgent(ly)?|hurry|turant|abhi|right away|as soon as possible|asap)\b)",
        r"(?=.*\b(confirm|verify)\b.{0,10}(your |the )?details)"
        r"(?=.*before.{0,10}(the )?amount.{0,15}(is |will be |gets )?(released|credited|disbursed|paid|transferred))",
        r"(?=.*\bapply now\b)(?=.*bank (information|details).{0,10}(is |are )?required)",
        r"(?=.*(approved|sanctioned|payment (is |has been )?pending|selected|eligible|shortlisted))"
        r"(?=.*\b(verify|confirm|update|provide)\b.{0,30}(bank|account)\b.{0,15}(detail|information))",
    ],
    # Added 2026-09-11: card/PIN/OTP digit-count readout phrasing and prize-
    # framing not already covered by otp_readout_request/reward_bait, plus
    # relative/authority-relay social-engineering preludes ("your father's
    # friend", "he told me to", "no need to panic", "we are here to help")
    # that precede a credential ask in real digital-arrest/family-emergency
    # scripts. Ported from a user-supplied pattern list; bounded `.{0,N}`
    # gaps used in place of the originally-suggested unbounded `.*` to match
    # this file's existing style (avoids pathological/greedy over-matching
    # across an entire long message). The four bare reassurance/relay
    # phrases ("no need to panic" etc.) are deliberately NOT added as
    # standalone patterns — each is far too common in ordinary benign
    # messages to flag alone (see this category's own design precedent:
    # isolation_tactics/relative_impersonation/job_fraud all require a
    # second, specific co-occurring concept rather than a bare phrase) — so
    # each is tied to a nearby credential/card/OTP/PIN context instead.
    "social_engineering": [
        r"card.{0,20}(3|three).{0,10}(digit|number)",
        r"\botp\b.{0,15}(spell|say|tell|share|read)",
        r"pin.{0,20}(6|six|3|three).{0,10}(digit|number)",
        r"lottery.{0,20}(won|win|winner|congratulation)",
        r"won.{0,20}(car|bike|iphone|prize|cash|lakh|crore)",
        r"congratulations.{0,20}(won|winner)", r"\blucky winner\b", r"\bjeeta hai\b",
        r"3.{0,5}digit.{0,20}card", r"card.{0,20}cvv", r"cvv.{0,20}(3|three).{0,10}(digit|number)",
        # Relative/authority-relay prelude + credential/card context
        # (English + Hinglish variants).
        r"(your father|papa ke dost|papa ne bheja|his father|her father|uncle ne bola)"
        r".{0,120}(otp|pin|cvv|card|tell me|batao|bata do)",
        r"(he told me to|unhone kaha)"
        r".{0,80}(otp|pin|cvv|card|tell me|batao|bata do)",
        r"(no need to panic|ghabrao mat|tension mat lo|we are here to help|hum help karne aaye)"
        r".{0,120}(otp|pin|cvv|card|share|tell|batao)",
        r"(just tell me|sirf batao|bas ek kaam)"
        r".{0,60}(otp|pin|cvv|card|number|digit)",
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
JOB_FRAUD_EXPLANATION = (
    "No legitimate employer, recruiter, or training program will ever ask you to pay money — "
    "refundable or not — to secure a job offer, interview slot, or training seat. A real "
    "employer pays you, not the other way around. Do not send any payment, block the sender, "
    "and report this at cybercrime.gov.in or by calling 1930."
)

# Rules treated as near-certain scam on their own — no legitimate caller has
# a reason to trigger any of these, so they override the ML/tone score
# regardless of what else did or didn't match (see predict()).
NEAR_DETERMINISTIC_RULES = {
    "isolation_tactics": ISOLATION_TACTICS_EXPLANATION,
    "otp_readout_request": OTP_READOUT_EXPLANATION,
    "card_collection_request": CARD_COLLECTION_EXPLANATION,
    "job_fraud": JOB_FRAUD_EXPLANATION,
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
    # Devanagari counterpart, added alongside the 2026-07-06 Hindi-script
    # otp_readout_request patterns above — a real bank SMS warning the user
    # not to share their OTP in Hindi must be exempted the same way the
    # English "do not share" phrasing already is.
    r"किसी को (मत|न) (बताएं|बोलना|बताना)",
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
    # Real bug traced via the Android OCR->Sarvam-translate->analyze_voice
    # path: HIGH_RISK_PATTERNS' cross-clause gaps (`.{0,120}` etc.) rely on
    # `.` matching any character, but Python's `re` module (no re.DOTALL
    # here) never lets `.` match a literal `\n`. Screenshot OCR text is
    # naturally multi-line, and Sarvam's translation preserves those line
    # breaks -- so a single continuous sentence like "...for verification.
    # Please open it on the computer" becomes "...for verification.\nPlease
    # open it on the computer" and every pattern spanning that gap silently
    # stops matching, even though the semantic content is unchanged. Collapse
    # all whitespace (not just lowercase) before rule-matching so line breaks
    # from OCR/translated/pasted multi-line text can't break proximity
    # matching -- the ML pipeline in predict() still sees the original,
    # un-collapsed text; only this rule-matching copy is normalized.
    t = re.sub(r"\s+", " ", text.lower())
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
        # Exact-text cache for the semantic-similarity check (see
        # _semantic_score) -- instance-level since ScamDetector is a
        # long-lived singleton (api/server.py's DETECTOR), so this persists
        # across requests for the process lifetime. Caches the (score,
        # scam_type) RESULT, not just the raw embedding: the FAISS index
        # itself is static, so a cached result is exactly reproducible and
        # skips the embed+search work entirely on a repeat, not just the
        # embedding step.
        self._semantic_cache = {}
        # Tier 2 online (Groq) cache, keyed by sha256 of the exact message
        # text as requested ("cache by message hash") rather than the raw
        # text itself -- functionally identical to a text-keyed dict for
        # exact-match caching, but matches the literal ask and avoids
        # holding arbitrarily long raw message text as a dict key.
        self._tier2_online_cache = {}

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

    def _score_text(self, text):
        """Pure scoring, no translation/LLM/level-decision — factored out of
        predict() so it can be run once on the original text and, for
        non-English/Hindi input, once more on a Sarvam translation, letting
        predict() pick whichever run scored higher (see predict()'s docstring
        note at the top of this module). Returns (score, rules, ml_fraud)."""
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

        # Critical combo: authority impersonation + (money OR credential) = digital arrest.
        # telecom_impersonation is a specific variant of authority_impersonation
        # (DoT/TRAI posing rather than police/CBI/ED posing) — same combo,
        # same elevation.
        if ("authority_impersonation" in rules or "telecom_impersonation" in rules) and (
            "money_demand" in rules or "credential_request" in rules
        ):
            score = max(score, 0.95)

        # relative_impersonation + isolation_tactics co-occurrence: the
        # family-emergency script's distress/money ask combined with an
        # explicit "don't tell/verify" instruction is the same reinforcing
        # pattern as the authority-impersonation combo above.
        if "relative_impersonation" in rules and "isolation_tactics" in rules:
            score = max(score, 0.95)

        # extortion_threat is structural by construction — every pattern in
        # that category already requires a threat clause AND a payment
        # clause together, so a single hit here carries the same weight as
        # two independent categories elsewhere (see rule_categories >= 2
        # above).
        if "extortion_threat" in rules:
            score = max(score, 0.85)

        # malware_attachment_delivery is structural the same way: every
        # pattern already requires a forward-to-someone instruction combined
        # with either a computer-specific open instruction (+ role framing)
        # or a risky attachment extension, so a single hit carries the same
        # weight as two independent categories elsewhere.
        if "malware_attachment_delivery" in rules:
            score = max(score, 0.85)

        # Near-deterministic overrides (isolation tactics, OTP/PIN readout
        # requests, in-person card collection) — each is near-certain scam on
        # its own, so any one of them overrides regardless of tone/ML score
        # and independently of which other categories (if any) also matched.
        if NEAR_DETERMINISTIC_RULES.keys() & rules.keys():
            score = max(score, 0.95)

        return score, rules, ml_fraud

    def _semantic_score(self, text):
        """Embeds `text` and searches the existing RAG scam-KB's FAISS
        index (rag/store.py, built from kb/scams.json) for the closest
        known scam card. Cache-first: an exact repeat of `text` returns
        instantly with no re-embedding and no index/disk I/O at all.
        Returns (score, scam_type) of the top match, or (0.0, None) if the
        store isn't built, the lookup fails for any reason, or there was no
        match at all -- the threshold check is the caller's job (see
        _tier2_offline), not this method's, since Tier 2 offline's gate is
        stricter than a bare threshold (also requires a rule signal)."""
        cached = self._semantic_cache.get(text)
        if cached is not None:
            return cached

        result = (0.0, None)
        if rag_store_exists():
            try:
                matches = rag_retrieve(text, n=1)
            except Exception as e:
                logger.warning("Semantic similarity lookup failed, skipping: %s", e)
                matches = []
            if matches:
                result = (float(matches[0]["score"]), matches[0]["scam_type"])

        self._semantic_cache[text] = result
        return result

    def _tier2_online(self, text):
        """TIER 2 ONLINE: one Groq call (GROQ_TIER2_MODEL, 3s timeout,
        cached by sha256 of `text`) asking for a direct scam verdict in
        JSON. Returns the parsed {is_scam, confidence, scam_type, reason}
        dict on success, or None on ANY failure (no/placeholder API key,
        timeout, network error, unparseable reply) -- None is predict()'s
        signal to fall through to TIER 2 OFFLINE, which is also how
        predict() decides mode="online" vs "offline" for its response."""
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._tier2_online_cache.get(key)
        if cached is not None:
            return cached

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            return None

        # Disambiguating context added 2026-09-11: the bare version of this
        # prompt was measured live against the full 72-case eval set at
        # FPR=0.400 (12/30 legitimate messages misflagged -- real bank
        # OTP/KYC/bill/delivery notices, "do not share" warnings, ordinary
        # family/work chat). Same failure class as the earlier LLM-second-
        # opinion feature two turns ago, worse here since this tier covers
        # a wider uncertain band (0.2-0.7) and originally replaced the
        # score outright rather than only ever raising it.
        prompt = (
            "IMPORTANT: These are NOT scams:\n"
            "- Bank OTP messages that say \"do not share\" (the bank is warning you, not asking)\n"
            "- Transaction alerts from known banks (SBI, HDFC, ICICI, Axis, Kotak)\n"
            "- Delivery notifications from Amazon, Flipkart\n"
            "- Bill payment reminders from official services\n"
            "- A message is only a scam if it ASKS you to share OTP/PIN/details, not if it warns you not to\n\n"
            "Analyze if this message is a scam targeting Indian citizens. "
            "Consider all Indian languages.\n"
            f"Message: {text}\n"
            'Reply JSON: {"is_scam": true/false, "confidence": 0.0-1.0, '
            '"scam_type": "string", "reason": "one sentence"}'
        )
        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=GROQ_TIER2_MODEL,
                messages=[{"role": "user", "content": prompt}],
                timeout=TIER2_ONLINE_TIMEOUT_S,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content)
            result = {
                "is_scam": bool(parsed["is_scam"]),
                "confidence": float(parsed["confidence"]),
                "scam_type": str(parsed.get("scam_type") or ""),
                "reason": str(parsed.get("reason") or ""),
            }
        except Exception as e:
            logger.warning("Tier 2 online (Groq) unavailable, falling back to offline tier: %s", e)
            return None

        self._tier2_online_cache[key] = result
        return result

    def _tier2_offline(self, text, rule_categories):
        """TIER 2 OFFLINE: semantic similarity, but double-gated as
        requested -- only "upgrades" (predict() takes max(tier1_score,
        semantic_score)) when semantic_score > TIER2_OFFLINE_SEMANTIC_THRESHOLD
        AND at least one Tier 1 rule category already matched. Requiring
        both was explicitly requested as a false-positive guard, and
        matches what an earlier, single-gated version of this same
        semantic layer measured live: raw top-1 similarity against this
        card corpus doesn't separate scam from safe well enough alone
        (SCAM cases ranged 0.427-0.732, SAFE cases 0.459-0.712, almost
        total overlap) -- requiring a rule hit too means a message with NO
        rule signal at all (most of the false positives that regression
        surfaced) can never be upgraded by semantic similarity alone,
        however high its score."""
        if rule_categories < 1:
            return None
        semantic_score, semantic_scam_type = self._semantic_score(text)
        if semantic_scam_type and semantic_score > TIER2_OFFLINE_SEMANTIC_THRESHOLD:
            return semantic_score, semantic_scam_type
        return None

    def predict(self, text):
        text = (text or "").strip()
        if not text:
            return self._format("SAFE", 0.0, "Empty message.", [], {}, mode="online", engine="rules")

        # TIER 1: deterministic rules + ML, on both the original text and
        # (for any of the 10 non-English/Hindi target languages' native
        # scripts) a Sarvam translation, keeping whichever scored higher.
        # English/Hindi/Hinglish (Latin script, or Devanagari — "hi-IN")
        # already work directly against this module's own patterns, so
        # they're excluded here the same way
        # bot.sarvam_translate.detect_native_script_lang already treats
        # Latin script as translation-exempt; source_lang is None for both.
        # This is unchanged from the prior multilingual upgrade -- still
        # "the existing rule layer" this redesign's Tier 1 refers to.
        score, rules, ml_fraud = self._score_text(text)
        source_lang = detect_native_script_lang(text)
        if source_lang and source_lang != "hi-IN":
            translated = translate_text_sarvam(text, source_lang, "en-IN")
            if translated:
                t_score, t_rules, t_ml_fraud = self._score_text(translated)
                if t_score > score:
                    score, rules, ml_fraud = t_score, t_rules, t_ml_fraud

        # TIER 1 immediate resolution at the extremes -- no LLM/semantic
        # call, no network, ever, for these two bands.
        if score >= TIER1_FRAUD_THRESHOLD:
            level = "FRAUD"
            signals = self.build_signals(rules)
            reason = self.build_reason(level, rules, ml_fraud)
            return self._format(level, round(score, 3), reason, signals, rules, mode="online", engine="rules")
        if score <= TIER1_SAFE_THRESHOLD:
            level = "SAFE"
            signals = self.build_signals(rules)
            reason = self.build_reason(level, rules, ml_fraud)
            return self._format(level, round(score, 3), reason, signals, rules, mode="online", engine="rules")

        # UNCERTAIN ZONE (TIER1_SAFE_THRESHOLD, TIER1_FRAUD_THRESHOLD):
        # neither a clear SAFE nor a clear FRAUD from the rules/ML alone --
        # try TIER 2 ONLINE first; None (missing key, timeout, network
        # error, unparseable reply) means "no internet" for this purpose,
        # so fall through to TIER 2 OFFLINE.
        tier2_online = self._tier2_online(text)
        if tier2_online is not None:
            llm_says_scam = tier2_online["is_scam"]
            llm_score = tier2_online["confidence"] if llm_says_scam else (1.0 - tier2_online["confidence"])
            # Changed 2026-09-11: this used to be `final_score = llm_score`
            # (a full replacement of the Tier 1 rule score) -- measured live
            # at FPR=0.400 on the 72-case eval, since a wrong LLM verdict had
            # no rule-based floor/ceiling to check it against at all. Now:
            # a SCAM verdict can only ever raise the score (max with the
            # Tier 1 rule score), and a SAFE verdict can only ever lower it
            # (min) -- so the LLM can push a genuine scam the rules under-
            # scored up into FRAUD/SUSPICIOUS, or pull a rule-driven false
            # positive back down toward SAFE, but never invert a strong
            # rule signal in either direction on its own.
            final_score = max(score, llm_score) if llm_says_scam else min(score, llm_score)
            if final_score >= TIER1_FRAUD_THRESHOLD:
                level = "FRAUD"
            elif final_score >= SUSPICIOUS_THRESHOLD:
                level = "SUSPICIOUS"
            else:
                level = "SAFE"
            signals = self.build_signals(rules)
            if llm_says_scam and tier2_online["scam_type"]:
                signals = signals + [f"LLM-flagged scam type: {tier2_online['scam_type']}"]
            reason = tier2_online["reason"] or self.build_reason(level, rules, ml_fraud)
            return self._format(level, round(final_score, 3), reason, signals, rules, mode="online", engine="llm")

        # TIER 2 OFFLINE: double-gated semantic similarity (see
        # _tier2_offline) -- only ever raises score, never replaces it the
        # way Tier 2 online's llm_score does, since a similarity match is
        # weaker evidence than a direct LLM verdict.
        engine = "rules"
        offline_match = self._tier2_offline(text, len(rules))
        if offline_match is not None:
            semantic_score, semantic_scam_type = offline_match
            score = max(score, semantic_score)
            rules = dict(rules)
            rules["semantic_similarity"] = 1
            engine = "semantic"

        if score >= TIER1_FRAUD_THRESHOLD:
            level = "FRAUD"
        elif score >= SUSPICIOUS_THRESHOLD:
            level = "SUSPICIOUS"
        else:
            level = "SAFE"

        signals = self.build_signals(rules)
        reason = self.build_reason(level, rules, ml_fraud)
        return self._format(level, round(score, 3), reason, signals, rules, mode="offline", engine=engine)

    def build_signals(self, rules):
        label = {
            "authority_impersonation": "Impersonates law-enforcement / govt authority",
            "credential_request": "Requests OTP/PIN/CVV/KYC credentials",
            "urgency_coercion": "Creates artificial urgency / coercion",
            "money_demand": "Demands money transfer",
            "reward_bait": "Offers unrealistic reward / lottery / returns",
            "isolation_tactics": "Discourages independent verification (bank/police/family)",
            "otp_readout_request": "Asks you to read out your OTP/PIN/CVV over the call",
            "card_collection_request": "Arranges in-person collection of your card, or asks you to keep the PIN ready",
            "relative_impersonation": "Claims to be a family member/friend in sudden distress asking for urgent money",
            "telecom_impersonation": "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection",
            "extortion_threat": "Threatens to leak private content unless paid (blackmail/sextortion framing)",
            "malicious_link_bait": "Pressures you to click a link, tied to an account/KYC suspension threat, a parcel/delivery hold, or a prize claim",
            "malware_attachment_delivery": "Asks you to forward an attachment (e.g. to a finance/accounts contact) and open it on a computer, or names a risky file type (.zip/.exe/.docm/etc.)",
            "job_fraud": "Asks you to pay a deposit/fee to secure a job offer, interview, or training slot",
            "universal_scam_pattern": "Combines an official-sounding benefit/approval claim with a request to verify, confirm, or update your bank/account details before you receive anything",
            "social_engineering": "Uses a prize/lottery hook or a relative/authority-relay preamble to lead into a card/PIN/OTP number request",
            "semantic_similarity": "Semantically similar to a known scam pattern in the knowledge base",
        }
        return [label[k] for k in rules]

    def build_reason(self, level, rules, ml):
        """Single source of truth for the user-facing explanation, shared by
        every caller (message path here, voice/voice_fraud.py's
        analyze_transcript(), rag/retriever.py's fallback) so the displayed
        reason always traces back to the same rule_categories that drove the
        score — never an independently-matched, unsynchronized signal set."""
        if not rules:
            if level == "SAFE":
                return "No fraud patterns detected; language consistent with legitimate messaging."
            return f"Language model flags risk (fraud likelihood {ml:.0%}) though no explicit rule pattern matched."
        deterministic_hits = [k for k in NEAR_DETERMINISTIC_RULES if k in rules]
        if deterministic_hits:
            return " ".join(NEAR_DETERMINISTIC_RULES[k] for k in deterministic_hits)
        parts = self.build_signals(rules)
        return f"{level}: detected {len(parts)} risk signal(s) — " + "; ".join(parts) + "."

    def _format(self, level, score, reason, signals, rules, mode="online", engine="rules"):
        return {
            "risk_level": level,
            "score": score,
            "reason": reason,
            "signals": signals,
            "recommended_action": ACTION_BY_LEVEL[level],
            "rule_categories": list(rules.keys()),
            "mode": mode,
            "engine": engine,
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
