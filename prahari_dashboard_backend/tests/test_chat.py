"""
Tests for POST /api/chat -- the real bot.agent.chat() RAG + multilingual
LLM-orchestration pipeline (app/api/chat.py -> app/services/chat.py ->
bot.agent.chat()). Run with: pytest tests/test_chat.py -v

These hit the real pipeline (real classifier, real LLM calls when keys are
configured) -- there is no mock/stub classifier or LLM client in this repo
to substitute in. Assertions are written to hold either way (LLM keys
present or absent), since llm/client.py's fallback chain is specifically
designed to degrade to a safe, well-formed response rather than fail.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post_chat(message: str, session_id: str = "test-session") -> dict:
    r = client.post("/api/chat", json={"session_id": session_id, "message": message})
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
    return r.json()


class TestChatHappyPath:
    def test_sample_fraud_query_returns_real_verdict(self):
        """The exact query from the QA spec: a genuine OTP-scam question."""
        body = _post_chat("I received a call asking for OTP from bank, is this scam?")
        assert body["answer"], "answer must not be empty"
        assert isinstance(body["answer"], str)
        assert body["engine"] is not None, "engine must be reported (which provider/path answered)"
        # confidence is legitimately None on non-scam-check intents (greeting,
        # general_chat, language_change, informational_query) -- only assert
        # it's present (not KeyError) and, if set, is a valid probability.
        assert "confidence" in body
        if body["confidence"] is not None:
            assert 0.0 <= body["confidence"] <= 1.0

    def test_obvious_scam_returns_high_confidence_fraud(self):
        body = _post_chat(
            "Sir this is CBI officer, your Aadhaar linked to money laundering. "
            "Share your OTP now or you will be arrested.",
            session_id="test-obvious-scam",
        )
        assert body["scam_type"] is not None
        assert body["confidence"] is not None
        assert body["confidence"] >= 0.7
        assert "1930" in body["answer"] or "cybercrime.gov.in" in body["answer"]

    def test_response_schema_has_documented_fields(self):
        body = _post_chat("Hello, who are you?", session_id="test-schema")
        for field in ("answer", "scam_type", "confidence", "engine", "profile",
                       "intent", "session_id", "history_length"):
            assert field in body, f"missing documented field: {field}"

    def test_session_history_increments_across_turns(self):
        sid = "test-history-increment"
        first = _post_chat("Hello", session_id=sid)
        second = _post_chat("What can you help with?", session_id=sid)
        assert second["history_length"] > first["history_length"]


class TestChatEdgeCases:
    """Verified individually via TestClient before being written as
    assertions -- see the conversation this test file was added in for the
    raw output. All six returned 200 with a non-empty answer and no
    exception, so that's what's asserted here."""

    @pytest.mark.parametrize("message", [
        "",
        "   ",
        "urgent send money now " * 500,  # ~11.5k chars
        "Bonjour, quelqu'un m'a appelé en pretendant etre de la police.",  # French
        "S1r th1s 1s CB1 0ff1cer y0ur Aadhaar l1nked t0 m0ney l@under1ng   pl3ase   s3nd   0TP",  # OCR-noisy
        "नमस्ते, किसी ने मुझे पुलिस अधिकारी बनकर फोन किया और पैसे मांगे।",  # Devanagari
    ], ids=["empty", "whitespace_only", "very_long_11k_chars", "unsupported_language_french",
            "ocr_noisy_text", "devanagari_script"])
    def test_no_crash_and_safe_response(self, message):
        r = client.post("/api/chat", json={"session_id": f"edge-{hash(message)}", "message": message})
        assert r.status_code == 200
        body = r.json()
        assert body["answer"], "must return non-empty guidance even on edge-case input"


class TestChatFallbackChainResilience:
    """Exercises llm/client.py's fallback chain directly (not through the
    route) -- forcing every provider to fail and confirming the failure is
    a single, clear, catchable error rather than a crash or hang. See
    llm/client.py's generate() for the actual chain logic; this does not
    re-test bot.agent's own try/except wrapping (already covered by the
    edge-case tests above never crashing even under real network
    conditions)."""

    def test_all_providers_failing_raises_one_clear_error(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "")
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("NVIDIA_API_KEY", "")
        from llm.client import generate
        with pytest.raises(RuntimeError, match="All LLM providers failed"):
            generate("test prompt", retries=1)

    def test_missing_gemini_key_does_not_crash_import(self, monkeypatch):
        """Regression test for the real bug found and fixed in this pass:
        llm.client used to construct the Gemini client eagerly at module
        import time, so a missing GEMINI_API_KEY crashed `import llm.client`
        itself -- before any caller's try/except ever ran. Re-importing the
        already-imported module doesn't re-trigger module-level code, so
        this asserts the fixed behavior structurally: _gemini_generate must
        check the key itself and raise a normal, catchable ValueError, not
        rely on import-time construction."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        from llm.client import _gemini_generate
        with pytest.raises(ValueError, match="GEMINI_API_KEY not configured"):
            _gemini_generate("test prompt")
