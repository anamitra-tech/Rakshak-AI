"""
MODULE 7 — Auto Case File Generator.

Builds a structured, auditable intelligence package for any FRAUD detection:
risk summary, detected signals, timeline, graph connections, recommended action.
Exports JSON (always). The same dict can be rendered to PDF downstream.
Designed for legal-admissibility: every field is traceable to a source signal.
"""
import hashlib
import json
import time
from datetime import datetime, timezone


def generate_case(message_result=None, session_result=None, url_result=None,
                  voice_result=None, graph_result=None, subject=None):
    ts = datetime.now(timezone.utc)
    signals, timeline = [], []
    max_score = 0.0

    if message_result:
        max_score = max(max_score, message_result.get("score", 0))
        signals += [{"source": "message", "signal": s} for s in message_result.get("signals", [])]
        timeline.append({"t": ts.isoformat(), "event": "Message analysed",
                         "verdict": message_result.get("risk_level"),
                         "score": message_result.get("score")})
    if voice_result:
        max_score = max(max_score, voice_result.get("score", 0))
        signals += [{"source": "voice", "signal": s} for s in voice_result.get("signals", [])]
        timeline.append({"t": ts.isoformat(), "event": "Call transcript analysed",
                         "verdict": voice_result.get("risk_level"),
                         "score": voice_result.get("score")})
    if url_result:
        max_score = max(max_score, url_result.get("score", 0))
        signals += [{"source": "link", "signal": s} for s in url_result.get("signals", [])]
        timeline.append({"t": ts.isoformat(), "event": "Link analysed",
                         "verdict": url_result.get("risk_level"),
                         "score": url_result.get("score")})
    if session_result and session_result.get("active_scam_session") == "YES":
        signals += [{"source": "session", "signal": s} for s in session_result.get("session_triggers", [])]
        timeline.append({"t": ts.isoformat(),
                         "event": f"Active scam session ({session_result.get('severity')})",
                         "verdict": "ACTIVE", "score": None})

    graph_connections = []
    if graph_result:
        for c in graph_result.get("clusters", [])[:3]:
            graph_connections.append({"cluster_id": c["cluster_id"], "size": c["size"],
                                      "kingpin": c["kingpin"], "risk": c["risk"]})

    if max_score >= 0.7:
        classification = "CONFIRMED_FRAUD"
    elif max_score >= 0.4:
        classification = "SUSPECTED_FRAUD"
    else:
        classification = "LOW_RISK"

    case = {
        "case_id": "CASE-" + ts.strftime("%Y%m%d") + "-" +
                   hashlib.sha1(str(time.time()).encode()).hexdigest()[:6].upper(),
        "generated_at": ts.isoformat(),
        "subject": subject or "Unknown entity",
        "classification": classification,
        "overall_risk_score": round(max_score, 3),
        "risk_summary": _summary(classification, signals, session_result),
        "detected_signals": signals,
        "timeline": timeline,
        "graph_connections": graph_connections,
        "recommended_action": _action(classification),
        "reporting_channel": {"helpline": "1930", "portal": "cybercrime.gov.in",
                              "agency_alert": "MHA I4C" if classification == "CONFIRMED_FRAUD" else None},
        "audit": {"engine_version": "1.0", "deterministic": True,
                  "evidence_count": len(signals)},
    }
    case["integrity_hash"] = hashlib.sha256(
        json.dumps(case, sort_keys=True).encode()).hexdigest()
    return case


def _summary(classification, signals, session):
    n = len(signals)
    base = f"{classification.replace('_',' ').title()} with {n} corroborating signal(s)."
    if session and session.get("active_scam_session") == "YES":
        base += f" Active scam session detected at {session.get('severity')} severity."
    return base


def _action(classification):
    return {
        "CONFIRMED_FRAUD": "Freeze linked accounts, alert telecom for number block, "
                           "notify victim, escalate package to MHA/I4C for cross-jurisdiction action.",
        "SUSPECTED_FRAUD": "Flag for analyst review, monitor session, pre-warn potential victim.",
        "LOW_RISK": "Log for pattern baselining. No immediate action.",
    }[classification]


if __name__ == "__main__":
    from ml.detector import ScamDetector
    from voice.voice_fraud import analyze_transcript
    from graph.fraud_graph import FraudGraph
    from data.synth import generate_fraud_graph
    d = ScamDetector()
    mr = d.predict("CBI officer, arrest warrant, transfer settlement to RBI account, share OTP")
    vr = analyze_transcript("Do not tell family, you are under arrest, transfer to safe account", d)
    fg = FraudGraph(); fg.bulk_load(generate_fraud_graph()); gr = fg.analyze()
    case = generate_case(message_result=mr, voice_result=vr, graph_result=gr,
                         subject="PH:+91-9000000001")
    print(json.dumps(case, indent=2)[:1200])
