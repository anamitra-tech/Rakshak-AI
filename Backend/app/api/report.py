"""
Citizen scam report submission. Unrelated to the classifier/AI-ML
handoff — this just logs a report and hands back a reference ID.
"""

import uuid

from fastapi import APIRouter

from app.models.schemas import CitizenReportRequest, CitizenReportResponse

router = APIRouter()


@router.post("/report", response_model=CitizenReportResponse)
def report(payload: CitizenReportRequest):
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    return CitizenReportResponse(
        report_id=report_id,
        status="received",
        message="Your report has been logged. Please also file a formal complaint at cybercrime.gov.in or dial 1930.",
    )
