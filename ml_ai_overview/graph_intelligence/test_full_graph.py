"""Full fraud graph intelligence test — 5 sessions, pre-computed fingerprints.

Expected hard links (weight >= 6, 2+ sessions):
  entity:phone_numbers:+919876543210  → sess_a, sess_e        (weight=10 HIGH)
  entity:upi_ids:scam@ybl             → sess_c, sess_d        (weight=10 HIGH)
  script:digital arrest               → sess_a, sess_b, sess_c (weight=8  HIGH)
  script:stay on the call             → sess_a, sess_c        (weight=8  HIGH)
Total = 4 hard links

Expected rings: all 5 sessions in one component via shared signals.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.fraud_graph import (
    build_fraud_graph_with_entities,
    get_graph_summary,
    get_hard_links,
    get_ring_clusters,
)

# ---------------------------------------------------------------------------
# Synthetic sessions with pre-computed fingerprints — no LLM or model calls
# ---------------------------------------------------------------------------
SESSIONS = {
    "sess_a": [
        {
            "role": "user",
            "content": "+919876543210 CBI ka call, digital arrest, do not tell family, background mein typing thi",
            "scam_type": None,
        },
        {
            "role": "assistant",
            "content": "Digital arrest scam response...",
            "scam_type": "digital_arrest",
            "fingerprint": {
                "hard_entities": {
                    "phone_numbers": ["+919876543210"], "upi_ids": [], "urls": [],
                    "bank_accounts": [], "amounts_inr": [], "officer_names": [],
                    "agency_names": [], "locations_mentioned": [],
                },
                "scammer_signature": {"isolation_tactics": ["dont tell anyone"]},
                "script_fingerprint": ["digital arrest", "stay on the call"],
                "timing_signals": [],
                "background_signals": ["typing ki awaaz"],
                "device_signals": [],
                "linguistic_fingerprint": {},
                "fingerprint_strength": "HIGH",
            },
            "twilio_metadata": {"from_country": "IN", "from_city": "Mumbai", "num_media": "0"},
        },
    ],
    "sess_b": [
        {
            "role": "user",
            "content": "+918765432109 se call, digital arrest, do not disconnect, senior officer ne baat ki, background mein aur log the",
            "scam_type": None,
        },
        {
            "role": "assistant",
            "content": "Digital arrest scam response...",
            "scam_type": "digital_arrest",
            "fingerprint": {
                "hard_entities": {
                    "phone_numbers": ["+918765432109"], "upi_ids": [], "urls": [],
                    "bank_accounts": [], "amounts_inr": [], "officer_names": [],
                    "agency_names": [], "locations_mentioned": [],
                },
                "scammer_signature": {"escalation_sequence": ["senior officer"]},
                "script_fingerprint": ["digital arrest", "do not disconnect"],
                "timing_signals": [],
                "background_signals": ["typing ki awaaz", "dusre log bol rahe"],
                "device_signals": [],
                "linguistic_fingerprint": {},
                "fingerprint_strength": "HIGH",
            },
        },
    ],
    "sess_c": [
        {
            "role": "user",
            "content": "Phir se call aaya doosre number se, digital arrest, stay on the call, same background awaaz, UPI scam@ybl pe paisa maanga",
            "scam_type": None,
        },
        {
            "role": "assistant",
            "content": "Digital arrest + UPI fraud response...",
            "scam_type": "digital_arrest",
            "fingerprint": {
                "hard_entities": {
                    "phone_numbers": [], "upi_ids": ["scam@ybl"], "urls": [],
                    "bank_accounts": [], "amounts_inr": [], "officer_names": [],
                    "agency_names": [], "locations_mentioned": [],
                },
                "scammer_signature": {},
                "script_fingerprint": ["digital arrest", "stay on the call"],
                "timing_signals": ["phir se call aaya"],
                "background_signals": ["dusre log bol rahe"],
                "device_signals": [],
                "linguistic_fingerprint": {},
                "fingerprint_strength": "HIGH",
            },
        },
    ],
    "sess_d": [
        {
            "role": "user",
            "content": "Lottery ka message aaya, KBC winner, UPI scam@ybl pe bhejo, different number tha",
            "scam_type": None,
        },
        {
            "role": "assistant",
            "content": "Lottery prize fraud response...",
            "scam_type": "lottery_prize_fraud",
            "fingerprint": {
                "hard_entities": {
                    "phone_numbers": [], "upi_ids": ["scam@ybl"], "urls": [],
                    "bank_accounts": [], "amounts_inr": [], "officer_names": [],
                    "agency_names": [], "locations_mentioned": [],
                },
                "scammer_signature": {},
                "script_fingerprint": [],
                "timing_signals": [],
                "background_signals": [],
                "device_signals": [],
                "linguistic_fingerprint": {},
                "fingerprint_strength": "LOW",
            },
        },
    ],
    "sess_e": [
        {
            "role": "user",
            "content": "+919876543210 same number, RBI officer bola, account freeze, abhi ke abhi paisa transfer karo",
            "scam_type": None,
        },
        {
            "role": "assistant",
            "content": "RBI impersonation scam response...",
            "scam_type": "digital_arrest",
            "fingerprint": {
                "hard_entities": {
                    "phone_numbers": ["+919876543210"], "upi_ids": [], "urls": [],
                    "bank_accounts": [], "amounts_inr": [], "officer_names": [],
                    "agency_names": [], "locations_mentioned": [],
                },
                "scammer_signature": {"pressure_phrases": ["abhi ke abhi"]},
                "script_fingerprint": ["account freeze"],
                "timing_signals": [],
                "background_signals": [],
                "device_signals": [],
                "linguistic_fingerprint": {},
                "fingerprint_strength": "MEDIUM",
            },
            "twilio_metadata": {"from_country": "IN", "from_city": "Delhi", "num_media": "0"},
        },
    ],
}

# ---------------------------------------------------------------------------
# Build and analyse
# ---------------------------------------------------------------------------
G = build_fraud_graph_with_entities(SESSIONS)
summary = get_graph_summary(G)
hard_links = get_hard_links(G)
rings = get_ring_clusters(G)

# ── Print ────────────────────────────────────────────────────────────────────
print("=" * 60)
print("FULL FRAUD GRAPH INTELLIGENCE REPORT")
print("=" * 60)
print(f"\nGraph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"\nSummary:")
print(f"  Total sessions       : {summary['total_sessions']}")
print(f"  Scam types seen      : {summary['scam_types_seen']}")
print(f"  Connected components : {summary['connected_components']}")
print(f"  Largest cluster size : {summary['largest_cluster_size']}")

print(f"\nHard Links ({len(hard_links)}):")
for lnk in hard_links:
    print(f"  [{lnk['confidence']}] {lnk['signal_type']}: {lnk['value']!r} "
          f"-> {lnk['linked_sessions']} sessions")

print(f"\nFraud Rings ({len(rings)}):")
for ring in rings:
    print(f"  [{ring['ring_confidence']}] {ring['victim_count']} victims "
          f"| {ring['confirmed_signals']} signals "
          f"| types={sorted(ring['signal_types'])}")
    print(f"    sessions: {sorted(ring['sessions'])}")

# ── Assertions ────────────────────────────────────────────────────────────
assert summary["total_sessions"] == 5, \
    f"Expected 5 victim nodes, got {summary['total_sessions']}"

assert len(hard_links) >= 4, (
    f"Expected >= 4 hard links, got {len(hard_links)}: "
    + str([l["value"] for l in hard_links])
)

assert len(rings) >= 1, "Expected at least 1 ring cluster"

high_rings = [r for r in rings if r["ring_confidence"] == "HIGH"]
assert high_rings, "Expected at least 1 HIGH confidence ring"

# sess_a, sess_b, sess_c, sess_e must be in the same ring
main_ring = next(
    (r for r in rings
     if all(s in r["sessions"] for s in ["sess_a", "sess_b", "sess_c", "sess_e"])),
    None,
)
assert main_ring is not None, \
    "sess_a, sess_b, sess_c, sess_e must be in the same ring cluster"
assert "script" in main_ring["signal_types"], \
    f"Main ring signal_types must contain 'script': {main_ring['signal_types']}"
assert "entity" in main_ring["signal_types"], \
    f"Main ring signal_types must contain 'entity': {main_ring['signal_types']}"

# sess_d must appear in the graph (connected via UPI to sess_c)
assert G.has_node("sess_d"), "sess_d must be a node in the graph"

# A and E linked by phone number (hard entity)
assert G.has_edge("sess_a", "sess_e") or G.has_edge("sess_e", "sess_a"), \
    "sess_a and sess_e must be directly linked (shared phone number)"

# C and D linked by UPI ID
assert G.has_edge("sess_c", "sess_d") or G.has_edge("sess_d", "sess_c"), \
    "sess_c and sess_d must be directly linked (shared UPI ID)"

print("\n" + "=" * 60)
print("ALL ASSERTIONS PASSED")
print("=" * 60)
