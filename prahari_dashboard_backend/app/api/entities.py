"""
Entity extraction route — separate from /analyze per the AI/ML handoff.
"""

from fastapi import APIRouter

from app.models.schemas import ExtractEntitiesRequest, ExtractEntitiesResponse

# Real implementation lives in app/utils/entity_extraction.py (regex-based,
# already matches this exact contract — see that file's docstring) rather
# than app/services/entity_extraction.py as the placeholder's comment
# guessed.
from app.utils.entity_extraction import extract_entities

router = APIRouter()


@router.post("/extract_entities", response_model=ExtractEntitiesResponse)
def extract(payload: ExtractEntitiesRequest):
    result = extract_entities(payload.text)
    return ExtractEntitiesResponse(**result)
