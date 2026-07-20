"""
PLACEHOLDER — awaiting AI/ML integration.

Fixed, obviously-fake node/edge/cluster data so api/network.py has
something to call while the real NetworkX-based graph service is built.
No real graph construction, centrality, or clustering algorithm lives
here on purpose.

--------------------------------------------------------------------
DROP-IN REPLACEMENT CONTRACT — read this before wiring in the real file
--------------------------------------------------------------------
The real implementation must expose two functions with these exact
signatures:

    def get_graph() -> dict
    def get_clusters() -> dict

Per the handoff notes: the real graph is built with NetworkX, in-memory,
computed fresh per request — no Neo4j, no pagination.

get_graph() must return a dict with EXACTLY these keys (matching
schemas.NetworkGraphResponse):
    {
        "nodes": [
            {
                "id": str,
                "phone_number": str,
                "category": str,
                "region": str,
                "risk_score": float,   # 0.0-1.0
            },
            ...
        ],
        "edges": [
            {"source": str, "target": str, "reason": str},
            ...
        ],
    }

get_clusters() must return a dict with EXACTLY this key (matching
schemas.NetworkClustersResponse):
    {
        "clusters": [
            {
                "id": str,
                "node_ids": list[str],
                "risk_score": float,   # 0.0-1.0
                "summary": str,
            },
            ...
        ],
    }

Once these functions exist in the real file, api/network.py only needs
its import line changed (see the comment at the top of that file).
--------------------------------------------------------------------
"""

_FIXED_GRAPH = {
    "nodes": [
        {
            "id": "placeholder-node-1",
            "phone_number": "[PLACEHOLDER-PHONE-0000000001]",
            "category": "[PLACEHOLDER — awaiting AI/ML integration]",
            "region": "[PLACEHOLDER-REGION]",
            "risk_score": 0.5,
        },
        {
            "id": "placeholder-node-2",
            "phone_number": "[PLACEHOLDER-PHONE-0000000002]",
            "category": "[PLACEHOLDER — awaiting AI/ML integration]",
            "region": "[PLACEHOLDER-REGION]",
            "risk_score": 0.5,
        },
    ],
    "edges": [
        {
            "source": "placeholder-node-1",
            "target": "placeholder-node-2",
            "reason": "[PLACEHOLDER — awaiting AI/ML integration]",
        },
    ],
}

_FIXED_CLUSTERS = {
    "clusters": [
        {
            "id": "placeholder-cluster-1",
            "node_ids": ["placeholder-node-1", "placeholder-node-2"],
            "risk_score": 0.5,
            "summary": "[PLACEHOLDER — awaiting AI/ML integration] Fixed fake cluster summary.",
        },
    ],
}


def get_graph() -> dict:
    return {
        "nodes": [dict(n) for n in _FIXED_GRAPH["nodes"]],
        "edges": [dict(e) for e in _FIXED_GRAPH["edges"]],
    }


def get_clusters() -> dict:
    return {"clusters": [dict(c) for c in _FIXED_CLUSTERS["clusters"]]}
