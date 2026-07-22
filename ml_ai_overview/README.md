# ml_ai_overview/

A curated, read-only **copy** of every source file that implements Rakshak-AI's ML/AI logic,
regrouped by functional role instead of by Python package / Android folder. This exists purely
as an organizational overview (e.g. for demoing/reviewing the AI architecture) — it changes
nothing about how the app or backend actually run.

**The original files are untouched and remain the source of truth.** Nothing under `/rag`,
`/ml`, `/voice`, `/graph`, `/casefile`, `/bot`, `/kb`, `/assistant`, `/llm`, `/api`, `/webhook`,
`/data`, `/feedback`, `/link`, `/geo`, or `/android` was moved or deleted — every file here is a
duplicate. Do not edit code under `ml_ai_overview/`; edit the original path and re-copy if this
overview needs to stay in sync.

## Taxonomy

The backend grouping mirrors the "PraHARI-AI agent role" table in the root `CLAUDE.md` (Section 1):

| Folder | Agent role | Original location(s) |
|---|---|---|
| `speech_intelligence/` | Speech Intelligence (scam-phrase/urgency detection) | `ml/detector.py`, `ml/llm_explainer.py`, `ml/export_offline_model.py`, `voice/voice_fraud.py` |
| `behavior_agent/` | Behavior (escalation/repetition across a session) | `ml/session.py` |
| `knowledge_rag/` | Knowledge/RAG (plain-language "why", sourced from the scam-card corpus) | `rag/*`, `kb/*`, `bot/*`, `assistant/*`, `llm/*` |
| `graph_intelligence/` | Graph Intelligence (cross-referencing fraud rings) | `graph/*` |
| `decision_agent/` | Decision Agent (fuses signals into a risk level) | `casefile/case_generator.py` |
| `additional_signal_detectors/` | Extra detection signals not in the original agent table | `link/url_safety.py`, `geo/geo_fraud.py` |
| `training_data_pipeline/` | How the training/knowledge corpora are built | `data/synth.py`, `data/classifier.py`, `data/scraper.py`, `data/dedup.py`, `data/merge.py`, `data/i4c_harvest.py`, `data/pib_harvest.py`, `data/pib_manual_cards.py` |
| `serving_layer/` | HTTP glue that exposes the agents above | `api/server.py`, `api/app_fastapi.py`, `webhook/app.py` |
| `evaluation/` | Test harnesses / gates referenced throughout `CLAUDE.md` | `eval_testset.py`, `eval_rag_testset.py`, `eval_chat_harness.py`, `eval_chat_testset.json`, `rakshak_eval_testset.json`, `check_pattern_parity.py`, `check_ml_scorer_parity.py` |
| `feedback_loop/` | User feedback capture (future retraining input) | `feedback/store.py` |

`app/` holds every AI-related Kotlin source file from the Android client
(`android/app/src/main/java/com/rakshak/ai/`), grouped by feature — mirroring that package's own
existing folder names:

| Folder | Feature | Original location |
|---|---|---|
| `call_screening/` | Pre-connect `CallScreeningService` (Tier 1) | `callscreening/` |
| `decision_intelligence/` | Client-side Decision Agent, caller lookup, Prahari API clients, ML scorer, offline rule engine, translated explanations | `intelligence/` (incl. `intelligence/translations/`) |
| `escalation/` | Tiers 2/3 escalation: complaint drafting, evidence capture, SMS/PDF delivery, timeout workers | `escalation/` |
| `location/` | Victim location capture for escalation | `location/` |
| `ocr/` | Screenshot text extraction feeding the detectors | `ocr/` |
| `sarvam/` | Sarvam speech/translation API client | `sarvam/` |
| `stt/` | Voice input (on-device + Sarvam) | `stt/` |
| `tts/` | Spoken warnings, language-aware voice selection | `tts/` |
| `ui/` | Every screen that surfaces an AI/ML outcome (warning card, check-a-call, main traffic light, NCRP complaint draft, safe result, etc.) | `ui/` |
| `shared_config/` | App-wide config consumed by the above (backend base URLs, language prefs, Application class) | `RakshakApp.kt`, `settings/AppSettings.kt` |

## Deliberately excluded (not missing — see reasoning)

A handful of files under the original ML/AI directories were **not** copied here, on purpose:

- **Empty/boilerplate `__init__.py` package markers** (all 0 bytes except `llm/__init__.py`,
  which is a 2-line re-export) — no logic to show.
- **Generated vector-index binaries** — `rag/faiss_store/`, `rag/chroma_store/`,
  `rag/legal_faiss_store/`. These are build *output* of `rag/build_store.py` /
  `rag/build_legal_store.py` (both of which *are* copied), not hand-written source, and are
  regenerated from `kb/scams.json` / `kb/legal_info.json`.
- **Scraped/intermediate data dumps** — `data/raw/*`, `data/classified/all_cards.json`,
  `data/final/new_cards.json`. These are the *output* of the scripts in `training_data_pipeline/`,
  not the pipeline logic itself.
- **Runtime data** — `feedback/data/feedback.db` (SQLite db, not code),
  `webhook/_evidence_files/*.pdf` (user-uploaded evidence from live sessions).

Every `.py`/`.kt`/`.json` file that contains actual ML/AI logic, prompts, or knowledge-base
content has a copy under this folder — see the tables above for the exact mapping.
