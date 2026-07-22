// Maps the unified-classifier category keys to readable chip labels.
// Keep in sync with RuleCategory in prahari_dashboard_backend/app/models/schemas.py.
export const CATEGORY_LABELS = {
  authority_impersonation: 'Authority Impersonation',
  credential_request: 'Credential Request',
  urgency_coercion: 'Urgency / Coercion',
  money_demand: 'Money Demand',
  reward_bait: 'Reward Bait',
  isolation_tactics: 'Isolation Tactics',
  otp_readout_request: 'OTP Readout Request',
  card_collection_request: 'Card Collection Request',
  relative_impersonation: 'Relative Impersonation',
  telecom_impersonation: 'Telecom Impersonation',
  extortion_threat: 'Extortion Threat',
  malicious_link_bait: 'Malicious Link Bait',
  malware_attachment_delivery: 'Malware Attachment Delivery',
  job_fraud: 'Job Fraud',
};

export const categoryLabel = (key) => CATEGORY_LABELS[key] || key;

export const VERDICT_STYLES = {
  SAFE: 'bg-emerald-50 text-emerald-600',
  SUSPICIOUS: 'bg-amber-50 text-amber-600',
  SCAM: 'bg-red-50 text-red-600',
};

export const SCAM_TREND_DATA = {
  authority_impersonation: {
    trends: 'Spiking 200% this quarter, often involving fake CBI, Customs, or Police officers demanding immediate video calls.',
    patterns: 'Scammer sends a fabricated official notice (e.g., Supreme Court warrant or FedEx seizure). They isolate the victim on a Skype/WhatsApp call, forbidding them from speaking to anyone ("Digital Arrest").',
    indicators: ['Official-looking logos on WhatsApp DP', 'Use of legal jargon (FIR, IPC sections)', 'Demand for "verification deposits"'],
  },
  credential_request: {
    trends: 'Consistently high volume. Attackers are moving away from generic emails to highly targeted SMS (Smishing) posing as banks.',
    patterns: 'Messages claim an account will be blocked unless KYC is updated. A link directs to a pixel-perfect replica of a banking login page.',
    indicators: ['Links using URL shorteners', 'Slight misspellings in domains (e.g., hdfcbamk.com)', 'Requests for ATM PINs or CVV'],
  },
  urgency_coercion: {
    trends: 'Commonly paired with telecom impersonation. Used to bypass logical reasoning by creating artificial time pressure.',
    patterns: 'The victim is given a strict deadline (e.g., "Your number will be deactivated in 2 hours") to comply with demands.',
    indicators: ['Countdown timers on linked sites', 'Words like "IMMEDIATELY", "URGENT", "ACTION REQUIRED"', 'Threats of legal action or heavy fines'],
  },
  money_demand: {
    trends: 'Transitioning to cryptocurrency and mule accounts to complicate tracing. Often disguised as customs fees or investment taxes.',
    patterns: 'After a relationship is built or a service promised, an unexpected "fee" arises that must be paid via UPI or bank transfer.',
    indicators: ['Demanding payment to personal UPI handles instead of business accounts', 'Refusal to accept credit cards', 'Escalating fees'],
  },
  reward_bait: {
    trends: 'Exploiting festive seasons and major e-commerce sales. Massive spikes during Diwali or Big Billion Days.',
    patterns: 'Victim is told they won a lottery, car, or iPhone but must pay "processing fees" or "GST" to claim the prize.',
    indicators: ['Unexpected lottery wins', 'Scratch cards received via post or WhatsApp', 'Requests for upfront tax payments'],
  },
  isolation_tactics: {
    trends: 'A hallmark of "Digital Arrest" and advanced extortion schemes. Designed to prevent victims from verifying facts.',
    patterns: 'Scammers insist the matter is a "matter of national security" or "highly confidential" and explicitly forbid the victim from telling family.',
    indicators: ['Demand to stay on a continuous video call', 'Threats of arrest if anyone is informed', 'Isolating victim in a separate room'],
  },
  otp_readout_request: {
    trends: 'Still the #1 method for direct financial theft. Scammers now use automated IVR calls to extract OTPs seamlessly.',
    patterns: 'Scammer poses as customer support or a delivery executive, claiming an OTP is needed to "cancel" a transaction or "deliver" a package.',
    indicators: ['Any request for an OTP over the phone', 'Screen sharing apps (AnyDesk, TeamViewer)', 'Claims that OTP is for "verification"'],
  },
  card_collection_request: {
    trends: 'Targeting elderly individuals. Scammers physically collect cards claiming they are "upgrading" them.',
    patterns: 'Victim receives a call from "the bank" stating their debit/credit card is compromised. A "courier" is sent to collect the old card.',
    indicators: ['Requests to hand over physical cards', 'Requests to write PIN on the card envelope', 'Unsolicited bank representatives visiting home'],
  },
  relative_impersonation: {
    trends: 'Rising rapidly due to AI Voice Cloning (Deepfakes). Scammers sound exactly like the victim\'s child or grandchild.',
    patterns: 'A distressed call or message from a "relative" claiming they are in an accident, jail, or lost their phone and urgently need funds.',
    indicators: ['Calls from unknown numbers claiming "I lost my phone"', 'Refusal to answer personal verification questions', 'Urgent need for funds via UPI'],
  },
  telecom_impersonation: {
    trends: 'Often the entry point for Digital Arrest. Usually involves automated calls claiming numbers are being used for illegal activities.',
    patterns: '"Press 1 for TRAI/Customer Service." The victim is told their Aadhaar was used to buy SIM cards used in money laundering.',
    indicators: ['Automated calls (Robocalls) from "TRAI"', 'Threats of number disconnection within 2 hours', 'Transfers to "Cyber Police"'],
  },
  extortion_threat: {
    trends: 'Sextortion is rampant. Scammers use morphed videos or record video calls to blackmail victims.',
    patterns: 'Victim accepts a video call from an unknown number. The screen shows illicit content. The call is recorded, and money is demanded to prevent public release.',
    indicators: ['Video calls from unknown numbers', 'Immediate threats to share videos with Facebook/Instagram friends', 'Demands for continuous payments'],
  },
  malicious_link_bait: {
    trends: 'Delivered via SMS (Smishing) claiming to be electricity board, courier services, or income tax refunds.',
    patterns: 'The message contains a link to download an APK (malware) or visit a phishing site to update KYC or pay a small pending due.',
    indicators: ['Bit.ly or obscure domains', '.apk file downloads outside the Play Store', 'Messages like "Your electricity will be disconnected tonight"'],
  },
  malware_attachment_delivery: {
    trends: 'Targeting businesses and HR departments via fake job applications or invoices containing RATs (Remote Access Trojans).',
    patterns: 'An email with a sense of urgency contains a ZIP or PDF file. Opening it installs malware that steals session cookies and passwords.',
    indicators: ['Unexpected invoices or resumes', 'Files requiring passwords provided in the email', 'Double extensions (e.g., document.pdf.exe)'],
  },
  job_fraud: {
    trends: 'Rising alongside genuine work-from-home hiring, often distributed via WhatsApp/Telegram groups and fake job-portal listings.',
    patterns: 'Victim is told they have been "selected" for a role after little or no real interview, then asked to pay a refundable deposit, registration fee, or training/starter-kit charge to confirm the offer or reserve a training slot.',
    indicators: ['Payment requested before any offer letter or employment contract', 'Vague job description with unrealistic pay for minimal work', 'Pressure to pay quickly to "lock" a limited slot', '"Refundable" framed deposit that is never actually refunded'],
  },
};

