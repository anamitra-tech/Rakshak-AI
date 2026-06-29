from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import logging
import os
import sys

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from bot.agent import chat

logging.basicConfig(level=logging.INFO)
app = FastAPI()

@app.post("/webhook", response_class=PlainTextResponse)
async def webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default="")
):
    try:
        if not Body.strip():
            reply = "Please send a message."
        else:
            session_id = From.replace("whatsapp:", "")
            result = chat(session_id, Body.strip())
            reply = result["answer"]
            logging.info(
                f"session={session_id} | "
                f"scam={result.get('scam_type')} | "
                f"profile={result.get('profile')} | "
                f"engine={result.get('engine')}"
            )
    except Exception as e:
        logging.error(f"Error: {e}")
        reply = "Kuch gadbad ho gayi. Seedha 1930 pe call karein."

    resp = MessagingResponse()
    resp.message(reply.strip('"'))
    return str(resp)

@app.get("/health")
async def health():
    return {"status": "ok", "cards": 75}
