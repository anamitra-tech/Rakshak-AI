"""
Unified classifier route. Covers both Citizen Fraud Shield and
digital-arrest-style scams through a single endpoint — there is no
separate Digital Arrest route or model. Replaces the old
POST /api/citizen/analyze and POST /api/digital-arrest/analyze routes,
both removed.
"""

from fastapi import APIRouter

from app.models.schemas import AnalyzeRequest, AnalyzeResponse

from app.services.classifier import classify

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    result = classify(payload.text, payload.mode)
    return AnalyzeResponse(**result)
