from rag.retriever import retrieve_and_respond

MESSAGES = [
    "CBI officer called, said I'm under digital arrest, don't tell family",
    "Got SMS saying my SBI KYC expired, share OTP to keep account active",
    "Someone on OLX sent me a QR code to scan to receive payment",
    "Good morning, how are you today",
    "Mujhe ek call aaya CBI ka, arrest warrant bol rahe hain",
    "call me urgent",
    "I received a WhatsApp message saying I won a KBC lottery of 25 lakh",
    "Statement of account zip file aaya WhatsApp pe finance manager ko forward karo",
    "Maine woh zip file khol di computer pe",
    "Sanchar Saathi ka link aaya SIM block ho raha hai",
    "HR ne APK bheja job application form ke liye",
    "CBI ne kaha Aadhaar biometric misuse ho raha hai OTP do",
]

for msg in MESSAGES:
    print("-" * 60)
    r = retrieve_and_respond(msg)
    print(f"USER      : {msg}")
    print(f"SCAM TYPE : {r['scam_type']}")
    print(f"CONFIDENCE: {r['confidence']:.2f}")
    print(f"ENGINE    : {r['engine']}")
    severity = r.get("severity", "")
    if severity:
        print(f"SEVERITY  : {severity}")
    print(f"ANSWER    : {r['answer']}")
    print(f"SOURCE    : {r['source_name']} — {r['source_url']}")
print("-" * 60)
