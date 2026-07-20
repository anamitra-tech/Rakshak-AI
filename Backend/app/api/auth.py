from fastapi import APIRouter, HTTPException, Request, Response
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.core.session import SESSION_COOKIE_NAME, create_session_token, read_session_token
from app.db.users_db import get_user, upsert_user
from app.models.schemas import GoogleAuthRequest, UserResponse

router = APIRouter()


def _set_session_cookie(response: Response, google_sub: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(google_sub),
        httponly=True,
        samesite="lax",
        secure=False,  # set True once served over https in production
        max_age=60 * 60 * 24 * 14,
        path="/",
    )


@router.post("/google", response_model=UserResponse)
def google_login(payload: GoogleAuthRequest, response: Response):
    if not settings.google_auth_configured:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID is not configured on the server.",
        )

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential.")

    google_sub = claims["sub"]
    email = claims["email"]
    name = claims.get("name", email)
    picture = claims.get("picture")

    # Upsert covers both sign-up (first time we see this google_sub) and
    # login (existing user) with the same call.
    user = upsert_user(google_sub, email, name, picture)

    _set_session_cookie(response, google_sub)

    return UserResponse(email=user["email"], name=user["name"], picture=user["picture"])


@router.get("/me", response_model=UserResponse)
def me(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    google_sub = read_session_token(token)
    if not google_sub:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    user = get_user(google_sub)
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    return UserResponse(email=user["email"], name=user["name"], picture=user["picture"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"status": "ok"}
