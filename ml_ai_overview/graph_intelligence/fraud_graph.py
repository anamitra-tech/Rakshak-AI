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


# ---------------------------------------------------------------------------
# Signal weights — higher = stronger evidence of same operator/ring
# entity=10, device=9, script=8, linguistic=7, sig=6,
# voip=5, bg=4, timing=3
# ---------------------------------------------------------------------------

LINK_WEIGHTS = {
    "entity": 10,
    "device": 9,
    "script": 8,
    "linguistic": 7,
    "sig": 6,
    "voip": 5,
    "bg": 4,
    "timing": 3,
}


def build_entity_index(sessions=None) -> dict:
    """Index all fingerprint signals → list of session IDs that share them."""
    if sessions is None:
        from bot.agent import _sessions  # noqa: PLC0415
        sessions = _sessions

    index: dict[str, list] = {}

    for session_id, entries in sessions.items():
        for entry in entries:
            fp = entry.get("fingerprint", {})

            if fp:
                # 1. Hard entities (phone, UPI, URL, account)
                for entity_type, values in fp.get("hard_entities", {}).items():
                    for val in (values or []):
                        if val and len(str(val)) > 3:
                            key = f"entity:{entity_type}:{val}"
                            index.setdefault(key, [])
                            if session_id not in index[key]:
                                index[key].append(session_id)

                # 2. Script verbatim phrases
                for phrase in fp.get("script_fingerprint", []):
                    key = f"script:{phrase}"
                    index.setdefault(key, [])
                    if session_id not in index[key]:
                        index[key].append(session_id)

                # 3. Scammer behavioral signature
                for sig_type, matches in fp.get("scammer_signature", {}).items():
                    for match in matches:
                        key = f"sig:{sig_type}:{match}"
                        index.setdefault(key, [])
                        if session_id not in index[key]:
                            index[key].append(session_id)

                # 4. Background acoustic signals
                for signal in fp.get("background_signals", []):
                    key = f"bg:{signal}"
                    index.setdefault(key, [])
                    if session_id not in index[key]:
                        index[key].append(session_id)

                # 5. Timing / call-sequence signals
                for signal in fp.get("timing_signals", []):
                    key = f"timing:{signal}"
                    index.setdefault(key, [])
                    if session_id not in index[key]:
                        index[key].append(session_id)

                # 6. Device / remote-access signals (ADDITION 1)
                for signal in fp.get("device_signals", []):
                    key = f"device:{signal}"
                    index.setdefault(key, [])
                    if session_id not in index[key]:
                        index[key].append(session_id)

                # 7. Linguistic fingerprint (ADDITION 2)
                for tell_type, matches in fp.get("linguistic_fingerprint", {}).items():
                    for match in matches:
                        key = f"linguistic:{tell_type}:{match}"
                        index.setdefault(key, [])
                        if session_id not in index[key]:
                            index[key].append(session_id)

            # 8. VoIP/Twilio geo metadata — present even without fingerprint (ADDITION 3)
            twilio = entry.get("twilio_metadata", {})
            if twilio:
                country = twilio.get("from_country", "")
                if country:
                    key = f"voip:country:{country}"
                    index.setdefault(key, [])
                    if session_id not in index[key]:
                        index[key].append(session_id)

    return index


def build_fraud_graph_with_entities(sessions=None) -> nx.Graph:
    """Combines scam-type graph with cross-session signal linkage."""
    G = build_fraud_graph(sessions)
    index = build_entity_index(sessions)

    for signal_key, sessions_list in index.items():
        if len(sessions_list) < 2:
            continue

        prefix = signal_key.split(":")[0]
        weight = LINK_WEIGHTS.get(prefix, 2)

        G.add_node(
            signal_key,
            node_type="signal",
            signal_type=prefix,
            value=signal_key,
            linked_sessions=len(sessions_list),
            weight=weight,
        )

        for sess in sessions_list:
            if G.has_node(sess):
                G.add_edge(sess, signal_key, edge_type=prefix, weight=weight)

        # Direct session-session edges only for high-confidence signals
        if weight >= 6:
            for i in range(len(sessions_list)):
                for j in range(i + 1, len(sessions_list)):
                    existing = G.get_edge_data(sessions_list[i], sessions_list[j])
                    if existing is not None:
                        existing["weight"] += weight
                    else:
                        G.add_edge(
                            sessions_list[i],
                            sessions_list[j],
                            edge_type="confirmed_link",
                            via=signal_key,
                            weight=weight,
                        )

    return G


def get_hard_links(G: nx.Graph) -> list:
    """Returns all shared signals seen in 2+ sessions with weight >= 6."""
    hard_links = []
    for node, data in G.nodes(data=True):
        if data.get("node_type") == "signal":
            n_sessions = data.get("linked_sessions", 0)
            weight = data.get("weight", 0)
            if n_sessions >= 2 and weight >= 6:
                hard_links.append({
                    "signal_type": data["signal_type"],
                    "value": data["value"],
                    "linked_sessions": n_sessions,
                    "confidence": "HIGH" if weight >= 8 else "MEDIUM",
                    "alert": (
                        f"[{data['signal_type'].upper()}] "
                        f"Same signal in {n_sessions} reports "
                        f"— possible same fraud ring"
                    ),
                })
    return sorted(hard_links, key=lambda x: x["linked_sessions"], reverse=True)


def get_ring_clusters(G: nx.Graph) -> list:
    """Returns probable fraud rings — groups of 2+ sessions linked by confirmed signals."""
    rings = []
    for component in nx.connected_components(G):
        sessions = [n for n in component if G.nodes[n].get("node_type") == "victim"]
        if len(sessions) < 2:
            continue

        signals = [
            n for n in component
            if G.nodes[n].get("node_type") == "signal"
            and G.nodes[n].get("weight", 0) >= 6
        ]
        if not signals:
            continue

        rings.append({
            "sessions": sessions,
            "victim_count": len(sessions),
            "confirmed_signals": len(signals),
            "ring_confidence": (
                "HIGH" if len(signals) >= 3
                else "MEDIUM" if len(signals) >= 2
                else "LOW"
            ),
            "signal_types": list({G.nodes[s]["signal_type"] for s in signals}),
        })

    return sorted(rings, key=lambda x: x["victim_count"], reverse=True)
