"""
Signed, httponly session cookie helpers (no server-side session store needed --
the cookie itself carries the google_sub, signed so it can't be forged).
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

SESSION_COOKIE_NAME = "prahari_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # 14 days

_serializer = URLSafeTimedSerializer(settings.session_secret, salt="prahari-session")


def create_session_token(google_sub: str) -> str:
    return _serializer.dumps({"sub": google_sub})


def read_session_token(token: str) -> str | None:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("sub")
