# head.md — working state / handoff notes

Note-to-self doc for picking this project back up. Not user-facing docs (that's
CLAUDE.md / README.md) — this is "what did I just do, what's dangling, what
did I get wrong." Update this file at the end of each work session instead of
trusting memory of the conversation.

Repo: `D:/et-ai-hackathon-Madhav-wins/Rakshak-AI`, branch `main`. Latest work
below is about to be committed on top of `bdb8d48` — check `git log` for the
actual current HEAD rather than trusting this number once stale.

---

## ⚠️ BLOCKED — pick this up first if resuming

**Live end-to-end test of the Tier 2/3b manual-check auto-escalation (item 4
below) is not done.** I asked the user for two real phone numbers and got no
answer yet before the session moved to committing:

1. **Auto-dial test number** for `tier3bPhoneNumber` — the countdown in
   `AutoEscalationCountdownActivity` places a real `Intent.ACTION_CALL` when
   it elapses (not just opens the dialer). Must NOT be `1930`. Do not guess
   one — ask the user.
2. **Trusted contact name + real phone number** for the Tier 2
   SMS-with-draft-complaint test (`EscalationOrchestrator.notifyTrustedContact`)
   — sends one real SMS via `SmsManager` to whatever number is configured.

Once both are provided: set them via `adb shell run-as com.rakshak.ai` into
`shared_prefs/rakshak_settings.xml` (keys `tier3b_phone_number`,
`trusted_contact_name`, `trusted_contact_phone` — see `AppSettings.kt`'s
companion object for the exact key strings), grant `CALL_PHONE`,
`READ_PHONE_STATE`, `SEND_SMS` via `adb shell pm grant`, force-stop + relaunch
the app, paste the CBI/digital-arrest scam text into "Check a call/message",
submit, and confirm: countdown UI appears, Cancel button works if tapped,
auto-dial fires on non-cancel, and `adb logcat` shows
`RakshakEscalation: SMS sent-report for <id>: sent=true` (not just "no
error" — that exact log line, from `SmsSentReceiver.kt`, is the delivery
bar this project holds itself to, matching the WhatsApp test precedent in
item 1 below).

As of this note, device state is: no trusted contact configured, no
`CALL_PHONE`/`READ_PHONE_STATE`/`SEND_SMS` granted, `tier3bPhoneNumber` blank
(debug-build default). Backend (`api.server`:8000, `webhook.app`:8001) and
`adb reverse tcp:8000`/`tcp:8001` were both up as of the last check in this
session — re-verify both before testing if picking this up later, they don't
survive a reboot/reconnect.

---

## Completed (committed + pushed to origin/main)

### 4. Tier 2/3b auto-escalation now also fires from the manual "Check a
call/message" screen, not just live incoming calls
- **Original behavior** (confirmed by reading the code before changing
  anything): a FRAUD/HIGH verdict from `CheckCallActivity` only
  auto-triggered Tier 2 SMS + Tier 3b auto-dial if BOTH `tier3bEnabled` was
  on AND a near-deterministic rule fired (`DecisionAgent.hasNearDeterministicSignal`).
  Otherwise it fell through to `WarningActivity`, requiring a manual "I need
  help" tap for SMS and a further tap on "Call 1930" (`ACTION_DIAL`, not an
  auto-dial) for Tier 3.
- **Changed**: `CheckCallActivity`'s trigger condition is now simply
  `decision.riskLevel == RiskLevel.HIGH` — any FRAUD-level verdict from this
  screen routes straight into the **existing, unmodified**
  `AutoEscalationCountdownActivity` (10s cancellable countdown → auto-dial +
  Tier 2 SMS "at the same time"). No new escalation logic was written; only
  the trigger condition changed — `EscalationOrchestrator.notifyTrustedContact()`
  and the `ACTION_CALL` intent are reused exactly as they already existed for
  the near-deterministic-rule path.
- Deliberately **not** gated behind `tier3bEnabled` or
  `hasNearDeterministicSignal` anymore — user's explicit choice (see the
  AskUserQuestion exchange this session): "any HIGH-risk verdict... regardless
  of whether tier3bEnabled is on or the match was rule-based vs. ML-only."
  Consequence flagged to the user and accepted: in a **release build**
  (where `tier3bPhoneNumber` defaults to `"1930"` even without ever opening
  Family Setup, see `AppSettings.DEFAULT_TIER3B_NUMBER`), if `CALL_PHONE`
  permission were ever granted outside the guided Family Setup flow, a HIGH
  verdict could auto-dial 1930 without explicit opt-in. Narrow edge case
  (permission is normally only requested via that flow) but real — not
  fixed, just documented.
- `NEAR_DETERMINISTIC_RULE_CATEGORIES` / `hasNearDeterministicSignal` in
  `DecisionAgent.kt` are now unused dead code (no call sites left) —
  deliberately NOT deleted, kept as the documented cross-platform mirror of
  `ml/detector.py`'s `NEAR_DETERMINISTIC_RULES` in case a more targeted gate
  is reintroduced later. Comments updated to say so explicitly rather than
  leave a stale "this is what gates Tier 3b" claim.
- **New, separate change bundled in the same diff**: trusted-contact
  weighting. A call/message whose number matches the family's configured
  `trustedContactPhone` now steps `DecisionAgent`'s risk level down one notch
  (HIGH→MEDIUM→LOW) instead of leaving it untouched — user's explicit choice
  ("weight it, don't bypass" — a spoofed/compromised trusted-contact number
  should still surface *something*, not be silently waved through). Applied
  identically in both `RakshakCallScreeningService` (live pre-connect calls)
  and `CheckCallActivity` (manual check). Only ever compares against the
  single configured number — never a broader contacts/call-log scan, per
  CLAUDE.md's no-PII-harvesting rule. New shared `PhoneNumberUtils.kt`
  (`normalizePhoneNumber`) extracted so this and `MockCallerLookupSource`'s
  existing matching use identical normalization.
- **Mandatory eval gate run and PASSED**: `eval_testset.py` against
  `rakshak_eval_testset.json` (54 cases, not touched by this change — no
  Python file was modified) — 100% recall across every scam category,
  `false_positive_bait` FPR 0.040 (`fp24` only, the documented known-failing
  case). Byte-identical to the documented baseline, as expected since this
  was pure Android/Kotlin escalation-wiring, not detection logic.
- Built, installed (`./gradlew installDebug`), and launched clean on the
  physical device (no `FATAL EXCEPTION`) after these changes — but the live
  end-to-end escalation test itself is the item still blocked above.

### 3. First real build/install/launch on physical hardware — see CLAUDE.md

### 3. First real build/install/launch on physical hardware — see CLAUDE.md
Section 12 for full detail; summary here for quick recall.
- A JDK17+SDK toolchain now exists at `D:\rakshak-android-toolchain` (source
  `env.sh` before `./gradlew`) — the "no JDK/Gradle in this environment"
  caveat in CLAUDE.md Sections 10-11 is stale as of this session, corrected
  in Section 10's Gradle-wrapper bullet.
- Found and fixed a real bug: two `AndroidManifest.xml` doc-comments used
  literal `--` inside XML comments (invalid XML), which broke the manifest
  merger the first time anything ever actually compiled this manifest.
  Fixed → em-dashes, matching the rest of the file's comment style.
- Physical-device Prahari connectivity needed two fixes beyond what CLAUDE.md
  Section 5 already said: (1) `network_security_config_debug.xml` only
  whitelisted cleartext to `10.0.2.2`, not any physical-device address —
  added `127.0.0.1`; (2) the dev machine's LAN IP was reachable from the PC
  but blocked *inbound* by Windows Firewall from the phone's side (no admin
  rights available to add a firewall rule this session) — used
  `adb reverse tcp:8000 tcp:8000` / `tcp:8001 tcp:8001` instead, which
  tunnels through the adb transport and looks like loopback traffic to the
  Python servers, sidestepping the firewall question. App's stored
  `prahari_base_url`/`evidence_base_url` (SharedPreferences, no in-app UI to
  edit them yet) set to `127.0.0.1` accordingly via `adb shell run-as`.
- This phone's USB-ADB driver is unreliable (Device Manager: `ADB Interface`
  stuck at `Unknown` status, `adb devices` flapped offline/unauthorized).
  Switched to wireless debugging (`adb pair`) for the rest of the session —
  stable, but re-pairing may be needed if the connection drops, and
  `adb reverse` doesn't survive a reconnect (must be re-run).
- Backend confirmed running end-to-end: `python -m api.server 8000` and
  `uvicorn webhook.app:app --port 8001` both up, both reachable from the
  device through the reverse tunnel (`nc -z 127.0.0.1 8000/8001` both OK).
  App builds, installs, and launches cleanly (no `FATAL EXCEPTION`, process
  stays alive) as of `versionName 0.1.0-phase1`.
- **Not yet manually verified**: an actual successful `/analyze_voice` +
  `/analyze_session` round-trip through the "Check a call/message" UI itself
  — `CheckCallActivity` isn't `exported`, so it can't be launched directly
  via `adb shell am start` to script this; needs a real tap-through. Backend
  reachability and app process health are confirmed, the full UI flow is
  not, as of the point this note was written.

### 1. Feedback logging system — commit `469b41e`
- `feedback/store.py`: SQLite append-only store, two tables (`corrections`,
  `advisory_ingestions`). Write-only in practice — verified by grepping the
  whole repo for importers; only `log_correction`/`log_advisory_ingestion`
  are ever called, the `fetch_recent_*` read helpers have zero callers
  anywhere. Nothing in `ml/`, `voice/`, `casefile/`, `bot/`, `rag/` touches it.
- `POST /feedback` on both `api/server.py` (port 8000, Android's backend) and
  `webhook/app.py` (port 8001, WhatsApp's backend).
- WhatsApp: verdict replies now end with a "👍/👎 was this right?" prompt;
  next message from that session is checked against `_resolve_feedback()`
  before being treated as new text to classify. Correction direction
  (`not_a_scam` vs `should_have_been_flagged`) is inferred from the verdict
  that was shown, not asked again.
- Android: `CheckCallActivity` (LOW-risk inline result) and `WarningActivity`
  (MEDIUM/HIGH) both got a "Was this right?" disclosure styled like the
  existing `whyToggle` — deliberately NOT a second pinned button, to respect
  CLAUDE.md 9.2's "exactly one action button during an active warning" rule.
  `submitFeedback()` on `PrahariApiClient` is fire-and-forget.
- `data/scraper.py` logs every CSK/PIB/Sanchar-Saathi card it scrapes into
  `advisory_ingestions` as a separate append-only event log (distinct from
  the curated `kb/scams.json` merge output).
- Chakshu itself has **no public feed to ingest** — confirmed via web search,
  it's a one-way citizen→DoT report portal, no API/dataset. User chose to
  wire the *actual* real external pipeline (the CSK/PIB/SS scraper) into the
  ingestion log instead of faking a Chakshu integration.
- Tested end-to-end including a live send to the user's real WhatsApp number
  (+917838073923, already sandbox-joined) — verdict delivered, 👎 reply
  correctly logged as `not_a_scam` in SQLite, confirmed via Twilio's own
  delivery-status API (`delivered`, no error).

### 2. Three new HIGH_RISK_PATTERNS categories — commit `38dc123`
- `relative_impersonation`, `telecom_impersonation`, `extortion_threat` added
  to `ml/detector.py`, cross-referenced against Sanchar Saathi/Chakshu's
  *published category taxonomy* (not a data feed — see above) — documented
  in CLAUDE.md §6.3.
- `telecom_impersonation` folded into the existing authority_impersonation +
  money/credential critical-combo elevation (0.95). `relative_impersonation`
  gets its own combo bump when it co-occurs with `isolation_tactics`.
  `extortion_threat` is deliberately structural (every pattern requires a
  threat clause AND a payment clause together) — given a 0.85 floor for that
  reason, but **not** added to `NEAR_DETERMINISTIC_RULES` (that override is
  mirrored in Android's `DecisionAgent.NEAR_DETERMINISTIC_RULE_CATEGORIES`
  for Tier 3b gating — extending that cross-platform contract was explicitly
  left as a separate future decision, not bundled in here).
- `rakshak_eval_testset.json` grew 36 → 52 cases. Gated via `eval_testset.py`
  (with and without the LLM layer) and `eval_rag_testset.py` (RAG path) — all
  green: 100% recall, 0% FPR except one deliberate known-failure (next item).

---

## Known, deliberately-not-fixed issue

**`fp24` in `rakshak_eval_testset.json`** — a benign "beta, I sent your
college fees" message scores SUSPICIOUS (0.512) from the **base ML
classifier alone** (`rule_categories: []`, nothing to do with the three new
categories). Feature-attribution check confirmed the ~31-template baseline
associates `account`/`transfer`/`rupaye`/4-5-digit-amount words with FRAUD
regardless of tense or family context. Flagged `"known_failing": true` in
the JSON with a `known_failing_note`, and called out in the JSON's top-level
`notes` field so `eval_testset.py` reporting this as a false positive is
never mistaken for a new regression. **This is Day 2's problem** (retraining
pipeline target), not something to patch in the rule layer.

---

## Explicitly deferred / not done (don't assume these exist)

- **Day 2 retraining pipeline** doesn't exist yet. `feedback/store.py`
  corrections are being collected but nothing reads them back into training.
  When that pipeline gets built, it should be gated by the full
  `rakshak_eval_testset.json` suite (including clearing `fp24`) before
  anything gets promoted live — same discipline as today's rule-category
  work.
- **No kb/scams.json cards** for `relative_impersonation`,
  `telecom_impersonation`, or `extortion_threat` yet. RAG explanations for
  these currently borrow the nearest-neighbor existing card (e.g. digital
  arrest, lottery fraud) rather than a dedicated one — noticed during the
  `eval_rag_testset.py` run, not filed as a tracked issue anywhere yet.
- **Tier 3b / NEAR_DETERMINISTIC_RULES extension** for the three new
  categories — open question, not decided. Don't add `extortion_threat` etc.
  to Android's `NEAR_DETERMINISTIC_RULE_CATEGORIES` without also updating
  `ml/detector.py`'s `NEAR_DETERMINISTIC_RULES` and re-gating — they must
  move together.
- Everything CLAUDE.md Section 10 already lists as a known Phase 1 gap
  (mock Tier 2 contact notify, no Gradle wrapper committed, etc.) is still
  true and untouched by this work — not mine to fix unless asked.

---

## Mistakes made this stretch (so I don't repeat them)

1. **Sent a real WhatsApp message to a fabricated test number** during the
   first round of feedback-flow testing, using live Twilio credentials from
   `.env` — the sandbox almost certainly no-op'd it (unjoined number), but I
   should have used a controlled number from the start instead of inventing
   one. Caught it after the fact, disclosed it, stopped both test servers
   immediately. **Lesson: check `.env` for live credentials *before* writing
   test calls that hit external services, not after.**
2. **Used memory-file `[[wiki-link]]` syntax inside CLAUDE.md** (a project
   doc, not a memory file) — caught on the same turn and fixed. Lesson: that
   syntax is for `~/.claude/.../memory/*.md` only.
3. **First-draft regex bugs**, both caught by self-testing before promotion,
   not after:
   - `telecom_impersonation`'s disconnect pattern used bare `connection`,
     which also matched an *electricity* disconnection scam (`es8`) already
     in the eval set — tightened to require an explicit sim/mobile/telecom
     qualifier.
   - Three Hindi/Hinglish scam drafts (`rel2`, `tel2`, `ext2`) missed on
     first pass because the vocabulary list was too narrow (e.g. required
     "trouble" but the draft said "accident") — broadened after a scratch
     test run against my own drafted cases, before touching `detector.py`.
4. **`fp18`'s original wording accidentally tested the ML baseline, not my
   new rules** — didn't initially separate "is this regex correct" from "is
   this incidentally colliding with unrelated pre-existing model behavior."
   Once traced (via `decision_function`/coefficient inspection), reworded
   the passing case as `fp18` and kept the original as `fp24` instead of
   just quietly dropping it.
5. Two false alarms during testing that wasted a few minutes each — worth
   remembering as *not real bugs* if they recur: `curl -d "From=whatsapp:+91..."`
   silently mangles `+` into a space (application/x-www-form-urlencoded
   quirk) — use `httpx`/proper URL-encoding for any test involving `+` in a
   form body. And Windows console printing UTF-8 em-dashes as `�` is a
   **display-only** codepage issue, not data corruption — verify with
   `repr()`/explicit UTF-8 stdout before concluding the actual payload is
   broken.

---

## Session housekeeping note (probably irrelevant, flagging anyway)

Earlier in this stretch I got stray `<task-notification>` messages for
background commands (ngrok tunnel, uvicorn/api.server restarts) that I never
started — ignored them as leftover noise from another session sharing this
environment. If they recur, same call: don't act on a task-notification for
a task ID I don't recognize starting.
