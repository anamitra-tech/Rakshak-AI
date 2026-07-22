"""
Deterministic hybrid retrieval over kb/legal_info.json for the /chat endpoint
(assistant/pipeline.py). No LLM anywhere in this file — dense similarity, BM25
scoring, and reciprocal rank fusion are all pure, reproducible math, kept
separate from the LLM-driven query-rewrite/rerank stages in pipeline.py by
design (see CLAUDE.md's /chat spec, point 4: "keep deterministic parts
deterministic").

Reuses rag/legal_store.py's existing FAISS index unchanged (kb/legal_info.json
already has its own store, isolated from kb/scams.json's) — this module adds a
sparse (BM25) index alongside it and fuses the two ranked lists.
"""
import json

from rank_bm25 import BM25Okapi

from rag.legal_store import retrieve as _dense_retrieve

_KB_PATH = "kb/legal_info.json"

_bm25_index: BM25Okapi | None = None
_bm25_entries: list[dict] | None = None
_bm25_tokens_cache: list[list[str]] | None = None


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _entry_text(entry: dict) -> str:
    return entry["title"] + " " + entry["body"] + " " + " ".join(entry.get("keywords", []))


def _load_bm25_index() -> tuple[BM25Okapi, list[dict]]:
    global _bm25_index, _bm25_entries, _bm25_tokens_cache
    if _bm25_index is not None and _bm25_entries is not None:
        return _bm25_index, _bm25_entries

    with open(_KB_PATH, encoding="utf-8") as f:
        entries = json.load(f)

    tokenized = [_tokenize(_entry_text(e)) for e in entries]
    index = BM25Okapi(tokenized)

    _bm25_index, _bm25_entries, _bm25_tokens_cache = index, entries, tokenized
    return index, entries


def dense_search(query: str, top_n: int = 10) -> list[dict]:
    """Wraps rag.legal_store.retrieve unchanged; returns entries with a real
    cosine-similarity 'score' field (0-1) attached — this is the deterministic
    signal pipeline.py's confidence floor gates on."""
    return _dense_retrieve(query, n=top_n)


def sparse_search(query: str, top_n: int = 10) -> list[dict]:
    """BM25 over the same kb/legal_info.json entries, independent index from
    the FAISS one. Returns entries with a 'score' field (raw BM25 score, not
    comparable across queries/corpora — only used for within-query ranking
    inside reciprocal_rank_fusion, never against the dense score directly)."""
    index, entries = _load_bm25_index()
    scores = index.get_scores(_tokenize(query))
    ranked = sorted(range(len(entries)), key=lambda i: scores[i], reverse=True)[:top_n]
    return [{**entries[i], "score": float(scores[i])} for i in ranked if scores[i] > 0]


def reciprocal_rank_fusion(
    dense_results: list[dict], sparse_results: list[dict], k: int = 60
) -> list[dict]:
    """Standard RRF: fused_score(doc) = sum over each ranked list containing
    doc of 1/(k + rank). Pure function of two rank-ordered lists; does not
    touch either list's raw score. Returns entries sorted by fused score
    descending, each carrying its original dense cosine 'score' (if it
    appeared in dense_results) as 'dense_score' for the confidence-floor
    check downstream — a doc that only BM25 found has 'dense_score': None.
    """
    fused: dict[str, dict] = {}

    for rank, entry in enumerate(dense_results):
        eid = entry["id"]
        fused.setdefault(eid, {"entry": entry, "rrf_score": 0.0, "dense_score": None})
        fused[eid]["rrf_score"] += 1.0 / (k + rank + 1)
        fused[eid]["dense_score"] = entry["score"]

    for rank, entry in enumerate(sparse_results):
        eid = entry["id"]
        if eid not in fused:
            fused[eid] = {"entry": entry, "rrf_score": 0.0, "dense_score": None}
        fused[eid]["rrf_score"] += 1.0 / (k + rank + 1)

    ordered = sorted(fused.values(), key=lambda x: x["rrf_score"], reverse=True)
    return [
        {**item["entry"], "rrf_score": item["rrf_score"], "dense_score": item["dense_score"]}
        for item in ordered
    ]


def hybrid_retrieve(query: str, top_n: int = 10) -> list[dict]:
    dense = dense_search(query, top_n=top_n)
    sparse = sparse_search(query, top_n=top_n)
    return reciprocal_rank_fusion(dense, sparse)
