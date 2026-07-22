"""Add 5 PIB-sourced scam cards: format → dedup → append → rebuild store → test."""
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
KB_PATH = ROOT / "kb" / "scams.json"
STORE_PATH = ROOT / "rag" / "chroma_store"

OVERLAP_THRESHOLD = 0.6

# "summary" is used only for dedup scoring; stripped before writing to KB
NEW_CARDS = [
    {
        "id": "pib_digital_arrest_001",
        "scam_type": "digital_arrest",
        "channel": "video_call",
        "languages": ["en", "hi", "hinglish"],
        "title": "Beware of 'Digital Arrest' Fraud Calls",
        "summary": (
            "Fraudsters impersonating CBI ED Customs or Police officers call citizens "
            "claiming they are under digital arrest for crimes like money laundering or "
            "drug trafficking. Victims are kept on video call for hours or days and "
            "coerced into transferring funds to avoid fake prosecution."
        ),
        "example_messages": [
            "Main CBI officer hoon. Aapka Aadhaar money laundering case mein linked hai. Aap digital arrest mein hain.",
            "This is CBI. You are under digital arrest for drug trafficking. Do not disconnect this call.",
            "Your Aadhaar is connected to a money laundering case. Stay on video call or you will be arrested.",
            "ED office se bol raha hoon. Aapke naam pe arrest warrant hai. Abhi video call pe rahiye.",
        ],
        "call_script": (
            "Caller claims to be CBI, ED, Customs, or Police and says victim is linked "
            "to money laundering or drug trafficking. Victim is told they are under "
            "'digital arrest' and must remain on video call for hours or days. Caller "
            "creates fear of immediate arrest and eventually demands money transfer."
        ),
        "red_flags": [
            "Caller claims to be CBI, ED, NCB, or Police officer",
            "Says your Aadhaar or phone number is linked to a crime",
            "Demands you stay on video call — 'digital arrest'",
            "Asks for money transfer to 'clear your name'",
            "Shows fake arrest warrants or court orders on screen",
            "Creates extreme urgency and fear",
        ],
        "what_to_do": (
            "Hang up immediately. No government agency conducts arrests via video call. "
            "Real agencies send written notices, not video calls. Do not pay anything. "
            "Call your family. Report on 1930 or cybercrime.gov.in."
        ),
        "if_already_opened": (
            "If you already paid, immediately call your bank to reverse the transfer, "
            "then report on helpline 1930."
        ),
        "post_open_keywords": [
            "digital arrest", "cbi call", "ed officer", "stay on call", "warrant",
        ],
        "severity": "critical",
        "source": {
            "name": "PIB MHA Advisory — Digital Arrest Scams",
            "url": "https://pib.gov.in/allRel.aspx",
            "date": "2024-2026",
        },
    },
    {
        "id": "pib_investment_fraud_001",
        "scam_type": "investment_fraud",
        "channel": "whatsapp",
        "languages": ["en", "hi", "hinglish"],
        "title": "Fake Stock Trading Apps and WhatsApp Investment Groups",
        "summary": (
            "Fraudsters add victims to WhatsApp or Telegram groups posing as SEBI advisors "
            "offering guaranteed profits through fake trading applications. Small initial "
            "withdrawals succeed to build confidence. Once large deposits arrive the app "
            "freezes or demands additional tax payments before funds vanish."
        ),
        "example_messages": [
            "Join our exclusive investment group. Our SEBI advisor gives guaranteed 40% monthly returns.",
            "Sir aapko Rs 10,000 invest karne par guaranteed Rs 14,000 return milega 30 din mein.",
            "Our trading app gave 38% profit last month. Download link sent — start with Rs 5,000.",
            "You have earned Rs 85,000 profit. To withdraw, pay 18% GST of Rs 15,300 first.",
        ],
        "call_script": (
            "Victim is added to a WhatsApp or Telegram group where members post screenshots "
            "of large profits. A 'SEBI advisor' recommends a trading app not on official "
            "stores. Small withdrawals succeed to build trust. Victim deposits large amounts. "
            "App then freezes or demands a tax payment before withdrawal. Funds disappear."
        ),
        "red_flags": [
            "Unsolicited WhatsApp or Telegram add to investment group",
            "Promises guaranteed returns of 30–40 percent monthly",
            "Asks to install a trading app not on Play Store or App Store",
            "Initial small withdrawal succeeds to build trust",
            "Suddenly requires tax payment to withdraw profits",
            "Advisor claims SEBI registration but cannot be verified at sebi.gov.in",
        ],
        "what_to_do": (
            "Never invest via WhatsApp or Telegram tips. Verify any advisor's SEBI "
            "registration at sebi.gov.in. Legitimate investments never guarantee fixed "
            "returns. Report to 1930 or cybercrime.gov.in."
        ),
        "if_already_opened": (
            "Stop all further payments. Screenshot the app and chats. Report on 1930 "
            "and file at cybercrime.gov.in with transaction IDs."
        ),
        "post_open_keywords": [
            "investment group", "sebi advisor", "guaranteed returns", "trading app",
            "withdraw profit", "tax payment",
        ],
        "severity": "high",
        "source": {
            "name": "PIB SEBI Advisory — Fake Trading Apps",
            "url": "https://pib.gov.in/allRel.aspx",
            "date": "2024-2026",
        },
    },
    {
        "id": "pib_courier_scam_001",
        "scam_type": "digital_arrest",
        "channel": "call",
        "languages": ["en", "hi", "hinglish"],
        "title": "Fake FedEx Courier Scam with Drugs Planted in Package",
        "summary": (
            "Caller poses as FedEx or another courier firm stating that a shipment registered "
            "under the victim's Aadhaar was intercepted containing contraband. The call "
            "transfers to a fake Narcotics or CBI officer who demands settlement money "
            "to close the case before a public arrest."
        ),
        "example_messages": [
            "This is FedEx. A parcel registered to your Aadhaar contains illegal drugs. Please stay on the line.",
            "Sir, aapke naam ka courier Mumbai customs mein pakda gaya. Usme drugs hain.",
            "This is NCB. Your package contained cocaine. You must pay settlement to avoid arrest.",
            "Your parcel was flagged at Delhi airport. Drugs and fake currency found. Officer calling shortly.",
        ],
        "call_script": (
            "Caller poses as FedEx or Blue Dart agent, says a package in victim's name "
            "was seized containing drugs, fake currency, or SIM cards. Call is transferred "
            "to a 'CBI' or 'NCB' officer who shows a fake FIR and demands immediate "
            "settlement money. Victim is told to keep the matter secret from family."
        ),
        "red_flags": [
            "Call from courier company about a package you did not send",
            "Package allegedly contains drugs, fake currency, or SIM cards",
            "Call transferred to fake CBI or NCB officer",
            "Demands immediate money transfer to avoid arrest",
            "Asks you to keep the call secret from family",
        ],
        "what_to_do": (
            "Hang up. Legitimate courier companies and government agencies never resolve "
            "criminal cases over a phone call. No phone payment can settle a drug case. "
            "Report on 1930 immediately."
        ),
        "if_already_opened": (
            "Call your bank immediately to block the transfer. Report at 1930 and "
            "cybercrime.gov.in. Save all call recordings as evidence."
        ),
        "post_open_keywords": [
            "fedex", "courier", "package drugs", "ncb officer", "parcel seized", "customs call",
        ],
        "severity": "critical",
        "source": {
            "name": "PIB MHA I4C Advisory — Courier Scam",
            "url": "https://cybercrime.gov.in",
            "date": "2024-2026",
        },
    },
    {
        "id": "pib_sextortion_001",
        "scam_type": "multi_call_escalation",
        "channel": "video_call",
        "languages": ["en", "hi", "hinglish"],
        "title": "Sextortion via WhatsApp Video Call",
        "summary": (
            "Fraudster initiates a WhatsApp video call during which a woman appears briefly "
            "on screen. Victim is then blackmailed with a recording and threatened with exposure "
            "to contacts and employer unless ransom is paid. Compliance never ends the extortion."
        ),
        "example_messages": [
            "I have your video. Pay Rs 50,000 or I will send it to your family and office.",
            "Aapka video mere paas hai. Agar paise nahi diye toh contacts ko bhej dunga.",
            "You accepted a WhatsApp call. The recording will go viral unless you pay now.",
            "Your contacts will receive this video in 2 hours unless Rs 25,000 is transferred.",
        ],
        "call_script": (
            "Fraudster calls victim on WhatsApp video. A woman briefly appears on screen. "
            "Call ends and victim immediately receives a message saying the video was recorded "
            "and will be shared with contacts and employer unless payment is made via UPI or "
            "crypto. Paying does not stop the blackmail — demands escalate further."
        ),
        "red_flags": [
            "Unexpected video call from an unknown number",
            "Woman appears briefly on screen during the call",
            "Immediately followed by blackmail threat and payment demand",
            "Demands urgent payment via UPI, crypto, or gift cards",
            "Threatens to share video with family and employer",
        ],
        "what_to_do": (
            "Do not pay. Paying emboldens the scammer and demands will increase. Block the "
            "number. Take screenshots of threats. Report at cybercrime.gov.in with evidence "
            "and call 1930."
        ),
        "if_already_opened": (
            "Stop all payments immediately — paying will not end the blackmail. Block the "
            "number, collect evidence, and report at cybercrime.gov.in. Victims are not at fault."
        ),
        "post_open_keywords": [
            "video call recorded", "whatsapp video", "sextortion", "pay or share",
            "blackmail", "send to contacts",
        ],
        "severity": "high",
        "source": {
            "name": "PIB MHA Advisory — Sextortion Scams",
            "url": "https://pib.gov.in/allRel.aspx",
            "date": "2024-2026",
        },
    },
    {
        "id": "pib_fake_customs_001",
        "scam_type": "digital_arrest",
        "channel": "call",
        "languages": ["en", "hi", "hinglish"],
        "title": "Fake Customs Officer — Package Seized at Airport",
        "summary": (
            "Caller impersonates a Customs officer claiming that a consignment addressed to "
            "the victim was seized at the airport for containing prohibited goods. Victim is "
            "coerced into paying clearance fees by phone or threatened with detention. "
            "Payments escalate with each interaction."
        ),
        "example_messages": [
            "This is Customs Department. A package in your name at Delhi Airport contains banned items.",
            "Sir, aapke naam ka parcel airport customs mein roka gaya hai. Duty bharne par hi milega.",
            "Your shipment has been seized. Pay Rs 15,000 customs clearance fee to avoid arrest.",
            "Customs officer here. Illegal goods found in your parcel. Pay now or face legal action.",
        ],
        "call_script": (
            "Caller poses as an airport Customs officer and says a package in the victim's "
            "name was seized for containing banned items. Victim is asked to pay a clearance "
            "fee by phone to release the shipment. Amount keeps increasing. If victim resists, "
            "caller threatens public arrest and media exposure."
        ),
        "red_flags": [
            "Call claiming your package was seized at airport customs",
            "Asks for customs duty payment over the phone to release package",
            "Threatens arrest if payment is not made immediately",
            "May show fake customs officer ID during a video call",
            "Amount increases each time the victim makes a payment",
        ],
        "what_to_do": (
            "Real customs issues arrive via official written notices, never phone calls. "
            "Never pay customs duty over a phone call. Visit the customs office in person "
            "for any genuine shipment query. Report to 1930."
        ),
        "if_already_opened": (
            "Contact your bank to block the transfer. Report at 1930 and visit a police "
            "station to file an FIR with the caller number and UPI ID used."
        ),
        "post_open_keywords": [
            "customs", "airport package", "seized parcel", "customs duty", "clearance fee",
        ],
        "severity": "high",
        "source": {
            "name": "PIB Customs MHA Advisory — Fake Customs Calls",
            "url": "https://pib.gov.in/allRel.aspx",
            "date": "2024-2026",
        },
    },
]


def _text(card: dict) -> str:
    return card.get("summary") or card.get("what_to_do") or card.get("title") or ""


def _overlap(new_text: str, existing_text: str) -> float:
    new_words = set(new_text.lower().split())
    if not new_words:
        return 0.0
    existing_words = set(existing_text.lower().split())
    return len(new_words & existing_words) / len(new_words)


def dedup(new_cards: list, kb_cards: list) -> list:
    existing_ids = {c.get("id") for c in kb_cards}
    kb_texts = [_text(c) for c in kb_cards]
    unique = []
    for card in new_cards:
        if card["id"] in existing_ids:
            log.info("DUP  (id match): %s", card["id"])
            continue
        card_text = _text(card)
        max_overlap = max(
            (_overlap(card_text, kt) for kt in kb_texts if kt),
            default=0.0,
        )
        if max_overlap > OVERLAP_THRESHOLD:
            log.info("DUP  (overlap=%.2f): %s", max_overlap, card["id"])
        else:
            log.info("NEW  (overlap=%.2f): %s", max_overlap, card["id"])
            unique.append(card)
    return unique


if __name__ == "__main__":
    kb_cards = json.loads(KB_PATH.read_text(encoding="utf-8"))
    log.info("Existing KB: %d cards", len(kb_cards))

    passing = dedup(NEW_CARDS, kb_cards)
    log.info("%d / %d cards passed dedup", len(passing), len(NEW_CARDS))

    if not passing:
        print("No new cards to add — all flagged as duplicates.")
        raise SystemExit(0)

    for card in passing:
        card.pop("summary", None)

    kb_cards.extend(passing)
    KB_PATH.write_text(
        json.dumps(kb_cards, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Wrote %d cards to kb/scams.json", len(kb_cards))

    if STORE_PATH.exists():
        shutil.rmtree(STORE_PATH)
        log.info("Deleted existing chroma_store — will rebuild")

    print("\n── Rebuilding vector store ──")
    r = subprocess.run(
        [sys.executable, "-m", "rag.build_store"],
        cwd=ROOT,
    )
    if r.returncode != 0:
        print("ERROR: store rebuild failed")
        raise SystemExit(1)

    print("\n── Bot agent tests ──")
    r = subprocess.run(
        [sys.executable, "-m", "bot.test_agent"],
        cwd=ROOT,
    )
    if r.returncode != 0:
        print("ERROR: bot tests failed")
        raise SystemExit(1)

    print(f"\n✓ Final KB count: {len(kb_cards)} cards")
