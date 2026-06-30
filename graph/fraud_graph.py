"""
MODULE 3 — Fraud Graph Intelligence Engine.

NetworkX-backed graph of phones / bank accounts / devices / users.
Detects fraud clusters (connected components + community detection),
central nodes (PageRank + degree centrality), and per-node risk scores.
Emits graph JSON for frontend visualisation (Cytoscape/D3 friendly).
"""
import networkx as nx

NODE_TYPE_PREFIX = {"PH": "phone", "BA": "bank_account", "DEV": "device", "US": "user"}


def _ntype(node_id):
    return NODE_TYPE_PREFIX.get(str(node_id).split(":", 1)[0], "unknown")


class FraudGraph:
    def __init__(self):
        self.G = nx.MultiDiGraph()

    def add_interaction(self, src, dst, itype="message", amount=0, ts=None):
        for n in (src, dst):
            if n not in self.G:
                self.G.add_node(n, ntype=_ntype(n))
        self.G.add_edge(src, dst, itype=itype, amount=amount, ts=ts)
        return {"nodes": self.G.number_of_nodes(), "edges": self.G.number_of_edges()}

    def bulk_load(self, interactions):
        for it in interactions:
            self.add_interaction(it["src"], it["dst"], it.get("type", "message"),
                                 it.get("amount", 0), it.get("ts"))

    def analyze(self):
        if self.G.number_of_nodes() == 0:
            return {"nodes": [], "edges": [], "clusters": [], "central_nodes": []}

        UG = self.G.to_undirected()
        simpleG = nx.Graph(self.G)   # collapse multi-edges for centrality

        # centrality
        pr = nx.pagerank(simpleG) if simpleG.number_of_edges() else {n: 0 for n in self.G}
        deg = dict(self.G.degree())
        max_deg = max(deg.values()) if deg else 1

        # clusters = connected components (scam rings)
        components = list(nx.connected_components(UG))
        comp_id = {}
        for i, comp in enumerate(components):
            for n in comp:
                comp_id[n] = i

        # per-node risk: blend of centrality, degree, money throughput
        money_through = {n: 0 for n in self.G}
        for u, v, d in self.G.edges(data=True):
            money_through[u] += d.get("amount", 0) or 0
            money_through[v] += d.get("amount", 0) or 0
        max_money = max(money_through.values()) if money_through and max(money_through.values()) else 1

        nodes = []
        for n in self.G.nodes():
            risk = min(1.0, 0.5 * pr.get(n, 0) / (max(pr.values()) or 1)
                       + 0.3 * deg.get(n, 0) / max_deg
                       + 0.2 * money_through[n] / max_money)
            role = self._infer_role(n, deg, money_through)
            nodes.append({
                "id": n, "type": _ntype(n), "cluster": comp_id.get(n, -1),
                "pagerank": round(pr.get(n, 0), 4), "degree": deg.get(n, 0),
                "money": money_through[n], "risk_score": round(risk, 3), "role": role,
            })

        edges = [{"source": u, "target": v, "type": d.get("itype"),
                  "amount": d.get("amount", 0)} for u, v, d in self.G.edges(data=True)]

        # rank clusters by size + aggregate risk
        clusters = []
        for i, comp in enumerate(components):
            members = [nd for nd in nodes if nd["cluster"] == i]
            agg = sum(m["risk_score"] for m in members)
            clusters.append({
                "cluster_id": i, "size": len(comp),
                "risk": round(agg, 2),
                "kingpin": max(members, key=lambda m: m["pagerank"])["id"],
                "members": sorted([m["id"] for m in members]),
            })
        clusters.sort(key=lambda c: c["risk"], reverse=True)

        central = sorted(nodes, key=lambda x: x["pagerank"], reverse=True)[:5]
        return {"nodes": nodes, "edges": edges, "clusters": clusters,
                "central_nodes": [{"id": c["id"], "pagerank": c["pagerank"],
                                   "role": c["role"]} for c in central]}

    def _infer_role(self, n, deg, money):
        nt = _ntype(n)
        if nt == "bank_account" and money[n] > 0:
            return "money_mule"
        if nt == "phone" and deg.get(n, 0) >= 4:
            return "scammer_hub"
        if nt == "device" and deg.get(n, 0) >= 2:
            return "shared_infrastructure"
        if nt == "phone":
            return "likely_victim"
        return "node"


if __name__ == "__main__":
    from data.synth import generate_fraud_graph
    fg = FraudGraph()
    fg.bulk_load(generate_fraud_graph())
    res = fg.analyze()
    print(f"nodes={len(res['nodes'])} edges={len(res['edges'])} clusters={len(res['clusters'])}")
    print("Top clusters:")
    for c in res["clusters"][:3]:
        print(f"  cluster {c['cluster_id']}: size={c['size']} risk={c['risk']} kingpin={c['kingpin']}")
    print("Central nodes:")
    for c in res["central_nodes"]:
        print(f"  {c['id']}  pr={c['pagerank']}  role={c['role']}")


# ---------------------------------------------------------------------------
# Session-based fraud graph (built from live bot session history)
# ---------------------------------------------------------------------------

def build_fraud_graph(sessions=None) -> nx.Graph:
    """Build an undirected graph linking victim sessions to scam-type clusters.

    Pass `sessions` explicitly (a dict of session_id → entry list) to avoid
    importing bot.agent — useful in tests.  When called with no arguments the
    live _sessions dict is pulled from bot.agent at call time.
    """
    if sessions is None:
        from bot.agent import _sessions  # lazy — bot.agent already loaded in webhook
        sessions = _sessions

    G = nx.Graph()
    for session_id, entries in sessions.items():
        scam_entries = [
            e for e in entries
            if e.get("scam_type") and e.get("role") == "assistant"
        ]
        if not scam_entries:
            continue

        scam_types = list({e["scam_type"] for e in scam_entries})
        G.add_node(
            session_id,
            node_type="victim",
            scam_types=scam_types,
            report_count=len(scam_entries),
            profile=entries[0].get("profile", "default"),
        )

        for st in scam_types:
            if not G.has_node(st):
                G.add_node(st, node_type="scam_cluster", count=0)
            G.nodes[st]["count"] += 1
            G.add_edge(session_id, st, weight=len(scam_entries))

        for other_id, other_entries in sessions.items():
            if other_id == session_id:
                continue
            other_types = {
                e["scam_type"] for e in other_entries if e.get("scam_type")
            }
            shared = set(scam_types) & other_types
            if shared:
                G.add_edge(
                    session_id,
                    other_id,
                    edge_type="shared_scam",
                    shared_types=list(shared),
                    weight=len(shared),
                )

    return G


def get_graph_summary(G: nx.Graph) -> dict:
    scam_clusters = [n for n, d in G.nodes(data=True) if d.get("node_type") == "scam_cluster"]
    victim_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "victim"]
    components = list(nx.connected_components(G))
    return {
        "total_sessions": len(victim_nodes),
        "scam_types_seen": len(scam_clusters),
        "connected_components": len(components),
        "largest_cluster_size": max((len(c) for c in components), default=0),
        "possible_coordinated_campaigns": [
            list(c) for c in components if len(c) > 2
        ],
    }
