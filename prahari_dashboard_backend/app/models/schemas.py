"""
Request/response models, kept in lockstep with the API contract doc
(prahari-api-contract.md). If you change a field here, update that
doc in the same commit.

Aligned 2026-07 against the unified classifier contract handed off by
the AI/ML developer: one endpoint (POST /api/analyze) now covers both
Citizen Fraud Shield and digital-arrest-style scams — there is no
separate Digital Arrest model or schema. The 13-category list below is
provisional pending a direct check against the AI/ML dev's
API_SPEC.md §1.2.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Unified classifier (Citizen Fraud Shield + digital-arrest-style scams)
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    text: str
    # "call_transcript" covers digital-arrest-style input: typed text,
    # on-device STT (Sarvam), or on-device OCR all arrive here as plain text.
    source_type: Literal[
        "sms", "email", "whatsapp", "payment_request", "call_transcript"
    ] = "sms"
    # offline: fast rule/ML pass (~6-10ms). online: slower (~3-5s), LLM-
    # generated `reason` text via Gemini with Groq fallback.
    mode: Literal["offline", "online"] = "offline"


# TODO: confirm this verbatim list against API_SPEC.md §1.2 on the AI/ML
# dev's side — this is a reconstruction from the handoff notes, not a
# direct copy of their source of truth.
RuleCategory = Literal[
    "authority_impersonation",
    "credential_request",
    "urgency_coercion",
    "money_demand",
    "reward_bait",
    "isolation_tactics",
    "otp_readout_request",
    "card_collection_request",
    "relative_impersonation",
    "telecom_impersonation",
    "extortion_threat",
    "malicious_link_bait",
    "malware_attachment_delivery",
]


class AnalyzeResponse(BaseModel):
    risk_score: float = Field(..., ge=0.0, le=1.0)  # 0.0-1.0, NOT 0-100
    verdict: Literal["SAFE", "SUSPICIOUS", "SCAM"]
    categories: list[RuleCategory] = Field(default_factory=list)  # can be empty
    reason: str  # single string, never a list


class CitizenReportRequest(BaseModel):
    scam_type: str
    description: str
    contact_info: Optional[str] = None
    date: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    district: Optional[str] = None

class CitizenReportResponse(BaseModel):
    report_id: str
    status: str = "received"
    message: str


# ---------------------------------------------------------------------------
# 2. Entity extraction — SEPARATE endpoint, not bundled into /analyze
# ---------------------------------------------------------------------------

class ExtractEntitiesRequest(BaseModel):
    text: str


class ExtractEntitiesResponse(BaseModel):
    phone_numbers: list[str] = Field(default_factory=list)
    upi_ids: list[str] = Field(default_factory=list)
    bank_accounts: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Fraud Network Intelligence (NetworkX-backed, in-memory, per-request —
#    no Neo4j, no pagination)
# ---------------------------------------------------------------------------

class NetworkNode(BaseModel):
    id: str
    phone_number: str
    category: str
    region: str
    risk_score: float = Field(..., ge=0.0, le=1.0)


class NetworkEdge(BaseModel):
    source: str
    target: str
    reason: str  # reason-for-link


class NetworkGraphResponse(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


class FraudCluster(BaseModel):
    id: str
    node_ids: list[str]
    risk_score: float = Field(..., ge=0.0, le=1.0)
    summary: str


class NetworkClustersResponse(BaseModel):
    clusters: list[FraudCluster]


# ---------------------------------------------------------------------------
# 4. Geospatial Crime Intelligence
# ---------------------------------------------------------------------------
# Synthetic demo data only — see geo_service.py. District boundary GeoJSON
# is bundled on the frontend (src/assets/geo/india_districts.geojson);
# `district` values below are chosen to match that file's `district`
# property so the frontend can join stats onto boundaries by name.

ScamType = Literal[
    "UPI Fraud",
    "Phishing",
    "Investment Scam",
    "Loan App Fraud",
    "KYC Fraud",
    "Job Fraud",
    "Digital Arrest",
]


class ComplaintPoint(BaseModel):
    lat: float
    lng: float
    scam_type: ScamType
    amount: float  # INR, amount involved/lost
    risk_score: int = Field(..., ge=0, le=100)
    date: str  # ISO date, YYYY-MM-DD
    district: str


class GeoComplaintsResponse(BaseModel):
    complaints: list[ComplaintPoint]


class DistrictStat(BaseModel):
    district_id: str
    complaint_count: int
    risk_score: float = Field(..., ge=0.0, le=100.0)  # complaints per 100k population, normalized 0-100
    top_scam_type: Optional[str] = None
    trend: Literal["up", "down", "flat"]
    trend_delta_pct: float  # % change in complaint count vs previous period of equal length


class GeoDistrictStatsResponse(BaseModel):
    districts: list[DistrictStat]


class GeoScamTypesResponse(BaseModel):
    scam_types: list[str]


class TrendPoint(BaseModel):
    date: str
    count: int


class ScamTypeTrend(BaseModel):
    scam_type: str
    points: list[TrendPoint]
    growth_rate_pct: float  # change from first half to second half of the selected period


class GeoTrendResponse(BaseModel):
    series: list[TrendPoint]  # total complaint volume over time, across all selected scam types
    by_scam_type: list[ScamTypeTrend]
    trending_scam_type: Optional[str] = None  # fastest-growing scam type in the period


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class GoogleAuthRequest(BaseModel):
    credential: str  # Google ID token (JWT) from the frontend Sign-In button


class UserResponse(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None


# ---------------------------------------------------------------------------
# Shared error shape
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: bool = True
    code: str
    message: str
