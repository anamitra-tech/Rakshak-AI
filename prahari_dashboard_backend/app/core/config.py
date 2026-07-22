"""
Central place for all environment-driven settings.

Everything has a safe default so the app boots without real API keys.
gemini_api_key/groq_api_key are unused by this codebase today -- they're
here so the AI/ML dev's real classifier file can read them once it's
dropped in (see services/classifier_placeholder.py for the interface
it needs to match).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM (unused for now — present so the real classifier file can
    #     read them once it's dropped in; online mode uses Gemini with
    #     Groq fallback per the AI/ML handoff) ---
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # --- Mapbox (frontend uses this directly, but kept here for reference /
    #     in case backend needs it for server-side geocoding later) ---
    mapbox_token: str = ""

    # --- CORS ---
    frontend_origin: str = "http://localhost:5173"

    # --- Auth ---
    google_client_id: str = ""
    session_secret: str = "dev-insecure-secret-change-me"

    @property
    def google_auth_configured(self) -> bool:
        return bool(self.google_client_id)


settings = Settings()
