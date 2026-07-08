**Phase 1 status: implemented.** The Android skeleton described below now exists in `/android`
(package `com.rakshak.ai`, minSdk 29). See the end of this doc for what's real vs. stubbed and
how to run it.

# Rakshak AI — Android Client, Phase 1 (revised)

This repo already contains **Prahari**, a working Python fraud-intelligence backend (see
`README.md`). This document specifies the Android call-protection app that will consume it,
and supersedes the earlier all-mock Phase 1 draft: wherever Prahari already covers a signal,
the Android client calls it over HTTP instead of stubbing it. Read this before writing any
Android code.

---

## 0. Hard constraints (unchanged, still binding)

1. **No covert call recording.** `CallScreeningService` only gets `Call.Details` (number, timing)
   *before* the call connects — no audio, no transcript. Live in-call audio requires becoming the
   default dialer with explicit two-party consent — that is still Phase 4, not this phase. Nothing
   in this revision changes that boundary.
2. **No broad contact/PII harvesting.** Minimum permissions only, system pickers over bulk grants.
3. **Personal data and fraud-detection logic stay architecturally separate.** The Prahari endpoints
   below take a phone number, transcript, URL, or message text — never contacts, account numbers,
   or family info. No agent/client call path may smuggle user-data-store content into a request body.
4. **Consume government infrastructure, don't rebuild it.** CNAP and Sanchar Saathi remain mocked —
   see Section 2.
5. The app never moves money, changes settings, or takes irreversible action without per-action
   confirmation, except the pre-authorized protective lock (still out of scope for this phase).

---

## 1. What Prahari already covers vs. what's genuinely mocked

| Rakshak agent role | Prahari coverage | Integration |
|---|---|---|
| **Call Intelligence** (CNAP + Sanchar Saathi, number-only, pre-connect) | **Not covered** — Prahari has no phone-number-reputation lookup; nothing to consume | `MockCallerLookupSource` stays, as originally planned |
| **Speech Intelligence** (scam-phrase / urgency detection on text) | **Covered** — `POST /analyze_voice {transcript}` (`voice/voice_fraud.py`), `POST /analyze_message {text}` (`ml/detector.py`) | Real HTTP calls, fed from manual/pasted text (see Section 3 — no live audio in this phase) |
| **Behavior** (escalation, repetition, sustained contact) | **Covered** — `POST /analyze_session {session_id, text}` (`ml/session.py`) | Real HTTP call, `session_id` = caller's E.164 number |
| **Knowledge/RAG** (plain-language "why", sourced from Chakshu/PIB/I4C corpus) | **Covered** — `kb/scams.json` (75 cards) + FAISS retrieval + LLM generation (`rag/retriever.py::retrieve_and_respond`, driven by `bot/agent.py::chat`) | Needs a new thin JSON endpoint (Section 4) — currently only reachable via the Twilio webhook |
| **Graph Intelligence** (cross-reference against known fraud rings) | **Partially covered** — `GET /graph` (`webhook/app.py`) links chat *sessions* by shared script/entity fingerprints (`graph/entity_extractor.py`); separately `GET /graph/analyze` (`api/server.py`) does phone/bank/device interaction-graph analytics if interactions are logged | Best-effort: query `/graph` with the caller's number as session key; treat "no match" as normal, not an error |
| **Decision Agent** (combine signals → risk level + reasons) | **Covered conceptually** — `casefile/case_generator.py::generate_case` already fuses message/voice/session/graph scores into CONFIRMED_FRAUD / SUSPECTED_FRAUD / LOW_RISK at the same 0.7 / 0.4 thresholds used everywhere else in Prahari | Android's Decision Agent mirrors these same thresholds/labels (mapped to high/medium/low) for consistency, and calls `/case/generate` directly when the user escalates to Tier 3 (real case file, not a stub) |

**Net effect:** only CNAP + Sanchar Saathi are mocked. Everything text/transcript/graph-based
routes to the real backend.

---

## 2. Call Intelligence Agent (unchanged design, richer mock data)

`CallerLookupSource` interface, `MockCallerLookupSource` implementation with hardcoded test
numbers (known-good bank lines, known-scam numbers, unknown). Each scam entry now also carries
a `suspectedScamType` tag (e.g. `"digital_arrest"`, `"bank_otp_kyc"`) matching the `scam_type`
vocabulary in `kb/scams.json` (see `_SCAM_AUTHORITY` map in `rag/retriever.py` for the existing
type list) — this tag is what lets the pre-connect warning card pull a *real* RAG explanation
(Section 3) instead of hardcoded copy, even though no transcript exists yet.

---

## 3. Where live Prahari calls plug in (and where they can't, yet)

Because `onScreenCall()` fires before connect with no audio, there is no live transcript to
stream to `/analyze_voice` or `/analyze_session` during actual ringing in this phase. Real
integration happens in two places:

1. **Pre-connect warning card, "Why?" panel:** if the mock lookup tags a `suspectedScamType`,
   call the new `/assistant/chat` endpoint (Section 4) with a synthetic query
   ("explain the {scamType} scam pattern") to render a genuine plain-language explanation +
   source citation from `kb/scams.json`, instead of static text.
2. **"Check a call/message" screen** (new, manual-entry): a text field where the user pastes or
   types what the caller said (post-call, or read off speakerphone) — or a future STT hookup once
   Phase 3/4 lands. Submitting it calls, in order:
   - `POST /analyze_voice {transcript}` — voice-specific classification
   - `POST /analyze_session {session_id, text}` — session_id = the caller's number, so repeated
     calls from the same number accumulate escalation signal server-side
   - `POST /assistant/chat {session_id, message}` — RAG explanation (also auto-populates the
     fingerprint graph for future ring detection)
   - Decision Agent (Android-side) combines the three into one risk level + reasons list, using
     the same 0.7/0.4 thresholds as `casefile/case_generator.py`
3. **Tier 3 escalation ("Call for help" / file a report):** calls `POST /case/generate` with the
   accumulated text/session_id/subject=phone number, producing a real, hashable case file the
   user can hand to 1930/cybercrime.gov.in — not a stub.

The traffic-light UI shown at actual ring-time (pre-connect) still reflects only the Call
Intelligence signal, exactly as originally scoped — that has not changed.

**Speech-to-text is entirely the Android app's responsibility — Prahari has none.**
`voice/voice_fraud.py::analyze_transcript()` takes a `transcript` string; nothing in this repo
produces that string from audio. There is no Whisper/Vosk/Google-Speech/AssemblyAI integration
anywhere in Prahari — the README lists "Whisper front-end to feed real audio into Module 6" only
as an unbuilt future extension. Concretely: the "Check a call/message" screen in this phase gets
its text from manual paste/typing; any later phase that wants to feed live or recorded call audio
into `/analyze_voice` must add its own STT (on-device `SpeechRecognizer` for a Phase 3
voicemail-style screening flow, or Whisper/equivalent once Phase 4 default-dialer audio capture
with two-party consent exists) and hand Prahari the resulting text — Prahari will never take raw
audio as input.

---

## 4. Backend prerequisite (spec only — not implemented yet)

Add one new endpoint before/alongside Android work, in `webhook/app.py` (or a new lightweight
router) wrapping the existing `bot.agent.chat()`:

```
POST /assistant/chat
  body: {"session_id": "<caller phone number>", "message": "<free text>"}
  returns: same dict shape chat() already returns (answer, scam_type, confidence, engine,
           profile, fingerprint?, intent, session_id, history_length)
```

Reusing `chat()` (rather than calling `retrieve_and_respond` directly) is deliberate: it also
gets the pushback gate, elderly/farmer formatting, verification-lure guardrail, and automatic
fingerprint extraction into the session graph for free — the same behavior the WhatsApp bot gets.

No other backend changes are required for this phase.

---

## 5. Operational setup for today's demo

- Two Python processes, two ports: `python -m api.server 8000` (Modules 1/2/5/6/7) and
  `uvicorn webhook.app:app --port 8001` (chat/graph — requires `GEMINI_API_KEY`/`GROQ_API_KEY`
  in `.env`, already present, plus the heavier `torch`/`FlagEmbedding`/`faiss` deps from
  `requirements.txt`).
- Android reaches them via two configurable base URLs (default `http://10.0.2.2:8000` and
  `http://10.0.2.2:8001` for emulator; `adb reverse tcp:8000 tcp:8000` etc. for a physical device).
- The `/assistant/chat` (RAG) path depends on heavier ML deps + external LLM API keys and is the
  most likely thing to fail to start or time out. The Android client must degrade gracefully
  (timeout + generic "explanation unavailable, verify independently" fallback) rather than block
  the rest of the flow — the app must never appear to hang because an explanation call failed.

---

## 6. Known limitations of the classifier we're consuming (tracked, not fixed)

Not fixing either of these now — documenting them so they're not forgotten before demoing/presenting
this to anyone who might assume "ML-trained" means "trained on real incident data":

1. **Prototype-grade training data, not production-grade.** As confirmed by reading
   `data/synth.py::generate_messages()`, the entire training set for `ml/detector.py::ScamDetector`
   (which `voice/voice_fraud.py` also reuses as its base score) is ~31 hand-written template
   sentences (8 digital-arrest, 6 bank/OTP, 5 investment/lottery, 12 safe, 4+4 short), resampled
   with light augmentation (leetspeak-ish digit swaps, filler words, double-spacing) up to 240+240
   rows. There is no real complaint/report corpus, no scraped scam-message dataset, no held-out
   real-world validation set behind this model — it should be described as a rule-layer-backed
   **prototype/demo classifier**, not a production-trained model, in any demo narration or docs.
2. **No genuine Hindi/code-mixed training data.** The templates include some Hinglish phrasing
   (Latin-script transliteration, e.g. `"Turant video call pe aaiye"`, `"OTP batao warna account
   band ho jayega"`), but every template is Latin-script only — there are zero Devanagari-script
   examples anywhere in the training set, and the "Hinglish/Hindi/English" support claimed in the
   module docstring rests on a handful of hand-crafted Latin-transliterated lines, not a real
   annotated Hindi or code-mixed corpus. This is a real gap against the target user base (elderly/
   rural users are at least as likely to receive scam messages in Devanagari as in Hinglish).

### 6.3 Rule-category coverage is cross-referenced against Sanchar Saathi/Chakshu's official taxonomy

`ml/detector.py::HIGH_RISK_PATTERNS` category set (2026-07-07 addition: `relative_impersonation`,
`telecom_impersonation`, `extortion_threat`) was chosen by cross-referencing the fraud categories
Sanchar Saathi's Chakshu facility actually tracks for citizen reports (impersonation of
police/CBI/customs/UIDAI/RBI, KYC/payment fraud, telecom-connection/SIM misuse, job/lottery/loan
offers — see `data/scraper.py::scrape_sanchar_saathi`'s FAQ scrape for the same list), not invented
ad hoc. The three additions filled gaps against that list that no existing category covered:
family-member-in-distress impersonation, DoT/TRAI/telecom-operator impersonation specifically (as
opposed to police/CBI/ED, already covered by `authority_impersonation`), and blackmail/sextortion
(threat of exposure + payment demand, a category Chakshu tracks separately from bank/authority
fraud). Chakshu itself remains a one-way citizen-report portal with no public read API or feed — see
the note on this in the Section 1 table — this cross-reference is against its published category
taxonomy, not a data feed.

Same process as the 2026-07-06 batch-expansion: candidate phrasings were LLM-drafted offline (no
separate tool — this conversation's model, prompted to paraphrase each category's script into
English/Hinglish/Devanagari variants), then hand-consolidated into regex requiring the *combination*
of signals a real script actually needs (e.g. `relative_impersonation` requires a distress/new-number
claim co-occurring with a money-transfer verb, not bare presence of "beta"/"mom" — see the code
comment above that category for the false-positive case this was tuned against). `extortion_threat`
is deliberately structural rather than script-based: every pattern requires a threat clause and a
payment clause together, so a single hit already carries the weight of two independent categories
(see the score bump in `predict()`).

Gated the same way: `rakshak_eval_testset.json` grew from 36 to 52 cases (3 scam + 2 false-positive-
bait per new category, symmetrically for all three, not just telecom, plus one deliberately-failing
case — see below), and both `eval_testset.py` (phone-app path, with and without the LLM explanation
layer) and `eval_rag_testset.py` (WhatsApp bot's RAG path) were re-run before these patterns were
considered promoted: 100% recall across every category including the three new ones, 0%
false_positive_bait FPR on every case except the one intentional exception, no regression on the
pre-existing 36 cases.

One drafted false-positive-bait case — a benign "beta, I've sent your college fees" message
(`"Beta, maine tumhare college fees ke liye 20000 rupaye tumhare account mein transfer kar diye
hain, check kar lena aur confirm karna."`) — tripped the pre-existing ML baseline at 0.512
(SUSPICIOUS, not FRAUD), independent of any new rule pattern (`rule_categories: []`). Feature-
attribution analysis confirmed the base ~31-template classifier (prototype-grade training data,
item 1 above) associates `account`/`transfer`/`rupaye`/4-5-digit amounts with FRAUD regardless of
tense or family context — it can't tell "I already sent you money" from "send me money now." A
reworded, passing variant was kept as `fp18`; the original failing text was deliberately kept too,
as `fp24`, flagged `"known_failing": true` with a `"known_failing_note"` explaining why — a real,
pre-identified target for Day 2's gated retraining pipeline to validate against once it exists.
`eval_testset.py` will report `fp24` as a false positive on every run until that pipeline lands; this
is expected and documented in the JSON's own top-level `notes`, not a regression to chase.

None of the three new categories were added to `NEAR_DETERMINISTIC_RULES` — that override is mirrored
in Android's `DecisionAgent.NEAR_DETERMINISTIC_RULE_CATEGORIES` for Tier 3b auto-escalation gating,
and deciding whether any of these three should eventually gate Tier 3b is a separate, deliberate
cross-platform decision, not a byproduct of this expansion.

---

## 7. New Android permission implied by this revision

- `INTERNET` (normal permission, no runtime prompt) — required now that the app makes real HTTP
  calls, where the original all-mock draft needed none. Flagging explicitly since it's a new
  addition versus the original plan.
- Permissions agreed earlier for the UI (`POST_NOTIFICATIONS`, `USE_FULL_SCREEN_INTENT`) and the
  CallScreeningService role-grant flow are unchanged.

---

## 8. Unchanged from the original spec

Decision Agent aggregation boundary, Escalation Tiers 1–3 (panic/mute stub, mock notify-contact,
real dial-1930-via-`ACTION_DIAL`), traffic-light UI, and the project-layout decision (new
`android/` subfolder, existing Python backend untouched) all carry over as previously agreed.

---

## 9. Design decisions for later phases (captured now, not implemented yet)

### 9.1 RAG explanation upgrade (Phase 2, Knowledge Agent)

Today, `rag/retriever.py::retrieve_and_respond` only ever hands the LLM a fixed template with the
retrieved card's `scam_type` and `what_to_do` slotted in (see `_PROMPT_TEMPLATE`) — the model isn't
given the actual transcript/message to reason over, and the fast-path "why" a user sees for a raw
classifier hit (`ml/detector.py`'s `reason`/`signals` fields) is pure keyword/rule output, not
generated reasoning.

Phase 2's Knowledge Agent should instead: pass the **full transcript/message text** together with
the top retrieved `kb/scams.json` card(s) as context to an LLM (e.g. Claude) and have the model
generate the plain-language "why this is risky" explanation from actual reasoning over that
context — not just interpolate two fields into a canned sentence. The existing small
classifier/rule-layer stays exactly as it is today: a fast, cheap, offline first-pass signal used
for triage and thresholding (SAFE/SUSPICIOUS/FRAUD, escalation decisions), but it stops being the
thing the user reads as "why" — the user-facing explanation becomes the LLM's reasoned output.
Not building this now; the current template-based `retrieve_and_respond` stays as-is until Phase 2.

### 9.2 Elderly-first UX requirements (all phases)

These constrain every phase's UI work going forward, not just Phase 1:

- **Warnings must be spoken aloud**, in the user's configured language — not just displayed as
  text. A frightened or low-literacy user may not read a screen mid-call; text-to-speech is not
  optional supplementary polish, it's the primary channel.
- **Exactly one large action button during an active warning** — no menus, no secondary options,
  no "more actions" affordance while risk is being shown. Decision paralysis is the failure mode
  being designed against here.
- **Setup is a one-time, family-member task, not an elderly-user task.** Trusted-contact list,
  language selection, and any other configuration happen once, in a calm setup flow intended to be
  completed by a family member/caregiver on the user's behalf — never asked of the elderly user
  in the moment, and never re-litigated mid-scam (this is consistent with the original spec's Tier
  4 rule that protective actions must be pre-authorized in advance, not decided live).
- **Silent and invisible in normal operation.** The app must not surface any UI, sound, or
  notification during a normal, unflagged call — it only appears at all once a risk signal fires.
  No persistent status icons, banners, or "scanning..." indicators during ordinary use.

Not implementing any of this yet — captured here so it isn't lost before UI work begins.

---

## 10. Phase 1 implementation notes (`/android`)

What's built, and the honest gaps against the ideal spec:

- `callscreening/RakshakCallScreeningService.kt` — pre-connect only, scores purely off
  `MockCallerLookupSource` (Prahari has nothing for a bare number, per Section 1). For HIGH risk
  it silences the call automatically via `CallResponse` inside `onScreenCall` — this is the real,
  working Tier-1 action, decided before any UI exists, not triggered by a button tap.
- `ui/CheckCallActivity.kt` — the manual "what did the caller say" screen; calls Prahari's real
  `/analyze_voice` and `/analyze_session` (never `/assistant/chat` — excluded, Phase 2).
- `intelligence/DecisionAgent.kt` — pure Kotlin aggregation, mirrors Prahari's 0.7/0.4 thresholds.
- `ui/WarningActivity.kt` — full-screen card, TTS-spoken headline, exactly one large button visible
  at a time (WARNING state → "I need help" → HELP state → "Call 1930"). The "Why?" disclosure is
  read-only, not a competing action, so it doesn't violate the one-button rule.
- `escalation/EscalationOrchestrator.kt` — Tier 3 (`dialHelpline`) is real (`ACTION_DIAL`, no
  `CALL_PHONE` permission needed). Tier 2 (`notifyTrustedContact`) is a logged/mock stub — no real
  contact list or message channel exists yet. The panic button's "mute" outcome is reported, not
  re-triggered — see the doc comment on `describePanicOutcome` for why an already-answered call
  can't be muted without InCallService/default-dialer status (Phase 3/4).
- Permissions used: `INTERNET`, `POST_NOTIFICATIONS`, `USE_FULL_SCREEN_INTENT` — all previously
  discussed in Sections 5/7, nothing new added. No `READ_PHONE_STATE`, `READ_CALL_LOG`,
  `ANSWER_PHONE_CALLS`, or `CALL_PHONE`.
- Gradle wrapper JAR is committed (`android/gradle/wrapper/gradle-wrapper.jar`). A JDK 17 +
  Android SDK toolchain is available at `D:\rakshak-android-toolchain` (source
  `D:\rakshak-android-toolchain\env.sh` before running `./gradlew`) — see Section 12 for the
  first real build/install/launch against a physical device, which superseded the earlier
  "no JDK/Gradle in this environment" assumption baked into Sections 10-11.

---

## 11. Voice input (STT) and language-aware spoken warnings (TTS)

Added to the "Check a call/message" screen and the warning speech feature, purely as additive
input/output — neither touches `ml/detector.py`, `rag/retriever.py`'s decision delegation, or any
other part of the Prahari detection pipeline. Confirmed via the full `rakshak_eval_testset.json`
suite (54 cases) both before and after: 100% recall, 0.040 false_positive_bait FPR (fp24 only),
byte-identical to the pre-change baseline, since no Python file in the detection path was touched.

### 11.1 STT — voice input on "Check a call/message" (`stt/VoiceInputHelper.kt`)

Voice is an *option alongside* the existing typed-text field, never a replacement — the transcript
field is still editable either way, and the "Check this" button still sends whatever text is in it.

Deliberately built on `SpeechRecognizer.createOnDeviceSpeechRecognizer()` (API 31+) rather than the
older `createSpeechRecognizer()` + `EXTRA_PREFER_OFFLINE` hint: the older path is only a *preference*
— Android can silently fall back to a cloud recognizer if no offline pack exists, which this app's
privacy posture (no audio/text leaves the device unless the user typed it themselves) treats as
unacceptable, not a case to design around. Consequence of that choice: on API 29-30 the mic option is
hidden entirely and typed input is the only way in — a real, disclosed gap, not silently degraded to
an online recognizer just to keep the feature working everywhere.

There is no public, reliable *pre-flight* API to ask "is language X's offline pack installed" that
was safe to wire in here — see the TODO below. Instead, `VoiceInputHelper` discovers per-language
offline availability *empirically*, at the moment recognition is attempted:
`SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED` / `ERROR_LANGUAGE_UNAVAILABLE` (API 31+) are treated
as persistent ("hide the mic option for this session, don't invite a retry loop"), while
`ERROR_NO_MATCH`/`ERROR_SPEECH_TIMEOUT`/etc. are treated as transient (retry is fine).

**TODO (not implemented, deliberately):** `SpeechRecognizer.checkRecognitionSupport()` plus
`RecognitionSupport.supportedOnDeviceLanguages` / `installedOnDeviceLanguages` (API 33+) would give a
genuine pre-flight per-language check instead of the attempt-then-react approach above — ask once
before even offering the mic button whether the current language is supported/installed, rather than
opening the mic and finding out from an error. Not added in this change: its exact method signatures
(parameter types, callback shape) could not be verified against a real Android SDK in the environment
this change was written in — no JDK/Gradle/compiler available (see the note above) — and shipping a
guessed compile-time API surface was judged a worse failure mode (a broken build) than the plainer,
verified approach actually shipped. Pick this up once there's a real device/SDK/compiler to check the
signatures against — verify `RecognitionSupportCallback`'s exact abstract methods and
`RecognitionSupport`'s exact field/getter names directly against
`android.speech.RecognitionSupport`/`RecognitionSupportCallback` in a real `compileSdk 34` environment
before writing the call, then wire it into `VoiceInputHelper.startListening()` ahead of the existing
try/attempt path on API 33+, keeping the current attempt-then-react path as the fallback for API
31-32 (where no such pre-flight query exists at all).

### 11.2 TTS — automatic voice selection (`tts/SpeechLanguageSelector.kt`)

`WarningActivity`'s `speak()` previously always used the one fixed `AppSettings.spokenLanguageTag`
regardless of what language the actual headline/reason text was in. It now runs the text through ML
Kit Language Identification (`com.google.mlkit:language-id`, on-device model bundled in the app —
no network call, no text leaves the device for this) before every `speak()` call, and picks whichever
locale is actually usable: detected language first, `spokenLanguageTag` as fallback, and if neither
has an installed TTS voice, leaves the engine's current locale alone rather than forcing something
unavailable. Applies to both existing speech call sites (the headline on open, and the panic-outcome
text) with no new call sites added.

### 11.3 Per-language coverage, honestly (12 languages: English, Hindi, Bengali, Marathi, Telugu,
Tamil, Gujarati, Urdu, Kannada, Malayalam, Punjabi, Odia)

**This section is a documentation-time assessment, not an empirical device test** — this environment
has no JDK/Gradle/emulator (see the note above), so nothing in this change could actually be
installed and run on a device or emulator. What follows is based on Android/Google's public
documentation and current reporting, cross-checked via web search while writing this section, not
assumed from training memory alone — but it is still a *claim about typical device behavior*, not a
measurement of this specific app on this specific hardware.

- **TTS (Google's Speech Services / Google Text-to-Speech engine, downloadable voice data):**
  broad coverage is plausible across all 12 — English and Hindi are solid; Bengali, Marathi, Telugu,
  Tamil, Gujarati, Kannada, Malayalam, Punjabi, Urdu, and Odia all appear as supported Google TTS
  languages in current public references. Actual availability on a given phone still depends on the
  installed Google app/TTS engine version and whether the user has downloaded that language's voice
  data (Settings → Text-to-speech → Install voice data) — `SpeechLanguageSelector.isUsable()` checks
  this per-device at runtime via `tts.isLanguageAvailable()` rather than assuming any language is
  present, so an uninstalled voice degrades to the fallback language, not a crash or silent English.
- **STT, genuinely on-device (`createOnDeviceSpeechRecognizer`, what this app actually uses):**
  coverage here is materially narrower and not well-documented publicly per language. **English is
  the only language with confident, broadly-available on-device support today.** Hindi has partial,
  growing, device-dependent support (newer Android versions/Pixel devices). For the remaining ten
  target languages (Bengali, Marathi, Telugu, Tamil, Gujarati, Kannada, Malayalam, Punjabi, Urdu,
  Odia), there is no confirmed, reliable on-device recognition today — Google's own rollout of
  broader on-device language coverage (e.g. a Gemini Nano-based "advanced mode") is, as of this
  writing, restricted to specific newer devices, not general availability. In practice: most users
  speaking one of those ten languages into the mic on this screen will hit
  `ERROR_LANGUAGE_UNAVAILABLE`/`ERROR_LANGUAGE_NOT_SUPPORTED` today and fall back to typed text, by
  design, not by bug.
- **Online fallback (Sarvam or similar) — not implemented.** Closing the ten-language STT gap above
  with an online Indian-language STT/TTS provider is the natural next step, but it means audio or
  text leaving the device to a third party, which is a deliberate architectural/privacy decision this
  change does not make unilaterally — same posture as CLAUDE.md's existing hard constraints on data
  boundaries. Flagged here as a real, live gap for an explicit future decision, not silently designed
  around.

---

## 12. First real build/install/launch against a physical device (this superseded Sections
10-11's "no JDK/Gradle/emulator in this environment" caveats)

A JDK 17 + Android SDK toolchain became available at `D:\rakshak-android-toolchain`
(`env.sh` sets `JAVA_HOME`/`ANDROID_HOME`/`GRADLE_USER_HOME` etc. — source it before any
`./gradlew` invocation). This section documents the first actual `./gradlew installDebug`
onto real hardware and the two real bugs it surfaced — both fixed, both applicable
regardless of which physical device or network this app is tested on next.

### 12.1 `AndroidManifest.xml` had invalid XML (real bug, not a toolchain issue)

Two doc-comments used a literal `--` inside an XML comment body (`"...screen only --
always..."`, `"...recognizer API -- below it..."`) — invalid per the XML spec (comments may
not contain `--`), and Android's manifest merger correctly refused to parse the file
(`SAXParseException: The string "--" is not permitted within comments`, line 37). This had
never been caught because nothing had compiled the manifest before. Fixed by replacing both
with em-dashes (`—`), matching the style already used everywhere else in the file's
comments. Watch for this in future long-form doc-comments inside XML — Markdown-style `--`
as an em-dash substitute is fine in `.md`/`.kt` but breaks XML comments outright.

### 12.2 Physical-device Prahari connectivity: LAN IP blocked by Windows Firewall,
`adb reverse` used instead

Section 5's "`adb reverse tcp:8000 tcp:8000` etc. for a physical device" guidance was
correct in spirit but under-specified two things this session had to work out by hitting
them:

1. **`network_security_config_debug.xml` only ever whitelisted cleartext HTTP to
   `10.0.2.2`** (the emulator alias). Pointing a physical device at any other host —
   LAN IP or loopback — was silently blocked by Android's cleartext-traffic policy
   (surfaces to the app as an `IOException`, indistinguishable from a real connectivity
   failure without checking `logcat` for `CleartextNotPermittedException`). Fixed by adding
   `127.0.0.1` to the same debug-only `cleartextTrafficPermitted` domain-config (not the LAN
   IP — see next point for why).
2. **The dev machine's LAN IP (`192.168.1.3:8000`/`:8001`) was reachable from the PC itself
   but not from the phone** — `adb shell nc -z <LAN-IP> 8000` timed out from the device side
   even though `curl 127.0.0.1:8000` worked locally. Root cause: Windows Firewall has no
   inbound-allow rule for the ad-hoc `python -m api.server` / `uvicorn` processes, and this
   session didn't have the elevated permissions to add one (`Get-NetFirewallRule` itself
   returned Access Denied). Rather than asking for admin rights to poke a hole in the
   firewall, used `adb reverse tcp:8000 tcp:8000` / `tcp:8001 tcp:8001` instead — that tunnels
   through the already-authenticated adb transport (works the same over wireless-debugging
   adb as over USB) and appears to the Python server as a loopback connection, sidestepping
   the inbound-LAN firewall rule question entirely. The app's stored `prahari_base_url` /
   `evidence_base_url` (`AppSettings`, `SharedPreferences` key `rakshak_settings` — there is
   no in-app settings UI to edit these yet, see Section 10/MainActivity's `baseUrlValue` being
   read-only) were set to `http://127.0.0.1:8000` / `:8001` accordingly, not the LAN IP.

**Operational consequence for next time**: `adb reverse` is scoped to the adb connection, not
persisted — after any adb server restart, device reconnect/re-pair (wireless-debugging pairing
codes are short-lived and this device's USB-adb driver was independently flaky this session,
see below), or app reinstall, `adb reverse tcp:8000 tcp:8000` / `tcp:8001 tcp:8001` must be
re-run before the app can reach Prahari again. The backend processes themselves
(`python -m api.server 8000`, `uvicorn webhook.app:app --port 8001`) are unaffected by any of
this and can stay running across reconnects.

### 12.3 This device's USB-ADB driver was unreliable; wireless debugging was used instead

Windows Device Manager showed the phone's `ADB Interface`/`USB Composite Device` stuck at
driver status `Unknown` (not `OK`), and `adb devices` flapped between `offline` /
`unauthorized` / briefly `device` regardless of server restarts or reconnects — a genuine
driver-binding problem, not a one-off cable glitch. Switched to wireless debugging
(`adb pair <ip>:<port> <code>`, then it auto-connects via mDNS) for the rest of the session,
which was stable. If USB adb is wanted again later, this needs an actual driver
reinstall/replace in Device Manager (not attempted — no admin elevation available this
session) before trusting it over wireless debugging.
