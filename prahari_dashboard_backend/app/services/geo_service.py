"""
Complaint geodata + district aggregation for the Geospatial Crime
Intelligence module.

Uses a seeded, generated in-memory dataset -- there is no Neo4j (or any
other DB) in this stack; see prahari-api-contract.md. If complaints ever
move into real storage, swap the dataset/query logic below for real
lookups -- the response shapes (schemas.py) stay the same.

`district` values are chosen to match the `district` property in the
frontend's bundled boundary file (src/assets/geo/india_districts.geojson)
so district stats can be joined onto map polygons by name.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

SCAM_TYPES = [
    "UPI Fraud",
    "Phishing",
    "Investment Scam",
    "Loan App Fraud",
    "KYC Fraud",
    "Job Fraud",
    "Digital Arrest",
]

# name -> (lat, lng, approx population) — centroids taken from the bundled
# district boundary file; populations are rough real-world estimates, used
# only to normalize complaint density into a 0-100 risk score.
DISTRICTS = {
    "Delhi": (28.6499, 77.1095, 16_800_000),
    "Gautam Buddha Nagar": (28.3849, 77.5175, 1_650_000),
    "Greater Bombay": (19.1374, 72.9079, 12_400_000),
    "Bangalore Urban": (12.9151, 77.5858, 9_600_000),
    "Lucknow": (26.8691, 80.8781, 2_800_000),
    "Chennai": (13.0552, 80.2350, 4_600_000),
    "Hyderabad": (17.3986, 78.4731, 3_900_000),
    "Kolkata": (22.5561, 88.3514, 4_500_000),
    "Pune": (18.5075, 74.2081, 9_400_000),
    "Jaipur": (27.0408, 75.7609, 3_100_000),
    "Patna": (25.4118, 85.2979, 2_000_000),
    "Surat": (21.2326, 73.4398, 4_500_000),
    "Coimbatore": (10.8562, 77.0905, 2_100_000),
    "Thane": (19.6529, 73.1666, 1_800_000),
    "Kanpur": (26.3759, 80.3008, 2_900_000),
}

# Skews which scam types are more common in which districts, so "top scam
# type per district" isn't uniform noise.
_DISTRICT_SCAM_WEIGHTS = {
    "Delhi": [3, 2, 2, 1, 2, 1, 4],
    "Gautam Buddha Nagar": [2, 1, 1, 1, 1, 1, 5],
    "Greater Bombay": [3, 2, 4, 1, 2, 1, 2],
    "Bangalore Urban": [2, 3, 3, 1, 1, 3, 1],
    "Lucknow": [3, 2, 1, 3, 2, 1, 2],
    "Chennai": [2, 2, 2, 2, 3, 1, 1],
    "Hyderabad": [2, 2, 3, 1, 1, 2, 2],
    "Kolkata": [3, 3, 1, 2, 2, 1, 1],
    "Pune": [2, 2, 2, 2, 1, 3, 1],
    "Jaipur": [3, 1, 1, 3, 2, 1, 1],
    "Patna": [2, 1, 1, 4, 2, 1, 1],
    "Surat": [2, 1, 3, 1, 1, 1, 1],
    "Coimbatore": [2, 1, 1, 1, 1, 2, 1],
    "Thane": [2, 1, 2, 1, 1, 1, 1],
    "Kanpur": [2, 1, 1, 2, 2, 1, 1],
}

_AMOUNT_RANGE = {
    "UPI Fraud": (500, 25_000),
    "Phishing": (1_000, 50_000),
    "Investment Scam": (20_000, 1_000_000),
    "Loan App Fraud": (2_000, 80_000),
    "KYC Fraud": (1_000, 40_000),
    "Job Fraud": (5_000, 150_000),
    "Digital Arrest": (50_000, 2_000_000),
}

_TOTAL_DAYS = 120
_COMPLAINTS_PER_DAY = 6
_SEED = 42


def _generate_complaints() -> list[dict]:
    rng = random.Random(_SEED)
    today = date.today()
    complaints = []

    for day_offset in range(_TOTAL_DAYS, -1, -1):
        day = today - timedelta(days=day_offset)
        # gentle upward drift for "Digital Arrest" and "Investment Scam" so
        # the trend chart / trending-scam-type indicator has something to show
        drift = 1.0 + (0.6 * (1 - day_offset / _TOTAL_DAYS))
        n_today = max(1, int(rng.gauss(_COMPLAINTS_PER_DAY, 2)))

        for _ in range(n_today):
            district = rng.choice(list(DISTRICTS.keys()))
            lat0, lng0, _pop = DISTRICTS[district]
            weights = list(_DISTRICT_SCAM_WEIGHTS[district])
            weights[2] *= drift  # Investment Scam
            weights[6] *= drift  # Digital Arrest
            scam_type = rng.choices(SCAM_TYPES, weights=weights, k=1)[0]

            lo, hi = _AMOUNT_RANGE[scam_type]
            amount = round(rng.uniform(lo, hi), 2)
            severity = min(1.0, amount / hi)
            risk_score = int(min(100, max(5, severity * 70 + rng.uniform(0, 30))))

            complaints.append({
                "lat": round(lat0 + rng.uniform(-0.08, 0.08), 5),
                "lng": round(lng0 + rng.uniform(-0.08, 0.08), 5),
                "scam_type": scam_type,
                "amount": amount,
                "risk_score": risk_score,
                "date": day.isoformat(),
                "district": district,
            })

    return complaints


_COMPLAINTS = _generate_complaints()


def get_scam_types() -> list[str]:
    return list(SCAM_TYPES)

def add_complaint(complaint: dict):
    _COMPLAINTS.append(complaint)

def mock_geocode(location_str: str) -> tuple[float, float, str]:
    """
    Mock geocoder. Matches a district string to a known district.
    If no match, defaults to Delhi.
    Returns (lat, lng, district_name).
    """
    if not location_str:
        return DISTRICTS["Delhi"][0], DISTRICTS["Delhi"][1], "Delhi"
        
    loc_lower = location_str.lower()
    for d in DISTRICTS.keys():
        if d.lower() in loc_lower:
            return DISTRICTS[d][0], DISTRICTS[d][1], d
            
    # Default to Delhi if not found
    return DISTRICTS["Delhi"][0], DISTRICTS["Delhi"][1], "Delhi"


def _parse_date(s: str | None) -> date | None:
    return datetime.strptime(s, "%Y-%m-%d").date() if s else None


def _filter(
    complaints: list[dict],
    scam_types: list[str] | None,
    start_date: str | None,
    end_date: str | None,
    district: str | None = None,
) -> list[dict]:
    results = complaints
    if scam_types:
        wanted = {s.lower() for s in scam_types}
        results = [c for c in results if c["scam_type"].lower() in wanted]
    if district:
        results = [c for c in results if c["district"].lower() == district.lower()]
    if start_date:
        results = [c for c in results if c["date"] >= start_date]
    if end_date:
        results = [c for c in results if c["date"] <= end_date]
    return results


def get_complaints(
    scam_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    district: str | None = None,
) -> list[dict]:
    return _filter(_COMPLAINTS, scam_types, start_date, end_date, district)


def _period_bounds(start_date: str | None, end_date: str | None) -> tuple[date, date]:
    end = _parse_date(end_date) or date.today()
    start = _parse_date(start_date) or (end - timedelta(days=29))
    return start, end


def get_district_stats(
    scam_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    start, end = _period_bounds(start_date, end_date)
    period_len = (end - start).days + 1
    prev_start = start - timedelta(days=period_len)
    prev_end = start - timedelta(days=1)

    current = _filter(_COMPLAINTS, scam_types, start.isoformat(), end.isoformat())
    previous = _filter(_COMPLAINTS, scam_types, prev_start.isoformat(), prev_end.isoformat())

    by_district_current: dict[str, list[dict]] = {}
    for c in current:
        by_district_current.setdefault(c["district"], []).append(c)

    prev_counts: dict[str, int] = {}
    for c in previous:
        prev_counts[c["district"]] = prev_counts.get(c["district"], 0) + 1

    # raw density = complaints per 100k population over the period
    raw_density = {}
    for district, (_lat, _lng, population) in DISTRICTS.items():
        count = len(by_district_current.get(district, []))
        raw_density[district] = (count / population) * 100_000

    max_density = max(raw_density.values()) if raw_density else 0

    stats = []
    for district in DISTRICTS:
        complaints = by_district_current.get(district, [])
        count = len(complaints)

        scam_counts: dict[str, int] = {}
        for c in complaints:
            scam_counts[c["scam_type"]] = scam_counts.get(c["scam_type"], 0) + 1
        top_scam_type = max(scam_counts, key=scam_counts.get) if scam_counts else None

        prev_count = prev_counts.get(district, 0)
        if prev_count == 0:
            trend_delta_pct = 100.0 if count > 0 else 0.0
        else:
            trend_delta_pct = round(((count - prev_count) / prev_count) * 100, 1)

        if trend_delta_pct > 5:
            trend = "up"
        elif trend_delta_pct < -5:
            trend = "down"
        else:
            trend = "flat"

        risk_score = round((raw_density[district] / max_density) * 100, 1) if max_density else 0.0

        stats.append({
            "district_id": district,
            "complaint_count": count,
            "risk_score": risk_score,
            "top_scam_type": top_scam_type,
            "trend": trend,
            "trend_delta_pct": trend_delta_pct,
        })

    return stats


def get_trend(
    scam_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    start, end = _period_bounds(start_date, end_date)
    filtered = _filter(_COMPLAINTS, scam_types, start.isoformat(), end.isoformat())

    all_days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]

    total_by_day: dict[str, int] = {d: 0 for d in all_days}
    by_type_by_day: dict[str, dict[str, int]] = {
        t: {d: 0 for d in all_days} for t in SCAM_TYPES
    }
    for c in filtered:
        total_by_day[c["date"]] = total_by_day.get(c["date"], 0) + 1
        by_type_by_day[c["scam_type"]][c["date"]] = by_type_by_day[c["scam_type"]].get(c["date"], 0) + 1

    series = [{"date": d, "count": total_by_day[d]} for d in all_days]

    midpoint = len(all_days) // 2 or 1
    by_scam_type = []
    growth_rates: dict[str, float] = {}
    for t in SCAM_TYPES:
        if scam_types and t.lower() not in {s.lower() for s in scam_types}:
            continue
        points = [{"date": d, "count": by_type_by_day[t][d]} for d in all_days]
        first_half = sum(p["count"] for p in points[:midpoint]) or 0
        second_half = sum(p["count"] for p in points[midpoint:]) or 0
        if first_half == 0:
            growth_rate_pct = 100.0 if second_half > 0 else 0.0
        else:
            growth_rate_pct = round(((second_half - first_half) / first_half) * 100, 1)
        growth_rates[t] = growth_rate_pct
        by_scam_type.append({
            "scam_type": t,
            "points": points,
            "growth_rate_pct": growth_rate_pct,
        })

    trending_scam_type = max(growth_rates, key=growth_rates.get) if growth_rates else None

    return {
        "series": series,
        "by_scam_type": by_scam_type,
        "trending_scam_type": trending_scam_type,
    }
