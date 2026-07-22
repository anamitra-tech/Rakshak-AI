"""
Single computed-once accessor for the dashboard's graph, shared by
investigator_app.py (HTML page) and api.py (REST endpoints) so both read
the same in-memory result instead of recomputing it, and so neither module
has to import the other.
"""
from functools import lru_cache

from dashboard.graph_model import build_graph
from dashboard.seed_data import load_seed_nodes


@lru_cache(maxsize=1)
def get_graph() -> dict:
    return build_graph(load_seed_nodes())
