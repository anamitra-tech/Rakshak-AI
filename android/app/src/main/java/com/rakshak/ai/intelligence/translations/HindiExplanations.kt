package com.rakshak.ai.intelligence.translations

/**
 * Hindi (hi) translations of the fixed, finite explanation strings that
 * ml/detector.py (build_signals(), NEAR_DETERMINISTIC_RULES, the two
 * rule-less build_reason() fallbacks) and Android's own
 * DecisionAgent.headline()/defaultReason() can emit — see
 * ExplanationTranslations's doc comment for how this table is used.
 *
 * Verified against a real device: speaking these through the hi-IN voice
 * produced normal AudioTrack amplitude (~13000+), versus the ~170
 * near-silent amplitude previously measured feeding raw English text
 * through that same voice — see AutoEscalationCountdownActivity's diagnosis.
 */
object HindiExplanations {
    val MAP: Map<String, String> = mapOf(
        // ml/detector.py::build_signals() — one per HIGH_RISK_PATTERNS category
        "Impersonates law-enforcement / govt authority" to
            "पुलिस या सरकारी अधिकारी होने का दिखावा करता है",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, पिन, CVV या KYC जानकारी मांगता है",
        "Creates artificial urgency / coercion" to
            "जल्दबाज़ी या दबाव बनाता है",
        "Demands money transfer" to
            "पैसे भेजने की मांग करता है",
        "Offers unrealistic reward / lottery / returns" to
            "अवास्तविक इनाम, लॉटरी या मुनाफे का लालच देता है",
        "Discourages independent verification (bank/police/family)" to
            "बैंक, पुलिस या परिवार से स्वतंत्र रूप से जांच करने से रोकता है",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "कॉल पर आपका OTP, पिन या CVV बताने के लिए कहता है",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "आपका कार्ड लेने घर आने की बात करता है, या पिन तैयार रखने के लिए कहता है",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "अचानक मुसीबत में फंसे परिवार के सदस्य या दोस्त होने का दावा करके तुरंत पैसे मांगता है",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "दूरसंचार विभाग, TRAI या आपकी मोबाइल कंपनी होने का दिखावा करके सिम या नंबर बंद करने की धमकी देता है",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "पैसे न देने पर निजी फोटो या वीडियो लीक करने की धमकी देता है",

        // ml/detector.py NEAR_DETERMINISTIC_RULES explanation paragraphs
        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "कोई भी असली बैंक, पुलिस अधिकारी या सरकारी अधिकारी आपको फोन काटकर स्वतंत्र रूप से जांच करने से — " +
                    "बैंक के आधिकारिक नंबर, परिवार के किसी सदस्य, या खुद जाकर — कभी नहीं रोकेगा। यह कदम छोड़ने, " +
                    "कॉल करने वाले की तरफ से खुद काम निपटाने, या परिवार को परेशान न करने की कोई भी सलाह अपने आप में " +
                    "एक चेतावनी है, चाहे कॉल करने वाला कितना भी शांत या भरोसेमंद क्यों न लगे।"
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "कोई भी बैंक, पुलिस अधिकारी या सरकारी अधिकारी आपसे फोन पर कभी भी OTP, पिन या CVV बताने के लिए नहीं " +
                    "कहेगा। जो कोई भी यह मांगता है, वह सीधे आपके खाते तक पहुंच बनाने की कोशिश कर रहा है।"
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "बैंक और सरकारी संस्थाएं आपका सक्रिय डेबिट या क्रेडिट कार्ड लेने के लिए किसी को आपके घर नहीं भेजतीं। " +
                    "अगर आपका कार्ड ब्लॉक करना है, तो यह दूर से ही किया जा सकता है — किसी को भी इसे आपसे शारीरिक " +
                    "रूप से लेने की ज़रूरत नहीं है।"
                ),

        // ml/detector.py::build_reason() rule-less SAFE fallback
        "No fraud patterns detected; language consistent with legitimate messaging." to
            "कोई धोखाधड़ी का संकेत नहीं मिला; भाषा सामान्य और भरोसेमंद संदेश जैसी लगती है।",

        // DecisionAgent.kt headline() — Android-side, not detector.py, but
        // part of the same spoken explanationText() (see decision.headline).
        "This looks like a scam. Do not share any code or send money." to
            "यह धोखाधड़ी लग रही है। कोई भी कोड न बताएं और पैसे न भेजें।",
        "This could be risky. Be careful and verify before doing anything." to
            "यह जोखिम भरा हो सकता है। सावधान रहें और कुछ भी करने से पहले जांच लें।",
        "This looks safe. Stay alert anyway." to
            "यह सुरक्षित लग रहा है। फिर भी सतर्क रहें।",

        // DecisionAgent.kt defaultReason()
        "Multiple risk signals were detected." to
            "कई खतरे के संकेत मिले हैं।",
        "Some risk signals were detected. Verify before proceeding." to
            "कुछ खतरे के संकेत मिले हैं। आगे बढ़ने से पहले जांच लें।",
        "No risk signals were detected." to
            "कोई खतरे का संकेत नहीं मिला।",
    )

    /** ml/detector.py::build_reason()'s only variable-content template
     *  (the fraud-likelihood percentage) — handled as a template rather
     *  than an exact-match entry above; see ExplanationTranslations. */
    const val ML_LIKELIHOOD_TEMPLATE: String =
        "भाषा मॉडल ने जोखिम की चेतावनी दी है (धोखाधड़ी की संभावना %s) हालांकि कोई स्पष्ट पैटर्न नहीं मिला।"
}
