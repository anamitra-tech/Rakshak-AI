package com.rakshak.ai.intelligence.translations

/**
 * Marathi (mr) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object MarathiExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "पोलीस किंवा सरकारी अधिकारी असल्याचे भासवतो",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, पिन, CVV किंवा KYC माहिती मागतो",
        "Creates artificial urgency / coercion" to
            "कृत्रिम घाई किंवा दबाव निर्माण करतो",
        "Demands money transfer" to
            "पैसे पाठवण्याची मागणी करतो",
        "Offers unrealistic reward / lottery / returns" to
            "अवास्तव बक्षीस, लॉटरी किंवा नफ्याचे आमिष दाखवतो",
        "Discourages independent verification (bank/police/family)" to
            "बँक, पोलीस किंवा कुटुंबाकडून स्वतंत्रपणे पडताळणी करण्यापासून परावृत्त करतो",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "कॉलवर तुमचा OTP, पिन किंवा CVV सांगण्यास सांगतो",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "तुमचे कार्ड घेण्यासाठी घरी येण्याबद्दल बोलतो, किंवा पिन तयार ठेवण्यास सांगतो",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "अचानक संकटात सापडलेला कुटुंबातील सदस्य किंवा मित्र असल्याचा दावा करून तातडीने पैसे मागतो",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "दूरसंचार विभाग, TRAI किंवा तुमच्या मोबाइल कंपनीचे नाव घेऊन सिम किंवा नंबर बंद करण्याची धमकी देतो",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "पैसे न दिल्यास खाजगी फोटो किंवा व्हिडिओ लीक करण्याची धमकी देतो",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "खरा बँक अधिकारी, पोलीस अधिकारी किंवा सरकारी अधिकारी तुम्हाला फोन ठेवून स्वतंत्रपणे पडताळणी करण्यापासून " +
                    "— बँकेच्या अधिकृत नंबरवर, कुटुंबातील एखाद्या सदस्यामार्फत, किंवा प्रत्यक्ष जाऊन — कधीही रोखणार " +
                    "नाही. हे पाऊल टाळण्याची, कॉल करणाऱ्याच्या वतीने स्वतः व्यवहार करण्याची, किंवा कुटुंबाला " +
                    "\"त्रास\" न देण्याची कोणतीही सूचना हीच स्वतः एक धोक्याची खूण आहे, कॉल करणारा कितीही शांत किंवा " +
                    "विश्वासार्ह वाटला तरीही."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "कोणताही बँक, पोलीस अधिकारी किंवा सरकारी अधिकारी तुम्हाला फोनवर तुमचा OTP, पिन किंवा CVV सांगण्यास " +
                    "कधीही सांगणार नाही. जो कोणी हे मागतो, तो थेट तुमच्या खात्यात प्रवेश मिळवण्याचा प्रयत्न करत आहे."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "बँका आणि सरकारी संस्था तुमचे सक्रिय डेबिट किंवा क्रेडिट कार्ड घेण्यासाठी कोणालाही तुमच्या घरी पाठवत " +
                    "नाहीत. तुमचे कार्ड ब्लॉक करायचे असल्यास ते दूरस्थपणे केले जाऊ शकते — कोणालाही ते प्रत्यक्ष " +
                    "घेण्याची गरज नाही."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "कोणतेही फसवणुकीचे संकेत आढळले नाहीत; भाषा सर्वसामान्य आणि विश्वासार्ह संदेशासारखी वाटते.",

        "This looks like a scam. Do not share any code or send money." to
            "हे फसवणुकीसारखे वाटते. कोणताही कोड सांगू नका किंवा पैसे पाठवू नका.",
        "This could be risky. Be careful and verify before doing anything." to
            "हे धोकादायक असू शकते. सावध रहा आणि काहीही करण्यापूर्वी पडताळणी करा.",
        "This looks safe. Stay alert anyway." to
            "हे सुरक्षित वाटते. तरीही सतर्क रहा.",

        "Multiple risk signals were detected." to
            "अनेक धोक्याचे संकेत आढळले.",
        "Some risk signals were detected. Verify before proceeding." to
            "काही धोक्याचे संकेत आढळले. पुढे जाण्यापूर्वी पडताळणी करा.",
        "No risk signals were detected." to
            "कोणतेही धोक्याचे संकेत आढळले नाहीत.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "भाषा मॉडेलने धोक्याचा इशारा दिला आहे (फसवणुकीची शक्यता %s) तरीही कोणताही स्पष्ट नमुना जुळला नाही."
}
