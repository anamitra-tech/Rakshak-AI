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
- No Gradle wrapper JAR is committed (this environment has no JDK/Gradle to generate one) — Android
  Studio will offer to create it on first open.
