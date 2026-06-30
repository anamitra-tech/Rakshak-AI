"""Simulates 5 fraud sessions and verifies the session-based graph."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.fraud_graph import build_fraud_graph, get_graph_summary

# ---------------------------------------------------------------------------
# Synthetic session data — no LLM or embedding model needed
# ---------------------------------------------------------------------------
SESSIONS = {
    "session_1": [
        {"role": "user",      "content": "CBI ne call kiya",          "scam_type": None},
        {"role": "assistant", "content": "Digital arrest scam...",     "scam_type": "digital_arrest"},
    ],
    "session_2": [
        {"role": "user",      "content": "CBI + bank freeze threat",   "scam_type": None},
        {"role": "assistant", "content": "Digital arrest scam...",     "scam_type": "digital_arrest"},
        {"role": "assistant", "content": "KYC update fraud...",        "scam_type": "bank_otp_kyc"},
    ],
    "session_3": [
        {"role": "user",      "content": "KYC expired message",        "scam_type": None},
        {"role": "assistant", "content": "Bank KYC fraud...",          "scam_type": "bank_otp_kyc"},
    ],
    "session_4": [
        {"role": "user",      "content": "Won a lottery",              "scam_type": None},
        {"role": "assistant", "content": "Lottery prize fraud...",     "scam_type": "lottery_prize_fraud"},
    ],
    "session_5": [
        {"role": "user",      "content": "Police call, arrested",      "scam_type": None},
        {"role": "assistant", "content": "Digital arrest scam...",     "scam_type": "digital_arrest"},
    ],
}

# ---------------------------------------------------------------------------
# Build graph and print summary
# ---------------------------------------------------------------------------
G = build_fraud_graph(SESSIONS)
summary = get_graph_summary(G)

print("=" * 50)
print("FRAUD GRAPH SUMMARY")
print("=" * 50)
print(f"  Total sessions       : {summary['total_sessions']}")
print(f"  Scam types seen      : {summary['scam_types_seen']}")
print(f"  Connected components : {summary['connected_components']}")
print(f"  Largest cluster size : {summary['largest_cluster_size']}")
print()

if summary["possible_coordinated_campaigns"]:
    print("Possible coordinated campaigns:")
    for i, campaign in enumerate(summary["possible_coordinated_campaigns"], 1):
        victims = sorted(n for n in campaign if n.startswith("session_"))
        scams   = sorted(n for n in campaign if not n.startswith("session_"))
        print(f"  Campaign {i}: sessions={victims}  scam_types={scams}")
else:
    print("No coordinated campaigns detected.")

print()
print(f"Graph nodes ({G.number_of_nodes()}):")
for n, d in G.nodes(data=True):
    print(f"  {n}: {d}")
print()
print(f"Graph edges ({G.number_of_edges()}):")
for u, v, d in G.edges(data=True):
    print(f"  {u} -- {v}  {d}")

# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------
assert summary["total_sessions"] == 5, "Expected 5 victim nodes"
assert summary["scam_types_seen"] == 3, "Expected 3 scam cluster nodes"

# Sessions 1, 2, 3, 5 share scam types → should land in the same large component
victim_campaign_sets = [
    {n for n in c if n.startswith("session_")}
    for c in summary["possible_coordinated_campaigns"]
]
linked = any(
    {"session_1", "session_2", "session_3"}.issubset(s)
    for s in victim_campaign_sets
)
assert linked, "Sessions 1, 2, 3 should be in the same coordinated campaign"

# Session 4 (lottery) should NOT appear in any coordinated campaign
session4_in_campaign = any(
    "session_4" in c for c in summary["possible_coordinated_campaigns"]
)
assert not session4_in_campaign, "Session 4 should be isolated (no shared scam types)"

print("=" * 50)
print("ALL ASSERTIONS PASSED")
print("=" * 50)
