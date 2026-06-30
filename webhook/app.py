from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_ROOT, ".env"))
sys.path.insert(0, _ROOT)

from bot.agent import chat, _sessions
from graph.fraud_graph import (
    build_fraud_graph_with_entities,
    get_graph_summary,
    get_hard_links,
    get_ring_clusters,
)

logging.basicConfig(level=logging.INFO)
app = FastAPI()

@app.post("/webhook")
async def webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    FromCountry: str = Form(default=""),
    FromCity: str = Form(default=""),
    NumMedia: str = Form(default="0"),
):
    try:
        if not Body.strip():
            reply = "Please send a message."
        else:
            session_id = From.replace("whatsapp:", "")
            result = chat(session_id, Body.strip())
            reply = result["answer"]

            # ADDITION 3 — store Twilio geo metadata for graph indexing
            twilio_metadata = {
                "from_country": FromCountry,
                "from_city": FromCity,
                "num_media": NumMedia,
            }
            result["twilio_metadata"] = twilio_metadata
            if session_id in _sessions and _sessions[session_id]:
                _sessions[session_id][-1]["twilio_metadata"] = twilio_metadata

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
    resp.message(reply.strip('"').strip("'"))
    return Response(content=str(resp), media_type="application/xml")

@app.get("/health")
async def health():
    return {"status": "ok", "cards": 75}

@app.get("/graph")
async def graph_endpoint():
    G = build_fraud_graph_with_entities()
    summary = get_graph_summary(G)
    hard_links = get_hard_links(G)
    rings = get_ring_clusters(G)
    return {
        "summary": summary,
        "hard_links": hard_links,
        "fraud_rings": rings,
        "nodes": [{"id": n, **d} for n, d in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)],
        "intelligence": {
            "confirmed_links": len(hard_links),
            "probable_rings": len(rings),
            "highest_confidence_ring": rings[0] if rings else None,
            "alert": (
                f"{len(rings)} probable fraud rings detected "
                f"across {sum(r['victim_count'] for r in rings)} victim reports"
            ) if rings else "Insufficient data for ring detection",
        },
    }
