"""
API LAYER — Digital Public Safety Intelligence System.

Built on Python's standard library http.server so it runs with ZERO external
dependencies (satisfies the 'offline mode / no external dependency' requirement).
A FastAPI version of the same routes is provided in api/app_fastapi.py for teams
that prefer ASGI.

Endpoints
  GET  /                      -> serves the frontend
  GET  /health
  POST /analyze_message       {text}
  POST /analyze_session       {session_id, text}
  POST /analyze_url           {url}
  POST /analyze_voice         {transcript}
  POST /graph/add_interaction {src, dst, type, amount}
  GET  /graph/analyze
  POST /graph/seed            -> load synthetic ring
  GET  /geo/analyze
  POST /geo/seed
  POST /case/generate         {text?, transcript?, url?, session_id?, subject?}
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.detector import ScamDetector
from ml.session import FraudSessionDetector
from ml import llm_explainer
from link.url_safety import analyze_url
from voice.voice_fraud import analyze_transcript
from graph.fraud_graph import FraudGraph
from geo.geo_fraud import GeoFraudLayer, demo_points
from casefile.case_generator import generate_case
from data.synth import generate_fraud_graph

print("Loading models...", file=sys.stderr)
DETECTOR = ScamDetector()
SESSION = FraudSessionDetector(DETECTOR)
GRAPH = FraudGraph()
GEO = GeoFraudLayer()
print("Models ready.", file=sys.stderr)

FRONTEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "frontend", "index.html")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, obj, code=200, ctype="application/json"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send(b"", 204, "text/plain")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(FRONTEND, "rb") as f:
                    return self._send(f.read(), 200, "text/html; charset=utf-8")
            except FileNotFoundError:
                return self._send({"error": "frontend not found"}, 404)
        if self.path == "/health":
            return self._send({"status": "ok", "modules": 7})
        if self.path == "/graph/analyze":
            return self._send(GRAPH.analyze())
        if self.path == "/geo/analyze":
            return self._send(GEO.analyze())
        return self._send({"error": "not found"}, 404)

    def do_POST(self):
        b = self._body()
        p = self.path
        try:
            if p == "/analyze_message":
                return self._send(DETECTOR.predict(b.get("text", "")))
            if p == "/analyze_session":
                session_id = b.get("session_id", "anon")
                text = b.get("text", "")
                # verdict (risk_level/score/rule_categories) is decided here,
                # entirely by the rules + ML classifier, before the LLM
                # explainer ever runs — llm_explainer.apply() only ever
                # rewrites `reason`, so this line is unaffected by whatever
                # happens next.
                verdict = DETECTOR.predict(text)
                llm_explainer.apply(verdict, text)
                return self._send(SESSION.ingest(session_id, text, verdict=verdict))
            if p == "/analyze_url":
                return self._send(analyze_url(b.get("url", "")))
            if p == "/analyze_voice":
                transcript = b.get("transcript", "")
                result = analyze_transcript(transcript, DETECTOR)
                llm_explainer.apply(result, transcript)
                return self._send(result)
            if p == "/graph/add_interaction":
                stat = GRAPH.add_interaction(b["src"], b["dst"],
                                             b.get("type", "message"),
                                             b.get("amount", 0), b.get("ts"))
                return self._send({"ok": True, **stat})
            if p == "/graph/seed":
                GRAPH.bulk_load(generate_fraud_graph())
                return self._send({"ok": True, "seeded": True, **GRAPH.analyze()})
            if p == "/geo/seed":
                GEO.bulk_add(demo_points())
                return self._send({"ok": True, "seeded": True})
            if p == "/case/generate":
                mr = DETECTOR.predict(b["text"]) if b.get("text") else None
                vr = analyze_transcript(b["transcript"], DETECTOR) if b.get("transcript") else None
                ur = analyze_url(b["url"]) if b.get("url") else None
                sr = SESSION.ingest(b["session_id"], b.get("text", "")) if b.get("session_id") else None
                gr = GRAPH.analyze() if GRAPH.G.number_of_nodes() else None
                case = generate_case(message_result=mr, voice_result=vr, url_result=ur,
                                     session_result=sr, graph_result=gr,
                                     subject=b.get("subject"))
                return self._send(case)
        except KeyError as e:
            return self._send({"error": f"missing field {e}"}, 400)
        except Exception as e:
            return self._send({"error": str(e)}, 500)
        return self._send({"error": "not found"}, 404)


def main(port=8000):
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Serving on http://0.0.0.0:{port}", file=sys.stderr)
    srv.serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
