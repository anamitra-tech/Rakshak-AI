"""
Best-effort mobile-number-prefix -> telecom circle (LSA) lookup, for the
investigator dashboard only. Not imported by, and does not touch, any
citizen-facing code or the detection pipeline.

Honesty notes (read before trusting this for anything beyond a demo):

1. India's mobile numbering plan allocates 4-digit series blocks to a
   circle at first-issue time (DoT/TRAI National Numbering Plan). This
   table is a small, illustrative subset of that allocation covering the
   prefixes that actually appear in this project's seed data plus a few
   extras for demo variety -- it is NOT an exhaustive, verified national
   table. Treat any circle label here as "probably this circle", not a
   certainty.
2. Mobile Number Portability (MNP) in India is *intra-circle only* -- a
   subscriber can port operators but not circles without acquiring a new
   number -- so a prefix's circle-of-first-allocation stays a reasonably
   durable signal even years later. It is still not a live location: a
   phone physically roaming outside its home circle looks identical here.
3. Any 10-digit string that doesn't start with 6-9 isn't a valid Indian
   mobile number at all (e.g. this repo's own "+911234567890" test-data
   artifact) -- those fall through to UNKNOWN_CIRCLE, not a guess.
"""

UNKNOWN_CIRCLE = "Unknown circle (unmapped or invalid prefix)"

# 4-digit-prefix -> circle name. Deliberately small; extend only with
# prefixes you can actually attribute to a source, not by guessing ranges.
_PREFIX_TO_CIRCLE = {
    "7838": "Delhi NCR",
    "9871": "Delhi NCR",
    "9873": "Delhi NCR",
    "9910": "Delhi NCR",
    "9820": "Mumbai",
    "9821": "Mumbai",
    "9987": "Mumbai",
    "9930": "Mumbai",
    "9769": "Maharashtra",
    "9765": "Maharashtra",
    "9880": "Karnataka",
    "9886": "Karnataka",
    "9945": "Karnataka",
    "9840": "Tamil Nadu",
    "9962": "Tamil Nadu",
    "9444": "Tamil Nadu",
    "9848": "Andhra Pradesh & Telangana",
    "9908": "Andhra Pradesh & Telangana",
    "9440": "Andhra Pradesh & Telangana",
    "9830": "West Bengal",
    "9831": "West Bengal",
    "9903": "West Bengal",
    "9825": "Gujarat",
    "9909": "Gujarat",
    "9924": "Gujarat",
    "9829": "Rajasthan",
    "9928": "Rajasthan",
    "9838": "UP East",
    "9936": "UP East",
    "9415": "UP West",
    "9720": "UP West",
    "9876": "Punjab",  # NOTE: also this repo's own demo/test-number series -- see seed_data.py
    "9779": "Haryana",
    "9847": "Kerala",
    "9946": "Kerala",
    "9977": "Madhya Pradesh & Chhattisgarh",
    "9754": "Madhya Pradesh & Chhattisgarh",
    "9835": "Bihar & Jharkhand",
    "9709": "Bihar & Jharkhand",
    "9437": "Odisha",
    "9556": "Odisha",
    "9435": "Assam & North East",
    "9954": "Assam & North East",
    "9797": "Jammu & Kashmir",
    "9805": "Himachal Pradesh",
}

# Circle -> approximate centroid (principal city), for map plotting only.
# These are ordinary public city coordinates, not perpetrator locations.
CIRCLE_CENTROIDS = {
    "Delhi NCR": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Maharashtra": (19.9975, 73.7898),   # Nashik, as a non-Mumbai MH anchor
    "Karnataka": (12.9716, 77.5946),
    "Tamil Nadu": (13.0827, 80.2707),
    "Andhra Pradesh & Telangana": (17.3850, 78.4867),
    "West Bengal": (22.5726, 88.3639),
    "Gujarat": (23.0225, 72.5714),
    "Rajasthan": (26.9124, 75.7873),
    "UP East": (25.3176, 82.9739),        # Varanasi
    "UP West": (28.6692, 77.4538),        # Ghaziabad/Noida belt
    "Punjab": (30.7333, 76.7794),         # Chandigarh (shared capital)
    "Haryana": (29.0588, 76.0856),        # Rohtak, as a non-Chandigarh HR anchor
    "Kerala": (9.9312, 76.2673),
    "Madhya Pradesh & Chhattisgarh": (23.2599, 77.4126),
    "Bihar & Jharkhand": (25.5941, 85.1376),
    "Odisha": (20.2961, 85.8245),
    "Assam & North East": (26.1445, 91.7362),
    "Jammu & Kashmir": (34.0837, 74.7973),
    "Himachal Pradesh": (31.1048, 77.1734),
}


def lookup_circle(phone_e164: str) -> str:
    """phone_e164 like '+919876543299'. Returns a circle name or UNKNOWN_CIRCLE."""
    digits = "".join(ch for ch in (phone_e164 or "") if ch.isdigit())
    # Strip a leading '91' country code if present, leaving the 10-digit number.
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10 or digits[0] not in "6789":
        return UNKNOWN_CIRCLE
    prefix = digits[:4]
    return _PREFIX_TO_CIRCLE.get(prefix, UNKNOWN_CIRCLE)


def centroid_for_circle(circle: str):
    """Returns (lat, lng) or None if the circle has no known centroid (e.g. UNKNOWN_CIRCLE)."""
    return CIRCLE_CENTROIDS.get(circle)
