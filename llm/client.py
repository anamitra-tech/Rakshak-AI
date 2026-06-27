import logging
import os

import requests
from dotenv import load_dotenv

try:
    import groq as _groq_sdk
except ImportError:
    _groq_sdk = None

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
OLLAMA_MODEL = "gemma3"
OLLAMA_URL = "http://localhost:11434/api/generate"


class LLMResponse:
    def __init__(self, text: str, engine: str):
        self.text = text
        self.engine = engine

    def __repr__(self):
        return f"LLMResponse(engine={self.engine!r}, text={self.text[:80]!r})"


def _call_groq(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not configured")

    from groq import Groq  # imported here so missing package doesn't break offline use

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=10,
    )
    return response.choices[0].message.content


def _call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


def generate(prompt: str) -> LLMResponse:
    """Call Groq (online) with automatic fallback to local Ollama (offline)."""
    try:
        text = _call_groq(prompt)
        logger.info("Engine: Groq (%s)", GROQ_MODEL)
        return LLMResponse(text=text, engine="groq")
    except Exception as exc:
        if _groq_sdk and isinstance(exc, _groq_sdk.RateLimitError):
            logger.warning("Groq rate-limited (429) — falling back to Ollama/%s", OLLAMA_MODEL)
        else:
            logger.warning("Groq unavailable (%s) — falling back to Ollama/%s", exc, OLLAMA_MODEL)
        text = _call_ollama(prompt)
        logger.info("Engine: Ollama (%s)", OLLAMA_MODEL)
        return LLMResponse(text=text, engine="ollama")
