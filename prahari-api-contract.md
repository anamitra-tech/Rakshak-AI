# Prahari API Contract

Source of truth for request/response shapes is `Backend/app/models/schemas.py`.
This doc is a human-readable summary — if the two ever disagree, the
schemas file wins.

Status key:
- **FINAL** — schemas, routes, and frontend wiring. Safe to build against.
- **PENDING AI/ML HANDOFF** — the route/schema shape is final, but the
  function behind it is a placeholder (fixed fake output) until the
  AI/ML developer's real file is dropped in. See the named
  `services/*_placeholder.py` file for the exact function signature
  their real file needs to match.

## 1. Unified classifier — `POST /api/analyze`

**Status: FINAL (schema/route) — PENDING AI/ML HANDOFF (intelligence)**
See `Backend/app/services/classifier_placeholder.py` for the exact
`classify(text: str, mode: str) -> dict` interface the real file must match.

One endpoint covers both Citizen Fraud Shield and digital-arrest-style
scams — there is no separate Digital Arrest model. Real digital-arrest
input (typed text, on-device STT via Sarvam, on-device OCR) all arrives
here as plain text with `source_type: "call_transcript"`.

Request:
```json
{
  "text": "string",
  "source_type": "sms | email | whatsapp | payment_request | call_transcript",
  "mode": "offline | online"
}
```
- `offline`: fast (~6-10ms), rule/ML only.
- `online`: slower (~3-5s), LLM-generated `reason` via Gemini with Groq fallback.

Response:
```json
{
  "risk_score": 0.0,
  "verdict": "SAFE | SUSPICIOUS | SCAM",
  "categories": ["authority_impersonation", "..."],
  "reason": "single string, never a list"
}
```
Categories (provisional — confirm against AI/ML dev's `API_SPEC.md §1.2`):
`authority_impersonation`, `credential_request`, `urgency_coercion`,
`money_demand`, `reward_bait`, `isolation_tactics`,
`otp_readout_request`, `card_collection_request`,
`relative_impersonation`, `telecom_impersonation`, `extortion_threat`,
`malicious_link_bait`, `malware_attachment_delivery`.

Empty input always returns a fixed SAFE result. Otherwise always a real
result — never null/error.

## 2. Entity extraction — `POST /api/extract_entities`

**Status: FINAL (schema/route) — PENDING decision (may be written in-house)**
See `Backend/app/services/entity_extraction_placeholder.py` for the exact
`extract_entities(text: str) -> dict` interface.

Separate from `/api/analyze`, not bundled into it.

Request: `{ "text": "string" }`

Response:
```json
{
  "phone_numbers": ["string"],
  "upi_ids": ["string"],
  "bank_accounts": ["string"],
  "urls": ["string"]
}
```

## 3. Fraud Network Intelligence

**Status: FINAL (schema/route) — PENDING AI/ML HANDOFF (intelligence)**
See `Backend/app/services/graph_placeholder.py` for the exact
`get_graph() -> dict` / `get_clusters() -> dict` interface.

NetworkX-based, in-memory, computed per request — no Neo4j, no pagination.

`GET /api/network/graph`:
```json
{
  "nodes": [
    {"id": "string", "phone_number": "string", "category": "string", "region": "string", "risk_score": 0.0}
  ],
  "edges": [
    {"source": "string", "target": "string", "reason": "string"}
  ]
}
```

`GET /api/network/clusters`:
```json
{
  "clusters": [
    {"id": "string", "node_ids": ["string"], "risk_score": 0.0, "summary": "string"}
  ]
}
```

## 4. Geospatial Crime Intelligence

**Status: FINAL** — synthetic/generated demo data only, no real backend
intelligence pending. Full map dashboard (heatmap, clustering,
choropleth, filters, trend chart) lives under
`Frontend/src/Dashboard/CommandWorkSpace/geospatial/`, wired into
`GeoSpatial.jsx`. District boundary GeoJSON is bundled on the frontend
at `Frontend/src/assets/geo/india_districts.geojson` (simplified from a
public India district boundary dataset) — not provided by the backend.
Mock complaint `district` values are chosen to match that file's
`district` property so stats can be joined onto map polygons by name.

- `GET /api/geo/complaints?scam_type=<repeatable>&start_date=&end_date=&district=`
  → `GeoComplaintsResponse` (`ComplaintPoint[]`: lat, lng, scam_type,
  amount, risk_score, date, district)
- `GET /api/geo/districts/stats?scam_type=<repeatable>&start_date=&end_date=`
  → `GeoDistrictStatsResponse` (`DistrictStat[]`: district_id,
  complaint_count, risk_score [0-100, complaints/population normalized],
  top_scam_type, trend, trend_delta_pct vs the preceding period of equal length)
- `GET /api/geo/trend?scam_type=<repeatable>&start_date=&end_date=`
  → `GeoTrendResponse` (daily `series`, per-scam-type `by_scam_type` with
  growth_rate_pct, and `trending_scam_type` — fastest-growing in the period)
- `GET /api/geo/scam-types` → `GeoScamTypesResponse` (canonical list: UPI
  Fraud, Phishing, Investment Scam, Loan App Fraud, KYC Fraud, Job Fraud,
  Digital Arrest — used to populate the filter panel)

See `Backend/app/services/geo_service.py` for the generated dataset
(680 complaints across 15 districts over the last 120 days) and
`Backend/app/models/schemas.py` for exact shapes.

## 5. Auth

**Status: FINAL.** `POST /api/auth/google`, `GET /api/auth/me`,
`POST /api/auth/logout` — see `GoogleAuthRequest` / `UserResponse` in schemas.py.

## Removed in this pass

- `POST /api/citizen/analyze`, `POST /api/citizen/analyze-file` — replaced
  by the unified `POST /api/analyze`.
- `POST /api/digital-arrest/analyze` — replaced by the unified
  `POST /api/analyze` with `source_type: "call_transcript"`. No audio
  upload, no Whisper transcription — those pipelines are gone.
- All Neo4j driver/query files (`app/db/neo4j_driver.py`,
  `app/db/queries.py`, `app/services/neo4j_service.py`) — confirmed not
  part of the real stack (NetworkX instead).
