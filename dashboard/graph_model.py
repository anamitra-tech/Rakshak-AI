"""
Graph clustering + layout for the investigator dashboard.

Builds a NetworkX graph over the node list from seed_data.py, connecting
cases that look like the same operator/ring:

  - shared_script:            TF-IDF cosine similarity over text_excerpt
                               (reuses sklearn's TfidfVectorizer, already a
                               project dependency via ml/detector.py -- no
                               new deps).
  - shared_callback_number:   a number mentioned inside one case's text is
                               another case's own node_id.
  - temporal_proximity:       two feedback_db-sourced cases (real
                               timestamps only -- see note below) reported
                               within TEMPORAL_WINDOW of each other.

temporal_proximity deliberately never fires between two
eval_testset_synthetic nodes, or between a synthetic and a real node: their
timestamps are fabricated for demo spread (see seed_data.py's
_synthetic_timestamp), not evidence of anything, and treating them as if
they were real reporting times would manufacture a fake cluster.

Does not touch ml/detector.py, casefile/case_generator.py, or graph/
fraud_graph.py -- this is a new, separate module.
"""
from datetime import datetime, timedelta

import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SCRIPT_SIMILARITY_THRESHOLD = 0.5
TEMPORAL_WINDOW = timedelta(hours=48)


def _shared_script_edges(nodes: list) -> list:
    texts = [n["text_excerpt"] for n in nodes]
    if len(texts) < 2:
        return []
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(texts)
    sims = cosine_similarity(matrix)

    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            sim = float(sims[i][j])
            if sim >= SCRIPT_SIMILARITY_THRESHOLD:
                edges.append({
                    "source": nodes[i]["node_id"],
                    "target": nodes[j]["node_id"],
                    "edge_type": "shared_script",
                    "weight": round(sim, 3),
                    "evidence": f"similar script text (cosine similarity {sim:.2f})",
                })
    return edges


def _shared_callback_number_edges(nodes: list) -> list:
    by_id = {n["node_id"]: n for n in nodes}
    edges = []
    seen_pairs = set()
    for n in nodes:
        for mentioned in n.get("mentioned_numbers", []):
            if mentioned in by_id and mentioned != n["node_id"]:
                pair = tuple(sorted((n["node_id"], mentioned)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                edges.append({
                    "source": pair[0],
                    "target": pair[1],
                    "edge_type": "shared_callback_number",
                    "weight": 1.0,
                    "evidence": f"{n['node_id']} mentions {mentioned} as a callback/reference number",
                })
    return edges


def _temporal_proximity_edges(nodes: list) -> list:
    real_time_nodes = [n for n in nodes if not n.get("timestamp_is_synthetic")]
    edges = []
    for i in range(len(real_time_nodes)):
        for j in range(i + 1, len(real_time_nodes)):
            a, b = real_time_nodes[i], real_time_nodes[j]
            ta = datetime.fromisoformat(a["timestamp_utc"])
            tb = datetime.fromisoformat(b["timestamp_utc"])
            delta = abs(ta - tb)
            if delta <= TEMPORAL_WINDOW:
                edges.append({
                    "source": a["node_id"],
                    "target": b["node_id"],
                    "edge_type": "temporal_proximity",
                    "weight": round(1.0 - (delta / TEMPORAL_WINDOW), 3),
                    "evidence": f"reported {delta} apart (both real timestamps)",
                })
    return edges


def build_graph(nodes: list) -> dict:
    edges = (
        _shared_script_edges(nodes)
        + _shared_callback_number_edges(nodes)
        + _temporal_proximity_edges(nodes)
    )

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["node_id"], **n)
    for e in edges:
        if G.has_edge(e["source"], e["target"]):
            G[e["source"]][e["target"]]["weight"] += e["weight"]
            G[e["source"]][e["target"]]["edge_types"].append(e["edge_type"])
            G[e["source"]][e["target"]]["evidence"].append(e["evidence"])
        else:
            G.add_edge(
                e["source"], e["target"],
                weight=e["weight"],
                edge_types=[e["edge_type"]],
                evidence=[e["evidence"]],
            )

    components = list(nx.connected_components(G))
    cluster_of = {}
    for i, comp in enumerate(components):
        for node_id in comp:
            cluster_of[node_id] = i

    positions = nx.spring_layout(G, seed=42, weight="weight") if G.number_of_nodes() else {}

    out_nodes = []
    for n in nodes:
        pos = positions.get(n["node_id"], (0.0, 0.0))
        out_nodes.append({
            **n,
            "cluster_id": cluster_of.get(n["node_id"], -1),
            "x": round(float(pos[0]), 4),
            "y": round(float(pos[1]), 4),
        })

    out_edges = []
    for u, v, d in G.edges(data=True):
        out_edges.append({
            "source": u,
            "target": v,
            "weight": round(d["weight"], 3),
            "edge_types": d["edge_types"],
            "evidence": d["evidence"],
        })

    clusters = []
    for i, comp in enumerate(components):
        members = [n for n in out_nodes if n["cluster_id"] == i]
        categories = sorted({c for m in members for c in m["rule_categories"]})
        circles = sorted({m["telecom_circle"] for m in members})
        clusters.append({
            "cluster_id": i,
            "size": len(comp),
            "members": sorted(comp),
            "rule_categories": categories,
            "telecom_circles": circles,
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)

    return {"nodes": out_nodes, "edges": out_edges, "clusters": clusters}


if __name__ == "__main__":
    from dashboard.seed_data import load_seed_nodes
    result = build_graph(load_seed_nodes())
    print(f"nodes={len(result['nodes'])} edges={len(result['edges'])} clusters={len(result['clusters'])}")
    for c in result["clusters"][:5]:
        print(f"  cluster {c['cluster_id']}: size={c['size']} categories={c['rule_categories']} circles={c['telecom_circles']}")
