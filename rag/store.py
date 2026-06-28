from pathlib import Path

import chromadb

from rag.embedder import embed

_STORE_PATH = Path(__file__).parent / "chroma_store"
_COLLECTION = "scam_cards"


def _client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=str(_STORE_PATH))


def store_exists() -> bool:
    return _STORE_PATH.exists() and any(_STORE_PATH.iterdir())


def build_store(cards: list) -> None:
    client = _client()
    collection = client.get_or_create_collection(
        name=_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    ids, embeddings, metadatas = [], [], []
    for card in cards:
        text = (
            card.title
            + " "
            + " ".join(card.example_messages)
            + " "
            + " ".join(card.red_flags)
        )
        ids.append(card.id)
        embeddings.append(embed(text))
        metadatas.append({
            "scam_type": card.scam_type,
            "channel": card.channel,
            "what_to_do": card.what_to_do,
            "source_name": card.source.get("name", ""),
            "source_url": card.source.get("url", ""),
        })

    collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)


def retrieve(query: str, n: int = 3) -> list:
    client = _client()
    collection = client.get_collection(_COLLECTION)
    results = collection.query(query_embeddings=[embed(query)], n_results=n)

    out = []
    for i, doc_id in enumerate(results["ids"][0]):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        out.append({
            "id": doc_id,
            "scam_type": meta["scam_type"],
            "what_to_do": meta["what_to_do"],
            "source_name": meta["source_name"],
            "source_url": meta["source_url"],
            "score": max(0.0, 1.0 - distance),
        })
    return out
