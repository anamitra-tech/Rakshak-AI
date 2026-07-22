"""
Clean, typed REST API for external integration (a separate backend/website
consuming this dashboard's data, not just the bundled browser UI).

Mounted under /api/v1 by investigator_app.py. Endpoints, full request/
response documentation, and example curl calls: see dashboard/API.md, or
the auto-generated interactive docs at /docs (Swagger UI) and /redoc once
the server is running.

Read-only throughout: nothing here writes to feedback.db, ml/detector.py,
or any citizen-facing surface.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from dashboard.data_provider import get_graph
from dashboard.jurisdiction import lookup_jurisdiction
from dashboard.telecom_circles import CIRCLE_CENTROIDS, UNKNOWN_CIRCLE

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ReportOut(BaseModel):
    node_id: str = Field(description="Phone number in E.164 form. Real for feedback_db-sourced reports, synthetic-but-deterministic for eval_testset_synthetic ones.")
    source: Literal["feedback_db", "eval_testset_synthetic"] = Field(description="feedback_db = real logged correction; eval_testset_synthetic = real detector output on a labeled test case, synthetic phone number.")
    risk_level: str
    score: float | None = Field(default=None, description="Null for feedback_db rows -- feedback/store.py does not persist the numeric score at correction time.")
    rule_categories: list[str] = Field(description="ml.detector.ScamDetector's actual rule_categories output for this text.")
    text_excerpt: str
    channel: str
    timestamp_utc: str
    timestamp_is_synthetic: bool = Field(description="True for eval_testset_synthetic rows -- their timestamp is a deterministic demo spread, not a real report time.")
    telecom_circle: str
    self_reported_city: str | None
    self_reported_state: str | None
    cluster_id: int


class ClusterOut(BaseModel):
    cluster_id: int
    size: int
    members: list[str] = Field(description="node_id (phone number) of every report in this cluster.")
    rule_categories: list[str]
    telecom_circles: list[str]


class CircleOut(BaseModel):
    circle: str
    report_count: int
    centroid_lat: float | None = Field(description="Approximate principal-city centroid for map display -- not a perpetrator or victim location.")
    centroid_lng: float | None
    node_ids: list[str]


class JurisdictionContactOut(BaseModel):
    state_or_ut: str
    officer_name: str
    designation: str
    phone: str | None = Field(description="Null where the official source lists no direct phone number (email only).")
    email: str
    source_url: str
    captured_on: str
    staleness_warning: str


class NationalEscalationOut(BaseModel):
    helpline: str
    portal: str
    note: str


class JurisdictionOut(BaseModel):
    resolved: bool
    resolved_via: Literal["state", "city"] | None = None
    reason: str | None = Field(default=None, description="Populated when resolved=false -- e.g. 'location not provided'.")
    state_or_ut: str | None
    contact: JurisdictionContactOut | None
    national_escalation: NationalEscalationOut


class MetaOut(BaseModel):
    total_reports: int
    total_clusters: int
    data_scale_note: str
    location_disclaimer: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATA_SCALE_NOTE = (
    "Demo-scale seed data only (feedback.db real corrections + "
    "rakshak_eval_testset.json scored through the live detector) -- "
    "not live production complaint volume."
)
_LOCATION_DISCLAIMER = (
    "Circle/city data shows where a NUMBER's telecom circle is allocated or "
    "where a citizen self-reported, not where a scammer is physically "
    "located -- precise perpetrator geolocation requires telecom-carrier "
    "access this system does not have."
)


def _report_to_out(node: dict) -> ReportOut:
    return ReportOut(**{k: node[k] for k in ReportOut.model_fields if k in node})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/meta", response_model=MetaOut, summary="Dataset scale + standing disclaimers")
def get_meta():
    g = get_graph()
    return MetaOut(
        total_reports=len(g["nodes"]),
        total_clusters=len(g["clusters"]),
        data_scale_note=_DATA_SCALE_NOTE,
        location_disclaimer=_LOCATION_DISCLAIMER,
    )


@router.get("/clusters", response_model=list[ClusterOut], summary="List all fraud-script clusters")
def list_clusters(min_size: int = Query(default=1, ge=1, description="Only return clusters with at least this many members.")):
    g = get_graph()
    return [ClusterOut(**c) for c in g["clusters"] if c["size"] >= min_size]


@router.get("/clusters/{cluster_id}", response_model=ClusterOut, summary="Get one cluster by id")
def get_cluster(cluster_id: int):
    g = get_graph()
    for c in g["clusters"]:
        if c["cluster_id"] == cluster_id:
            return ClusterOut(**c)
    raise HTTPException(status_code=404, detail=f"No cluster with id {cluster_id}")


@router.get("/reports", response_model=list[ReportOut], summary="List reports, optionally filtered")
def list_reports(
    circle: str | None = Query(default=None, description="Exact telecom_circle name, e.g. 'Delhi NCR'."),
    cluster_id: int | None = Query(default=None),
    source: Literal["feedback_db", "eval_testset_synthetic"] | None = Query(default=None),
    rule_category: str | None = Query(default=None, description="Only reports whose rule_categories includes this value."),
):
    g = get_graph()
    reports = g["nodes"]
    if circle is not None:
        reports = [n for n in reports if n["telecom_circle"] == circle]
    if cluster_id is not None:
        reports = [n for n in reports if n["cluster_id"] == cluster_id]
    if source is not None:
        reports = [n for n in reports if n["source"] == source]
    if rule_category is not None:
        reports = [n for n in reports if rule_category in n["rule_categories"]]
    return [_report_to_out(n) for n in reports]


@router.get("/reports/{node_id}", response_model=ReportOut, summary="Get one report by phone number (node_id)")
def get_report(node_id: str):
    g = get_graph()
    for n in g["nodes"]:
        if n["node_id"] == node_id:
            return _report_to_out(n)
    raise HTTPException(status_code=404, detail=f"No report for node_id {node_id}")


@router.get("/circles", response_model=list[CircleOut], summary="Report counts by telecom circle")
def list_circles():
    g = get_graph()
    by_circle: dict[str, list[str]] = {}
    for n in g["nodes"]:
        by_circle.setdefault(n["telecom_circle"], []).append(n["node_id"])

    out = []
    for circle, node_ids in by_circle.items():
        centroid = CIRCLE_CENTROIDS.get(circle) if circle != UNKNOWN_CIRCLE else None
        out.append(CircleOut(
            circle=circle,
            report_count=len(node_ids),
            centroid_lat=centroid[0] if centroid else None,
            centroid_lng=centroid[1] if centroid else None,
            node_ids=node_ids,
        ))
    return sorted(out, key=lambda c: c.report_count, reverse=True)


@router.get(
    "/jurisdiction", response_model=JurisdictionOut,
    summary="State cybercrime-cell contact lookup (jurisdiction routing, NOT location tracking)",
    description=(
        "Takes ONLY a self-reported state and/or city -- never a phone number. "
        "If neither is given or recognized, returns resolved=false with "
        "reason='location not provided' rather than guessing from any "
        "phone-number/telecom-circle signal (no such fallback exists)."
    ),
)
def get_jurisdiction(
    state: str | None = Query(default=None, description="Self-reported state/UT name, e.g. 'Maharashtra' or 'MH'."),
    city: str | None = Query(default=None, description="Self-reported city, used only if state is absent/unrecognized."),
):
    return JurisdictionOut(**lookup_jurisdiction(state=state, city=city))
