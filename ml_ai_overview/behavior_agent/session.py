"""
MODULE 2 — Active Fraud Session Detector.

In-memory streaming logic that tracks an ongoing interaction by session id
(phone number / chat id) and detects scam interaction *patterns* over time:
  - urgency escalation across turns
  - OTP / UPI / money request sequence
  - repeated high-risk messages from same entity
  - sustained session length (digital-arrest hostage pattern)

Redis can be swapped in for the dict store without changing the interface.
"""
import time
from collections import defaultdict


class SessionStore:
    """Swap this for a Redis-backed store in production; same interface."""
    def __init__(self):
        self._s = defaultdict(lambda: {"events": [], "first": None})

    def add(self, sid, event):
        s = self._s[sid]
        if s["first"] is None:
            s["first"] = event["ts"]
        s["events"].append(event)
        # keep last 50 events per session (sliding window)
        s["events"] = s["events"][-50:]
        return s

    def get(self, sid):
        return self._s.get(sid)


class FraudSessionDetector:
    def __init__(self, detector):
        self.detector = detector          # reuse Module 1
        self.store = SessionStore()

    def is_already_active(self, session_id) -> bool:
        """Read-only peek at whether this session was ALREADY flagged
        active/high-risk from PRIOR messages, without ingesting a new event
        or affecting any state. Used to distinguish a first-person
        conversational follow-up ("he says he'll arrest me") within an
        established high-risk session from a fresh session's first message,
        which must still go through full classification/display even if it
        happens to trip the same thresholds on its own — see
        webhook/app.py's _is_conversational_followup gate. Callers must
        still call ingest() as normal for the current message; this only
        reports the state as of the *previous* call."""
        s = self.store.get(session_id)
        if s is None or not s["events"]:
            return False
        return self._evaluate(session_id, s, None)["active_scam_session"] == "YES"

    def ingest(self, session_id, text, ts=None, verdict=None):
        ts = ts or time.time()
        # Callers that already computed (and possibly LLM-second-opinion
        # overrode) a verdict for this exact text can pass it in directly, so
        # the override is reflected in session history instead of being
        # silently recomputed and discarded here.
        if verdict is None:
            verdict = self.detector.predict(text)
        event = {"ts": ts, "text": text, "score": verdict["score"],
                 "rules": verdict["rule_categories"]}
        s = self.store.add(session_id, event)
        return self._evaluate(session_id, s, verdict)

    def _evaluate(self, sid, s, last_verdict):
        events = s["events"]
        n = len(events)
        scores = [e["score"] for e in events]
        duration = events[-1]["ts"] - s["first"]

        # signal: urgency escalation (scores trending up)
        escalating = n >= 3 and scores[-1] > scores[0] and scores[-1] >= 0.6

        # signal: credential+money request sequence anywhere in session
        all_rules = set(r for e in events for r in e["rules"])
        request_sequence = bool({"credential_request", "money_demand"} & all_rules) and \
                           "authority_impersonation" in all_rules

        # signal: repeated high-risk messages
        high_risk_count = sum(1 for x in scores if x >= 0.7)
        repeated = high_risk_count >= 2

        # signal: sustained session (hostage pattern) — >3 min of high-risk contact
        sustained = duration > 180 and high_risk_count >= 1

        active = escalating or request_sequence or repeated or sustained

        # severity
        if request_sequence or (sustained and high_risk_count >= 3):
            severity = "CRITICAL"
        elif repeated or escalating:
            severity = "HIGH"
        elif high_risk_count >= 1:
            severity = "LOW"
        else:
            severity = "LOW"

        triggers = []
        if escalating: triggers.append("urgency escalation across messages")
        if request_sequence: triggers.append("authority + credential/money request sequence")
        if repeated: triggers.append(f"{high_risk_count} high-risk messages from same entity")
        if sustained: triggers.append(f"sustained high-risk session ({int(duration)}s)")

        return {
            "session_id": sid,
            "active_scam_session": "YES" if active else "NO",
            "severity": severity if active else "NONE",
            "message_count": n,
            "duration_seconds": round(duration, 1),
            "high_risk_messages": high_risk_count,
            "session_triggers": triggers,
            "last_message": last_verdict,
        }


if __name__ == "__main__":
    from ml.detector import ScamDetector
    fsd = FraudSessionDetector(ScamDetector())
    sid = "PH:+91-9000000001"
    convo = [
        "Hello sir, this is regarding your account.",
        "This is CBI officer. Your Aadhaar is linked to a money laundering case.",
        "You are under digital arrest. Do not disconnect or tell anyone.",
        "Transfer 50000 to this RBI safe account immediately to avoid arrest. Share OTP.",
    ]
    t0 = time.time()
    for i, m in enumerate(convo):
        r = fsd.ingest(sid, m, ts=t0 + i * 60)
        print(f"msg{i+1}: active={r['active_scam_session']} sev={r['severity']:8s} triggers={r['session_triggers']}")
