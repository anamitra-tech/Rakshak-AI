import json
from pathlib import Path

import faiss
import numpy as np

from rag.embedder import embed

_STORE_PATH = Path(__file__).parent / "faiss_store"
_INDEX_FILE = _STORE_PATH / "index.faiss"
_CARDS_FILE = _STORE_PATH / "cards.json"


def store_exists() -> bool:
    return _INDEX_FILE.exists() and _CARDS_FILE.exists()


def build_store(cards: list) -> None:
    texts = [
        card.title
        + " "
        + " ".join(card.example_messages)
        + " "
        + " ".join(card.red_flags)
        for card in cards
    ]

    embeddings = embed(texts)
    vectors = np.array(embeddings, dtype="float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    _STORE_PATH.mkdir(exist_ok=True)
    faiss.write_index(index, str(_INDEX_FILE))

    meta = [
        {
            "id": card.id,
            "scam_type": card.scam_type,
            "what_to_do": card.what_to_do,
            "source_name": card.source.get("name", ""),
            "source_url": card.source.get("url", ""),
            "if_already_opened": card.if_already_opened,
            "severity": card.severity,
        }
        for card in cards
    ]
    with open(_CARDS_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def retrieve(query: str, n: int = 3) -> list:
    index = faiss.read_index(str(_INDEX_FILE))
    with open(_CARDS_FILE, encoding="utf-8") as f:
        cards = json.load(f)

    q_vec = np.array(embed([query]), dtype="float32")
    faiss.normalize_L2(q_vec)

    scores, indices = index.search(q_vec, n)

    out = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        card = cards[idx]
        out.append({
            "id": card["id"],
            "scam_type": card["scam_type"],
            "what_to_do": card["what_to_do"],
            "source_name": card["source_name"],
            "source_url": card["source_url"],
            "if_already_opened": card.get("if_already_opened", ""),
            "severity": card.get("severity", ""),
            "score": float(score),
        })
    return out
