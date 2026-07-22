import sys
sys.stdout.reconfigure(encoding="utf-8")

import json

from rag.legal_store import build_store, store_exists

if store_exists():
    print("Legal-info store already exists — skipping build.")
else:
    with open("kb/legal_info.json", encoding="utf-8") as f:
        entries = json.load(f)
    print(f"Embedding {len(entries)} legal-info entries...")
    build_store(entries)
    print(f"{len(entries)} entries embedded with BGE-M3 -> FAISS")
