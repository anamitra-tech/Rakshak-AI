"""
FastAPI version of the API (optional — requires `pip install fastapi uvicorn`).

The stdlib server in api/server.py is the zero-dependency default used for the
offline demo. This file exposes the identical routes via FastAPI for teams that
want OpenAPI docs, async, and production ASGI deployment (uvicorn/gunicorn).

Run:  uvicorn api.app_fastapi:app --reload --port 8000
"""
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.detector import ScamDetector
from ml.session import FraudSessionDetector
from link.url_safety import analyze_url
from voice.voice_fraud import analyze_transcript
from graph.fraud_graph import FraudGraph
from geo.geo_fraud import GeoFraudLayer, demo_points
from casefile.case_generator import generate_case
from data.synth import generate_fraud_graph

app = FastAPI(title="Prahari · Digital Public Safety Intelligence", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DETECTOR = ScamDetector()
SESSION = FraudSessionDetector(DETECTOR)
GRAPH = FraudGraph()
GEO = GeoFraudLayer()

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend", "index.html")


class Msg(BaseModel):
    text: str = ""

class Sess(BaseModel):
    session_id: str = "anon"
    text: str = ""

class Url(BaseModel):
    url: str = ""

class Voice(BaseModel):
    transcript: str = ""

class Interaction(BaseModel):
    src: str
    dst: str
    type: str = "message"
    amount: float = 0
    ts: float | None = None

class CaseReq(BaseModel):
    text: str | None = None
    transcript: str | None = None
    url: str | None = None
    session_id: str | None = None
    subject: str | None = None


@app.get("/")
def home():
    return FileResponse(FRONTEND)

@app.get("/health")
def health():
    return {"status": "ok", "modules": 7}

@app.post("/analyze_message")
def analyze_message(m: Msg):
    return DETECTOR.predict(m.text)

@app.post("/analyze_session")
def analyze_session(s: Sess):
    return SESSION.ingest(s.session_id, s.text)

@app.post("/analyze_url")
def analyze_url_ep(u: Url):
    return analyze_url(u.url)

@app.post("/analyze_voice")
def analyze_voice_ep(v: Voice):
    return analyze_transcript(v.transcript, DETECTOR)

@app.post("/graph/add_interaction")
def add_interaction(i: Interaction):
    return {"ok": True, **GRAPH.add_interaction(i.src, i.dst, i.type, i.amount, i.ts)}

@app.post("/graph/seed")
def graph_seed():
    GRAPH.bulk_load(generate_fraud_graph())
    return {"ok": True, **GRAPH.analyze()}

@app.get("/graph/analyze")
def graph_analyze():
    return GRAPH.analyze()

@app.post("/geo/seed")
def geo_seed():
    GEO.bulk_add(demo_points())
    return {"ok": True}

@app.get("/geo/analyze")
def geo_analyze():
    return GEO.analyze()

@app.post("/case/generate")
def case_generate(c: CaseReq):
    mr = DETECTOR.predict(c.text) if c.text else None
    vr = analyze_transcript(c.transcript, DETECTOR) if c.transcript else None
    ur = analyze_url(c.url) if c.url else None
    sr = SESSION.ingest(c.session_id, c.text or "") if c.session_id else None
    gr = GRAPH.analyze() if GRAPH.G.number_of_nodes() else None
    return generate_case(message_result=mr, voice_result=vr, url_result=ur,
                         session_result=sr, graph_result=gr, subject=c.subject)
