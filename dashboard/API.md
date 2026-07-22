# Rakshak Investigator Dashboard — REST API

Base URL (local demo): `http://127.0.0.1:8002/api/v1`

This is a **separate process/port** from the citizen-facing backend
(`api.server` on 8000, `webhook.app` on 8001) — nothing here touches
those, `ml/detector.py`, or `casefile/case_generator.py`. Read-only
throughout. Data is demo-scale seed data (real `feedback.db` corrections +
`rakshak_eval_testset.json` scored through the live detector), not live
production volume — see `GET /meta`.

Interactive docs (Swagger UI / ReDoc), generated automatically from the
same models as this file, are available once the server is running:

- `http://127.0.0.1:8002/docs`
- `http://127.0.0.1:8002/redoc`

All endpoints return `application/json`. There is no authentication — this
is a local investigator tool, not deployed as a public service.

---

## `GET /meta`

Dataset scale and standing disclaimers. Call this first if you're
integrating elsewhere — the `data_scale_note` and `location_disclaimer`
strings are meant to be surfaced verbatim next to any UI built on this
data, not silently dropped.

```
curl http://127.0.0.1:8002/api/v1/meta
```

```json
{
  "total_reports": 37,
  "total_clusters": 32,
  "data_scale_note": "Demo-scale seed data only ...",
  "location_disclaimer": "Circle/city data shows where a NUMBER's telecom circle is allocated ..."
}
```

---

## `GET /clusters`

All fraud-script clusters (connected components over shared-script /
shared-callback-number / temporal-proximity edges — see
`dashboard/graph_model.py`).

| Query param | Type | Default | Meaning |
|---|---|---|---|
| `min_size` | int | 1 | Only return clusters with at least this many members |

```
curl "http://127.0.0.1:8002/api/v1/clusters?min_size=2"
```

```json
[
  {
    "cluster_id": 0,
    "size": 4,
    "members": ["+911234567890", "+917838073923", "+919876500001", "+919876543299"],
    "rule_categories": ["authority_impersonation", "isolation_tactics", "urgency_coercion"],
    "telecom_circles": ["Delhi NCR", "Punjab", "Unknown circle (unmapped or invalid prefix)"]
  }
]
```

## `GET /clusters/{cluster_id}`

Single cluster by id. `404` if it doesn't exist.

```
curl http://127.0.0.1:8002/api/v1/clusters/0
```

---

## `GET /reports`

List reports (one per node/phone number), optionally filtered.

| Query param | Type | Meaning |
|---|---|---|
| `circle` | string | Exact `telecom_circle` name, e.g. `Delhi NCR` |
| `cluster_id` | int | Only reports in this cluster |
| `source` | `feedback_db` \| `eval_testset_synthetic` | Real logged correction vs. real-detector-scored test case with a synthetic phone number |
| `rule_category` | string | Only reports whose `rule_categories` includes this value |

```
curl "http://127.0.0.1:8002/api/v1/reports?circle=Delhi%20NCR"
curl "http://127.0.0.1:8002/api/v1/reports?rule_category=otp_readout_request"
```

```json
[
  {
    "node_id": "+917838073923",
    "source": "feedback_db",
    "risk_level": "FRAUD",
    "score": null,
    "rule_categories": ["authority_impersonation", "urgency_coercion"],
    "text_excerpt": "This is CBI officer, your Aadhaar is linked to money laundering, do not disconnect",
    "channel": "whatsapp",
    "timestamp_utc": "2026-07-06T15:15:27.187693+00:00",
    "timestamp_is_synthetic": false,
    "telecom_circle": "Delhi NCR",
    "self_reported_city": null,
    "self_reported_state": null,
    "cluster_id": 0
  }
]
```

`score` is `null` for `feedback_db` rows because `feedback/store.py` does
not persist the numeric detector score at correction time, only the
verdict — not a bug, just what's actually logged.

## `GET /reports/{node_id}`

Single report by phone number (URL-encode the `+`). `404` if unknown.

```
curl "http://127.0.0.1:8002/api/v1/reports/%2B917838073923"
```

---

## `GET /circles`

Report counts by telecom circle, with the circle's approximate centroid
(principal-city coordinates, for map display — **not** a scammer or victim
location; see `location_disclaimer` in `/meta`).

```
curl http://127.0.0.1:8002/api/v1/circles
```

```json
[
  {
    "circle": "Punjab",
    "report_count": 2,
    "centroid_lat": 30.7333,
    "centroid_lng": 76.7794,
    "node_ids": ["+919876500001", "+919876543299"]
  }
]
```

---

## `GET /jurisdiction`

**Jurisdiction-based routing — not location tracking.** Looks up the
correct state/UT cybercrime-cell nodal-officer contact from a **citizen's
self-reported state and/or city only**. Never derives a state from a phone
number or telecom circle — that fallback does not exist in this codebase.
Meant to be surfaced **alongside** 1930/NCRP, never as a replacement (see
`national_escalation` in every response).

| Query param | Type | Meaning |
|---|---|---|
| `state` | string | Self-reported state/UT name or common alias (e.g. `MH`, `Maharashtra`) |
| `city` | string | Self-reported city, used only if `state` is absent/unrecognized (small explicit city→state table, ~35 major cities — not a geocoder) |

**Resolved example:**
```
curl "http://127.0.0.1:8002/api/v1/jurisdiction?state=Maharashtra"
```
```json
{
  "resolved": true,
  "resolved_via": "state",
  "state_or_ut": "Maharashtra",
  "contact": {
    "state_or_ut": "Maharashtra",
    "officer_name": "Sanjay Shintre",
    "designation": "DIG Cyber Crime",
    "phone": "022-22160080",
    "email": "dig.cbr-mah@gov.in",
    "source_url": "https://cybercrime.gov.in/Webform/Crime_NodalGrivanceList.aspx",
    "captured_on": "2026-07-17",
    "staleness_warning": "Officer name and direct phone number are as captured from the official portal on 2026-07-17 and may be outdated (nodal officer postings rotate with IPS/state-police transfers). The email domain and https://cybercrime.gov.in/Webform/Crime_NodalGrivanceList.aspx link are the most durable part of this record -- re-verify there before relying on a name or number for anything urgent."
  },
  "national_escalation": {
    "helpline": "1930",
    "portal": "https://cybercrime.gov.in",
    "note": "Always available regardless of state -- report here first/in parallel; the state contact above is a supplementary escalation channel, not a replacement."
  }
}
```

**No location provided:**
```
curl http://127.0.0.1:8002/api/v1/jurisdiction
```
```json
{
  "resolved": false,
  "reason": "location not provided",
  "state_or_ut": null,
  "contact": null,
  "national_escalation": { "helpline": "1930", "portal": "https://cybercrime.gov.in", "note": "..." }
}
```

**Unrecognized state/city** (`Atlantis`, or a city not in the small
lookup table) returns the same `resolved: false` shape with
`reason: "state/city text not recognized -- not guessed from any other signal"`
— it never falls back to guessing.

### Coverage and honest gaps — read before integrating this into anything user-facing

- **Source**: `dashboard/jurisdiction.py`'s table was captured verbatim
  from cybercrime.gov.in's own public "State/UT Nodal Officer & Grievance
  Officer" list on **2026-07-17**. All **36/36 states and UTs** are
  covered — this is a genuinely complete table from a single official
  source, not a partial one pieced together from blogs.
- **Phone number gaps**: 3 of 36 entries (**Andhra Pradesh, Chhattisgarh,
  Madhya Pradesh**) have no phone number on the official page as captured
  — email only. `phone` is `null` for these, not silently omitted.
- **Staleness is real and structural, not hypothetical**: nodal officers
  are IPS/state-police postings that rotate with transfers on a timescale
  of months. A spot-check against independent sources during this build
  surfaced *different* (also plausible) contact numbers for at least
  Delhi and Maharashtra at finer granularity (district cyber cell / city
  cyber police station, e.g. Mumbai Cyber PS's own helpline) than the
  state-nodal-officer level this table captures — both can be correct
  simultaneously (different granularity of contact), which is exactly why
  every entry carries a `captured_on` date and a `source_url` back to the
  live page rather than being presented as a permanent fact. **Treat the
  officer name and direct phone number as "was correct as of the capture
  date," and re-verify at the source URL before using either for anything
  urgent** — the email domain and the source URL itself are the durable
  parts of the record.
- **Granularity**: this is state/UT-level nodal contact only (matching
  what cybercrime.gov.in itself publishes as the authoritative
  escalation-of-last-resort per state). District-level cyber police
  stations and city-specific helplines exist in addition but are not
  covered here — a reasonable future extension, not built now.
- **What this deliberately does NOT do**: it never infers a state/circle
  from a phone number for this feature (`telecom_circles.py` is not even
  imported by `jurisdiction.py`), and the city→state fallback is a small
  explicit table of ~35 unambiguous major cities, not a geocoder — an
  unrecognized city is reported as unrecognized, never guessed.

---

## Error handling

- Unknown `cluster_id` / `node_id` → `404` with a JSON `{"detail": "..."}` body.
- Invalid query values (e.g. `min_size=0`) → `422` (FastAPI's standard validation error shape).
- Unrecognized `state`/`city` in `/jurisdiction` → **not** an error; `200` with `resolved: false` (see above).
