import logging
import os
import time

import requests
from google import genai as google_genai
from dotenv import load_dotenv

try:
    import groq as _groq_sdk
except ImportError:
    _groq_sdk = None

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.5-flash"
OLLAMA_MODEL = "gemma3"
OLLAMA_URL = "http://localhost:11434/api/generate"

_gemini_client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class LLMResponse:
    def __init__(self, text: str, engine: str):
        self.text = text
        self.engine = engine

    def __repr__(self):
        return f"LLMResponse(engine={self.engine!r}, text={self.text[:80]!r})"


def _groq_generate(prompt: str) -> LLMResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not configured")

    from groq import Groq

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        timeout=10,
    )
    return LLMResponse(text=response.choices[0].message.content, engine="groq")


def _fallback_generate(prompt: str) -> LLMResponse:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return LLMResponse(text=response.json()["response"], engine="ollama")


def generate(prompt: str, retries: int = 3) -> LLMResponse:
    for attempt in range(retries):
        try:
            response = _gemini_client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            if response.text and len(response.text.strip()) > 10:
                logger.info("Engine: Gemini (%s)", GEMINI_MODEL)
                return LLMResponse(text=response.text, engine="gemini")
        except Exception as e:
            logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
            time.sleep(1)

    logger.warning("Gemini failed after %d attempts — falling back to Groq", retries)
    try:
        return _groq_generate(prompt)
    except Exception as exc:
        logger.warning("Groq fallback failed (%s) — falling back to Ollama", exc)
        return _fallback_generate(prompt)
