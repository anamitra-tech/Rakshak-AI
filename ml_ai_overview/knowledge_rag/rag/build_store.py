import sys
sys.stdout.reconfigure(encoding="utf-8")

from kb.loader import load_cards
from rag.store import build_store, store_exists

if store_exists():
    print("Store already exists — skipping build.")
else:
    cards = load_cards()
    print(f"Embedding {len(cards)} cards...")
    build_store(cards)
    print(f"{len(cards)} cards embedded with BGE-M3 → FAISS")
