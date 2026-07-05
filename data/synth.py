"""
Synthetic data generation for the Digital Public Safety Intelligence System.

Generates labelled corpora for:
  - scam / safe text messages (Hinglish + Hindi + English)
  - phishing / safe URLs
  - fraud interaction graphs (clustered scam rings)

No external dependencies. Deterministic via seed for demo reproducibility.
"""
import random

# ---------------------------------------------------------------------------
# MESSAGE TEMPLATES
# ---------------------------------------------------------------------------

# FRAUD: digital-arrest impersonation (CBI / ED / Customs / Police)
DIGITAL_ARREST = [
    "Sir this is CBI officer. Your Aadhaar is linked to money laundering case. Do not disconnect call.",
    "Main ED se bol raha hoon. Aapke naam pe arrest warrant nikla hai. Turant video call pe aaiye.",
    "Customs department. A parcel in your name contains illegal items. Police case register ho gaya hai.",
    "Hum Mumbai police se hain. Aapka number drug trafficking me use hua hai. Abhi paise transfer karke verify karo.",
    "This is a digital arrest notice. Stay on video call until investigation complete. Do not tell family.",
    "CBI headquarters. Aapke bank account se illegal transaction hua hai, immediate arrest hoga agar cooperate nahi kiya.",
    "Narcotics control bureau. Your SIM is involved in a case. Send money to safe RBI account now to avoid jail.",
    "Aap digital arrest me hain. Camera band mat karo. Settlement ke liye 50000 abhi bhejo.",
]

# FRAUD: bank / OTP / UPI
BANK_OTP = [
    "Dear customer your account will be blocked. Share OTP to keep KYC active immediately.",
    "Aapka SBI account suspend ho gaya hai. OTP batao warna account band ho jayega.",
    "Bank se call. Debit card expire ho raha hai, CVV aur OTP share karo urgent.",
    "Congratulations! UPI cashback 9999 credit hua. Claim ke liye is link pe OTP daalo.",
    "Your KYC pending hai. Click link and enter UPI PIN to update otherwise account freeze.",
    "Electricity bill overdue, connection cut tonight. Pay now on this number to avoid disconnection.",
]

# FRAUD: investment / lottery / job
INVEST_LOTTERY = [
    "Invest 5000 get 50000 in 2 days guaranteed. Limited slots, join Telegram group fast.",
    "You won 25 lakh KBC lottery! Pay processing fee to claim your prize immediately.",
    "Work from home, earn 5000 daily. Just pay registration 999 to start today.",
    "Crypto double scheme, send USDT now and receive 2x within 24 hours guaranteed profit.",
    "Aapko part time job mila hai, 3000 rupaye registration bhejo aur kaam shuru karo.",
]

# FRAUD: sophisticated scripts that deliberately avoid obvious trigger words
# (no "OTP", "arrest", "guaranteed", "urgent") — an investment-webinar
# follow-up upsell, a courier "document issue" verification-call lure. Mirrors
# the harder "expert_scam" style in rakshak_eval_testset.json, so the model
# doesn't just learn "calm, business-sounding = safe".
SUBTLE_LURE = [
    "I'm following up on the trading session you joined recently. A few clients are moving into the next round before it closes this week, want me to note you down with a starting amount?",
    "Your portfolio review is due, the fund has been performing steadily and there's room for a few more early participants before allocation closes this month.",
    "Your shipment is on hold at customs because of a document mismatch, this is common for international parcels, I can help sort it over a quick verification call so it doesn't get returned.",
    "There's a minor issue with your parcel's paperwork, nothing serious, let's do a short call to confirm a few details so it starts moving again.",
]

# FRAUD: isolation / anti-verification tactics — category-agnostic. These
# discourage the victim from independently verifying through the bank,
# police, or family, regardless of which scam category (bank fraud, digital
# arrest, courier, family emergency) is running underneath. See
# ml/detector.py's "isolation_tactics" rule, which treats this pattern as
# near-deterministic on its own.
ISOLATION_TACTICS = [
    # discourage calling the bank/police through official channels
    "Sir please do not call the bank yourself, that line is always busy and it will only cause delay. I will verify it for you.",
    "Police station line abhi busy hai, dubara report karne se sirf duplicate complaint banegi. Mujhe hi verify karne do.",
    "Don't waste time calling customer care, they will only put you on hold. I can sort this out directly.",
    # discourage contact with family
    "No need to worry your son or daughter about this, I will handle everything myself so you don't have to disturb them.",
    "Ghar walo ko batane ki zaroorat nahi hai, main khud sab sambhal lunga, unhe pareshan mat karo.",
    "There's no reason to trouble your family with this right now, let's keep it between us until it's resolved.",
    # offering to take over / act "for" or "on behalf of" the victim
    "Just give me the phone, I will enter the details myself so you don't need to worry about the process.",
    "Aap tension mat lo, main aapki taraf se yeh transaction khud kar dunga.",
    "You don't need to do anything, I will complete the verification on your behalf right now.",
    # courier/agent arriving in person instead of a branch visit
    "There is no need for you to visit the branch. Our representative will come to your home to collect the documents and card.",
    "Humara agent aapke ghar aayega cash aur card collect karne, aapko bank jaane ki zaroorat nahi hai.",
    "A courier will be sent to your address to pick up the card and papers, no need to step out.",
]

# SAFE: legit bank / normal conversation (false-positive traps)
SAFE_MSGS = [
    "Your OTP for login is 482910. Do not share it with anyone. - HDFC Bank",
    "Rs 2,000 debited from a/c XX4521 on 12-06 to Amazon. Bal 14,300. Not you? Call 1800.",
    "Hi beta, reached office safely. Will call in evening. Take care.",
    "Reminder: your electricity bill of Rs 1,240 is due on 30th. Pay via official BSES app.",
    "Order shipped! Your package arrives tomorrow. Track on the app.",
    "Movie tonight at 8? Let me know if you're free.",
    "Salary of Rs 54,200 credited to your account. - ICICI",
    "Your appointment with Dr. Sharma is confirmed for Monday 10 AM.",
    "Kal milte hain coffee ke liye, 5 baje theek hai?",
    "Your train PNR 245... is confirmed. Coach B4 seat 32.",
    "Account statement for May is ready. Download from net banking.",
    "Thanks for your payment of Rs 499 to Netflix. Subscription active.",

    # Hospital / appointment reminders
    "This is a reminder from City Hospital for your check-up appointment tomorrow at 11am with Dr. Mehta.",
    "Your lab test report is ready for pickup, please visit the diagnostic center anytime before 6pm.",
    "Reminder: your dental cleaning is scheduled for Thursday 4pm, call the clinic if you need to reschedule.",
    # Delivery notifications
    "Your Flipkart order will be delivered by this evening, please keep your phone reachable for the delivery partner.",
    "Package out for delivery, expected between 1pm and 4pm today.",
    "Your grocery order has been packed and will reach you within the hour.",
    # Insurance renewals
    "Your health insurance policy is due for renewal next month, let us know if you'd like a callback to discuss options.",
    "Bike insurance premium receipt has been emailed to you, thank you for renewing on time.",
    "Your term insurance renewal is due in two weeks, no action needed until then.",
    # Government / Panchayat calls
    "This is from the Gram Panchayat office informing you about the vaccination camp scheduled this Friday.",
    "Calling from the municipal office regarding your property tax receipt, it has been generated and is available online.",
    "This is the local ward office reminding residents about the water supply maintenance on Sunday morning.",
    # Telecom recharge reminders
    "Your mobile plan validity ends tomorrow, recharge anytime to continue uninterrupted service.",
    "Data balance is running low, top up whenever convenient from the app.",
    "Your broadband bill has been generated, pay by the 5th to avoid a late fee.",
    # Utility complaint follow-ups
    "Following up on your water supply complaint, the technician has been assigned and will visit within two days.",
    "Your internet service complaint has been resolved, please let us know if the issue persists.",
    "Update on your gas cylinder booking: the delivery is scheduled for tomorrow afternoon.",
    # Bank fraud-monitoring / precaution advisories (legit banks proactively
    # reassuring the customer — a distinct pattern from an actual scam ask)
    "This is a routine call from your credit card provider to confirm a recent purchase looks correct — no action is needed if it was you.",
    "As a precaution we've temporarily paused a transaction that looked unusual, feel free to call our helpline number from your statement to confirm.",
    "Just confirming your recent transaction was successful, thank you for banking with us.",
    # Genuine bank fraud-alert calls: card already blocked (past, completed
    # bank action) + new card couriered (delivered TO the customer, not
    # collected) + explicit invitation to verify independently — the exact
    # opposite shape of a scam script, which asks for money/codes and
    # discourages verification. Added after a real false positive where the
    # base classifier alone (no rule fired) scored one of these 0.527/SUSPICIOUS.
    "This is Rahul from the bank's fraud prevention team. We detected an unauthorized transaction attempt on your credit card and have already blocked it as a precaution — no money has been debited. A new card will be couriered to your registered address within a week. If you'd like to verify this yourself, please hang up and call the number on the back of your old card or visit your nearest branch.",
    "We noticed a suspicious transaction attempt on your debit card about ten minutes ago and blocked it immediately as a precaution. No money was debited. Your replacement card will arrive by courier in 5-7 working days. You're welcome to call our official helpline to confirm before doing anything else.",
    "This is your bank's fraud monitoring desk. We've already blocked your card after an unauthorized attempt was flagged. You don't need to share any details on this call — a new card is being couriered to you, and you can always verify this call independently through the branch or the number on your card.",
    "Aapke card par ek suspicious transaction ki koshish hui thi, humne turant card block kar diya hai suraksha ke liye, koi paisa nahi kata hai. Naya card courier se aapke ghar aa jayega. Aap chahe to bank ki official helpline par call karke ya branch jaakar confirm kar sakte hain.",
    # Hinglish / casual family variants
    "Maine tumhara internet bill pay kar diya hai, ab tension lene ki zaroorat nahi.",
    "Aaj shaam tak parcel aa jayega, ghar par koi rahe please.",
    "Doctor ne kaha appointment agle hafte reschedule kar do, koi jaldi nahi hai.",
]

SHORT_FRAUD = ["call me urgent send money", "OTP batao abhi", "arrest warrant turant call karo", "paise bhejo emergency"]
SHORT_SAFE = ["call me later", "ok done", "ghar aa raha hoon", "thanks see you"]


def generate_messages(n_per_class=120, seed=42):
    random.seed(seed)
    rows = []
    fraud_pools = [
        ("digital_arrest", DIGITAL_ARREST), ("bank_otp", BANK_OTP), ("investment", INVEST_LOTTERY),
        ("isolation_scam", ISOLATION_TACTICS), ("subtle_lure", SUBTLE_LURE),
    ]
    for _ in range(n_per_class):
        cat, pool = random.choice(fraud_pools)
        base = random.choice(pool)
        rows.append((_augment(base, seed=random.random()), "FRAUD", cat))
    for _ in range(n_per_class):
        rows.append((_augment(random.choice(SAFE_MSGS), seed=random.random()), "SAFE", "legit"))
    for s in SHORT_FRAUD:
        rows.append((s, "FRAUD", "short"))
    for s in SHORT_SAFE:
        rows.append((s, "SAFE", "short"))
    random.shuffle(rows)
    return rows


def _augment(text, seed=0.0):
    """Light adversarial augmentation: spacing, leetspeak-ish, fillers."""
    r = random.Random(seed)
    t = text
    if r.random() < 0.3:
        t = t.replace("o", "0", 1) if "o" in t else t
    if r.random() < 0.3:
        t = t + " " + r.choice(["please", "abhi", "jaldi", "now", "ji"])
    if r.random() < 0.2:
        t = t.replace(" ", "  ", 1)
    return t


# ---------------------------------------------------------------------------
# URL DATASET
# ---------------------------------------------------------------------------
PHISH_URLS = [
    "http://sbi-kyc-update.xyz/login", "http://hdfc.secure-verify.tk/otp",
    "https://bit.ly/3xScam", "http://icici-bank.account-suspend.ru/",
    "http://rbi-refund.online/claim", "https://paytm-cashback.win/redeem",
    "http://192.168.4.21/bank", "http://amaz0n-prize.club/win",
    "http://gov-in-arrest.cf/notice", "https://tinyurl.com/freecash99",
    "http://upi-verify.kyc-update.top/", "http://netfIix-billing.info/pay",
]
SAFE_URLS = [
    "https://www.onlinesbi.sbi/", "https://www.hdfcbank.com/", "https://www.icicibank.com/",
    "https://www.amazon.in/", "https://www.irctc.co.in/", "https://www.rbi.org.in/",
    "https://paytm.com/", "https://www.netflix.com/", "https://cybercrime.gov.in/",
    "https://www.google.com/",
]

def generate_urls():
    return [(u, "DANGEROUS") for u in PHISH_URLS] + [(u, "SAFE") for u in SAFE_URLS]


# ---------------------------------------------------------------------------
# FRAUD GRAPH GENERATOR (clustered scam rings)
# ---------------------------------------------------------------------------
def generate_fraud_graph(seed=7):
    """Returns list of interaction dicts: {src, dst, type, amount}."""
    random.seed(seed)
    interactions = []
    # Ring A: 1 mastermind, 3 mules, many victims
    mastermind = "PH:+91-9000000001"
    mules = [f"BA:ACC-MULE-{i}" for i in range(3)]
    victims = [f"PH:+91-9{random.randint(100000000,999999999)}" for _ in range(8)]
    for v in victims:
        interactions.append({"src": v, "dst": mastermind, "type": "call", "amount": 0})
        m = random.choice(mules)
        interactions.append({"src": v, "dst": m, "type": "transaction", "amount": random.randint(20000, 200000)})
        interactions.append({"src": m, "dst": mastermind, "type": "transaction", "amount": random.randint(50000, 300000)})
    # Ring B: separate smaller ring
    mm2 = "PH:+91-9000000002"
    mule2 = "BA:ACC-MULE-9"
    for _ in range(4):
        v = f"PH:+91-8{random.randint(100000000,999999999)}"
        interactions.append({"src": v, "dst": mm2, "type": "call", "amount": 0})
        interactions.append({"src": v, "dst": mule2, "type": "transaction", "amount": random.randint(10000, 80000)})
    interactions.append({"src": mule2, "dst": mm2, "type": "transaction", "amount": 150000})
    # device link bridging the two rings (shared infra)
    interactions.append({"src": mastermind, "dst": "DEV:IMEI-SHARED-01", "type": "device", "amount": 0})
    interactions.append({"src": mm2, "dst": "DEV:IMEI-SHARED-01", "type": "device", "amount": 0})
    return interactions


if __name__ == "__main__":
    msgs = generate_messages()
    print(f"messages: {len(msgs)}  sample: {msgs[0]}")
    print(f"urls: {len(generate_urls())}")
    print(f"graph interactions: {len(generate_fraud_graph())}")
