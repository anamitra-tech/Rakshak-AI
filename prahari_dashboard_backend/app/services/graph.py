"""
Real Fraud Network Intelligence service — replaces graph_placeholder.py.

Backed by dashboard/graph_model.py + dashboard/seed_data.py: a NetworkX
graph over real FRAUD-verdict nodes (feedback/data/feedback.db corrections +
rakshak_eval_testset.json cases, both scored through the real
ml.detector.ScamDetector), linked by shared script similarity, shared
callback numbers, and temporal proximity. See dashboard/graph_model.py's
docstring for exactly how edges are derived.

That module's node/edge/cluster shape doesn't match this API's
NetworkNode/NetworkEdge/FraudCluster schemas field-for-field, so this file
adapts/transforms the real output into the existing contract rather than
changing the contract itself:
  - node_id / rule_categories / telecom_circle / score  -> id+phone_number /
    category / region / risk_score
  - edge weight/edge_types/evidence                     -> a single human-
    readable `reason` string (joined evidence)
  - cluster_id/size/members/rule_categories/circles      -> id/node_ids/
    risk_score/summary

get_graph() and get_clusters() each rebuild the graph fresh per call (the
dataset here is small — dashboard/seed_data.py's own docstring notes ~37
nodes as of this writing — so recomputing is cheap and always reflects the
latest feedback.db corrections).
"""
from dashboard.graph_model import build_graph
from dashboard.seed_data import load_seed_nodes

# feedback_db nodes don't carry a stored score (feedback/store.py doesn't
# persist one at correction time — see seed_data.py's score=None comment);
# every node reaching this graph is already FRAUD-verdict by construction
# (both seed sources filter to FRAUD only), so a score-less node still
# clearly belongs above the FRAUD threshold (0.7 in ml/detector.py) rather
# than defaulting to 0 or being dropped.
_MISSING_SCORE_FALLBACK = 0.9

# Below this, a "cluster" is just one unlinked node — already visible in the
# node list, and not itself an actionable fraud-ring signal worth a summary
# card. Filtering these out of get_clusters() only changes which connected
# components get surfaced as a "cluster" here; every node still appears via
# get_graph().
_MIN_CLUSTER_SIZE = 2


def _node_risk_score(node: dict) -> float:
    score = node.get("score")
    return float(score) if score is not None else _MISSING_SCORE_FALLBACK


def _build():
    nodes = load_seed_nodes()
    return build_graph(nodes)


def get_graph() -> dict:
    result = _build()

    out_nodes = [
        {
            "id": n["node_id"],
            "phone_number": n["node_id"],
            "category": ", ".join(n.get("rule_categories") or []) or "uncategorized",
            "region": n.get("telecom_circle") or "Unknown",
            "risk_score": _node_risk_score(n),
        }
        for n in result["nodes"]
    ]

    out_edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "reason": "; ".join(e.get("evidence") or []) or "; ".join(e.get("edge_types") or []),
        }
        for e in result["edges"]
    ]

    return {"nodes": out_nodes, "edges": out_edges}


def get_clusters() -> dict:
    result = _build()
    risk_by_id = {n["node_id"]: _node_risk_score(n) for n in result["nodes"]}

    clusters = []
    for c in result["clusters"]:
        if c["size"] < _MIN_CLUSTER_SIZE:
            continue
        member_scores = [risk_by_id[m] for m in c["members"] if m in risk_by_id]
        avg_risk = sum(member_scores) / len(member_scores) if member_scores else _MISSING_SCORE_FALLBACK

        categories = ", ".join(c.get("rule_categories") or []) or "no specific pattern"
        circles = ", ".join(c.get("telecom_circles") or []) or "unknown circles"
        summary = (
            f"{c['size']} linked reports across {circles}, matching {categories} "
            f"pattern(s) — linked by shared script, callback number, or timing."
        )

        clusters.append({
            "id": str(c["cluster_id"]),
            "node_ids": c["members"],
            "risk_score": round(min(1.0, avg_risk), 3),
            "summary": summary,
        })

    return {"clusters": clusters}
