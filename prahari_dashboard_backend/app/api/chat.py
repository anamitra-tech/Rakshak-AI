"""
Assistant chat route -- RAG + multilingual LLM orchestration
(bot.agent.chat()). See app/services/chat.py for what it actually calls.
"""

from fastapi import APIRouter

from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat import chat as chat_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    result = chat_service(payload.session_id, payload.message)
    return ChatResponse(**result)
