"""
PLACEHOLDER — awaiting AI/ML integration.

Fixed, obviously-fake response so api/entities.py has something to call
while the real entity extraction is decided. No real regex or parsing
logic lives here on purpose — see the note below.

--------------------------------------------------------------------
DROP-IN REPLACEMENT CONTRACT — read this before wiring in the real file
--------------------------------------------------------------------
The real implementation must expose a function with this exact
signature:

    def extract_entities(text: str) -> dict

Returns a dict with EXACTLY these keys (matching
schemas.ExtractEntitiesResponse):
    {
        "phone_numbers": list[str],
        "upi_ids": list[str],
        "bank_accounts": list[str],
        "urls": list[str],
    }

Once this function exists in the real file, api/entities.py only needs
its import line changed (see the comment at the top of that file).

NOTE: this may end up being simple regex-based extraction written
in-house rather than an AI/ML handoff — but that's a separate,
explicit task. Do not pre-write real extraction logic in this file.
--------------------------------------------------------------------
"""

_FIXED_RESULT = {
    "phone_numbers": ["[PLACEHOLDER-PHONE-0000000000]"],
    "upi_ids": ["placeholder@PLACEHOLDER"],
    "bank_accounts": ["[PLACEHOLDER-ACCOUNT-000000000000]"],
    "urls": ["https://placeholder.invalid/awaiting-integration"],
}


def extract_entities(text: str) -> dict:
    return {k: list(v) for k, v in _FIXED_RESULT.items()}
