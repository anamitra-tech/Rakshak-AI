import logging
import os
import time

# torch, FlagEmbedding, and faiss must load before gRPC on Windows to avoid DLL conflict
try:
    import torch as _torch  # noqa: F401
    from FlagEmbedding import BGEM3FlagModel as _BGE  # noqa: F401
    import faiss as _faiss  # noqa: F401
except ImportError:
    pass

import requests
from google import genai as google_genai
from dotenv import load_dotenv

try:
    import groq as _groq_sdk
except ImportError:
    _groq_sdk = None

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"  # temporarily primary -- see generate()
GEMINI_MODEL = "gemini-2.5-flash"  # temporarily secondary fallback -- see generate()
# Tested against the real account/key: "nvidia/llama-3.1-nemotron-70b-instruct"
# (the originally guessed id) returns 404 "Function ... Not found for
# account" -- it's listed in GET /v1/models but not enabled/invokable on
# this account. "nvidia/llama-3.3-nemotron-super-49b-v1" is confirmed
# working (real 200 response) and is what's actually wired in below.
NVIDIA_NIM_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"
NVIDIA_NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
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


def _nemotron_generate(prompt: str) -> LLMResponse:
    """Additional fallback tier, OpenAI-compatible NIM endpoint. Confirmed
    working against a real key/account -- see the NVIDIA_NIM_MODEL comment
    above for the model-id caveat."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key or api_key == "your_nvidia_api_key_here":
        raise ValueError("NVIDIA_API_KEY not configured")

    response = requests.post(
        NVIDIA_NIM_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": NVIDIA_NIM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 1024,
        },
        timeout=30,
    )
    response.raise_for_status()
    text = response.json()["choices"][0]["message"]["content"]
    return LLMResponse(text=text, engine="nemotron")


def _fallback_generate(prompt: str) -> LLMResponse:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    return LLMResponse(text=response.json()["response"], engine="ollama")


def _gemini_generate(prompt: str) -> LLMResponse:
    response = _gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    if response.text and len(response.text.strip()) > 10:
        logger.info("Engine: Gemini (%s)", GEMINI_MODEL)
        return LLMResponse(text=response.text, engine="gemini")
    raise ValueError("Gemini returned an empty/too-short response")


_ENGINE_FNS = {
    "groq": _groq_generate,
    "gemini": _gemini_generate,
    "nemotron": _nemotron_generate,
    "ollama": _fallback_generate,
}

# TEMPORARY (demo/testing quota workaround): Groq tried first by default,
# since its free tier has much higher headroom than Gemini's 20/day cap --
# Gemini remains a real, still-available fallback, not removed. Scoped,
# not blanket: bot/agent.py::classify_intent() passes prefer_gemini=True
# instead, because that is the one call site where engine choice affects a
# real decision (which intent branch fires, i.e. whether ScamDetector even
# runs for a message that doesn't trip the deterministic rule-based
# backstop) rather than just output wording. Confirmed via eval_rag_testset.py
# that applying Groq-first there too caused a real recall regression
# (expert_scam 1.00->0.90, one case misrouted to general_chat) -- reverted
# for that call site specifically, kept everywhere else. Revert this whole
# workaround by making "gemini" the default order once Gemini quota stops
# being the binding constraint.
_DEFAULT_ORDER = ["groq", "gemini", "nemotron", "ollama"]
_GEMINI_FIRST_ORDER = ["gemini", "groq", "nemotron", "ollama"]


def generate(prompt: str, retries: int = 3, prefer_gemini: bool = False) -> LLMResponse:
    order = _GEMINI_FIRST_ORDER if prefer_gemini else _DEFAULT_ORDER
    primary = order[0]

    for attempt in range(retries):
        try:
            return _ENGINE_FNS[primary](prompt)
        except Exception as e:
            logger.warning("%s attempt %d failed: %s", primary, attempt + 1, e)
            time.sleep(1)

    logger.warning("%s failed after %d attempts — trying fallback chain %s", primary, retries, order[1:])
    for name in order[1:-1]:
        try:
            return _ENGINE_FNS[name](prompt)
        except Exception as exc:
            logger.warning("%s fallback failed (%s) — trying next", name, exc)

    return _ENGINE_FNS[order[-1]](prompt)
