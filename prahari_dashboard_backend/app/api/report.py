"""
Citizen scam report submission. Unrelated to the classifier/AI-ML
handoff — this just logs a report and hands back a reference ID.
"""

import uuid
from datetime import date
import random

from fastapi import APIRouter

from app.models.schemas import CitizenReportRequest, CitizenReportResponse
from app.services import geo_service

router = APIRouter()


@router.post("/report", response_model=CitizenReportResponse)
def report(payload: CitizenReportRequest):
    report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
    
    lat = payload.lat
    lng = payload.lng
    district = payload.district
    
    if lat is None or lng is None:
        lat, lng, district = geo_service.mock_geocode(payload.district or "")
    else:
        # If lat/lng provided but no district, we can roughly mock reverse geocode
        if not district:
            _, _, district = geo_service.mock_geocode("")

    # Map request to ComplaintPoint dictionary
    valid_scams = geo_service.SCAM_TYPES
    mapped_scam = next((s for s in valid_scams if s.lower() == payload.scam_type.lower()), None)
    
    if not mapped_scam:
        mapping = {
            "authority_impersonation": "Digital Arrest",
            "credential_request": "Phishing",
            "urgency_coercion": "Digital Arrest",
            "money_demand": "Investment Scam",
            "reward_bait": "Phishing",
            "isolation_tactics": "Digital Arrest",
            "otp_readout_request": "UPI Fraud",
            "card_collection_request": "Phishing",
            "relative_impersonation": "Digital Arrest",
            "telecom_impersonation": "Digital Arrest",
            "extortion_threat": "Digital Arrest",
            "malicious_link_bait": "Phishing",
            "malware_attachment_delivery": "Phishing",
            "upi_fraud": "UPI Fraud",
            "phishing": "Phishing",
            "investment_scam": "Investment Scam",
            "investment_fraud": "Investment Scam",
            "loan_app_fraud": "Loan App Fraud",
            "kyc_fraud": "KYC Fraud",
            "job_fraud": "Job Fraud",
            "digital_arrest": "Digital Arrest",
        }
        lower_type = payload.scam_type.lower().replace(" ", "_")
        mapped_scam = mapping.get(lower_type, "Phishing") # Default fallback

    complaint_dict = {
        "lat": lat,
        "lng": lng,
        "scam_type": mapped_scam,
        "amount": round(random.uniform(100, 5000), 2), # Mock amount for now
        "risk_score": random.randint(30, 90), # Mock risk score
        "date": payload.date or date.today().isoformat(),
        "district": district,
    }
    
    geo_service.add_complaint(complaint_dict)

    return CitizenReportResponse(
        report_id=report_id,
        status="received",
        message="Your report has been logged. Please also file a formal complaint at cybercrime.gov.in or dial 1930.",
    )
