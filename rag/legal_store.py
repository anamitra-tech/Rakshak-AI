"""
FAISS store for kb/legal_info.json — kept entirely separate from
rag/store.py's scam-pattern index (kb/scams.json) so retrieval quality of
one KB can't degrade the other; same embed()/faiss pattern, different
source data and index files.
"""
import json
from pathlib import Path

import faiss
import numpy as np

from rag.embedder import embed

_STORE_PATH = Path(__file__).parent / "legal_faiss_store"
_INDEX_FILE = _STORE_PATH / "index.faiss"
_ENTRIES_FILE = _STORE_PATH / "entries.json"


def store_exists() -> bool:
    return _INDEX_FILE.exists() and _ENTRIES_FILE.exists()


def build_store(entries: list[dict]) -> None:
    texts = [
        e["title"] + " " + e["body"] + " " + " ".join(e.get("keywords", []))
        for e in entries
    ]

    embeddings = embed(texts)
    vectors = np.array(embeddings, dtype="float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    _STORE_PATH.mkdir(exist_ok=True)
    faiss.write_index(index, str(_INDEX_FILE))

    with open(_ENTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)


def retrieve(query: str, n: int = 2) -> list:
    index = faiss.read_index(str(_INDEX_FILE))
    with open(_ENTRIES_FILE, encoding="utf-8") as f:
        entries = json.load(f)

    q_vec = np.array(embed([query]), dtype="float32")
    faiss.normalize_L2(q_vec)

    scores, indices = index.search(q_vec, n)

    out = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        entry = entries[idx]
        out.append({**entry, "score": float(score)})
    return out
