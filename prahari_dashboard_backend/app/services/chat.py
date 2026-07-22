"""
Assistant chat service -- thin wrapper around bot.agent.chat(), this
repo's actual LLM-orchestration entry point: intent classification, RAG
retrieval over kb/scams.json (rag/retriever.py, FAISS-backed), multilingual
support (bot/languages.py, bot/sarvam_translate.py), and generation via
llm/client.py's fallback chain. That chain is Groq -> Gemini -> Nemotron ->
Ollama by default (Groq first for free-tier quota headroom -- see the
comment in llm/client.py), except bot.agent.classify_intent()'s one call
site, which deliberately requests Gemini first because reverting that
specific call caused a measured recall regression in eval testing. Do not
"fix" either order to match a different assumed sequence without re-running
that eval suite -- it's not an oversight, it's a validated tradeoff.

MEMORY LIMITATION (real, not fixed here per instructions -- flagging only):
conversation history and repeat-scam pattern detection are kept in a plain
in-memory dict inside bot.agent (_sessions, keyed by session_id) -- the
same model the WhatsApp bot already uses. This means:
  - History is lost on every backend restart (including a plain uvicorn
    --reload triggered by a source file change).
  - History does NOT survive across multiple backend worker processes
    (e.g. `uvicorn --workers 4` or any horizontally-scaled deployment) --
    a session's messages can land on a different worker than the one that
    saw its earlier turns, silently losing context.
  - There is no TTL/eviction: _sessions grows for the lifetime of the
    process.
This is fine for a single-process dev/demo deployment (what this repo
currently runs as) and is an intentional, pre-existing architecture
decision, not something introduced by this file -- swapping it for real
persistence (Redis, a DB-backed session store) is a separate, larger
change or a future direction, not fixed here.
"""
from bot.agent import chat as _chat


def chat(session_id: str, message: str) -> dict:
    return _chat(session_id, message)
