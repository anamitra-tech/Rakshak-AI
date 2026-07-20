"""
Entity extraction route — separate from /analyze per the AI/ML handoff.
"""

from fastapi import APIRouter

from app.models.schemas import ExtractEntitiesRequest, ExtractEntitiesResponse

# --- SWAP THIS IMPORT ONCE THE REAL FILE EXISTS ---
# from app.services.entity_extraction import extract_entities
from app.services.entity_extraction_placeholder import extract_entities

router = APIRouter()


@router.post("/extract_entities", response_model=ExtractEntitiesResponse)
def extract(payload: ExtractEntitiesRequest):
    result = extract_entities(payload.text)
    return ExtractEntitiesResponse(**result)
