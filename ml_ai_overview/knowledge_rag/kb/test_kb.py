from kb.loader import load_cards

cards = load_cards()
print(f"Loaded {len(cards)} scam card(s).")

types = sorted({c.scam_type for c in cards})
if types:
    print("Types found:", ", ".join(types))
else:
    print("No types yet — knowledge base is empty.")
