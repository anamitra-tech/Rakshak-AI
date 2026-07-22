package com.rakshak.ai.intelligence.translations

/**
 * Kannada (kn) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object KannadaExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "ಪೊಲೀಸ್ ಅಥವಾ ಸರ್ಕಾರಿ ಅಧಿಕಾರಿಯಂತೆ ನಟಿಸುತ್ತದೆ",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, ಪಿನ್, CVV ಅಥವಾ KYC ಮಾಹಿತಿಯನ್ನು ಕೇಳುತ್ತದೆ",
        "Creates artificial urgency / coercion" to
            "ಕೃತಕ ತುರ್ತು ಅಥವಾ ಒತ್ತಡವನ್ನು ಸೃಷ್ಟಿಸುತ್ತದೆ",
        "Demands money transfer" to
            "ಹಣ ಕಳುಹಿಸುವಂತೆ ಒತ್ತಾಯಿಸುತ್ತದೆ",
        "Offers unrealistic reward / lottery / returns" to
            "ಅವಾಸ್ತವಿಕ ಬಹುಮಾನ, ಲಾಟರಿ ಅಥವಾ ಲಾಭದ ಆಮಿಷ ತೋರಿಸುತ್ತದೆ",
        "Discourages independent verification (bank/police/family)" to
            "ಬ್ಯಾಂಕ್/ಪೊಲೀಸ್/ಕುಟುಂಬದೊಂದಿಗೆ ಸ್ವತಂತ್ರವಾಗಿ ಪರಿಶೀಲಿಸದಂತೆ ತಡೆಯುತ್ತದೆ",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "ಕರೆಯಲ್ಲಿ ನಿಮ್ಮ OTP, ಪಿನ್ ಅಥವಾ CVV ಹೇಳುವಂತೆ ಕೇಳುತ್ತದೆ",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "ನಿಮ್ಮ ಕಾರ್ಡ್ ಪಡೆಯಲು ಮನೆಗೆ ಬರುವುದಾಗಿ ಹೇಳುತ್ತದೆ, ಅಥವಾ ಪಿನ್ ಸಿದ್ಧವಾಗಿಡಲು ಕೇಳುತ್ತದೆ",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "ಇದ್ದಕ್ಕಿದ್ದಂತೆ ಸಂಕಷ್ಟದಲ್ಲಿರುವ ಕುಟುಂಬ ಸದಸ್ಯ ಅಥವಾ ಸ್ನೇಹಿತ ಎಂದು ಹೇಳಿಕೊಂಡು ತುರ್ತು ಹಣ ಕೇಳುತ್ತದೆ",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ಟೆಲಿಕಾಂ ಇಲಾಖೆ, TRAI ಅಥವಾ ನಿಮ್ಮ ಮೊಬೈಲ್ ಆಪರೇಟರ್‌ನಂತೆ ನಟಿಸಿ ಸಿಮ್/ನಂಬರ್ ಸಂಪರ್ಕ ಕಡಿತಗೊಳಿಸುವ ಬೆದರಿಕೆ ಹಾಕುತ್ತದೆ",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "ಹಣ ಪಾವತಿಸದಿದ್ದರೆ ಖಾಸಗಿ ಫೋಟೋ ಅಥವಾ ವೀಡಿಯೊ ಸೋರಿಕೆ ಮಾಡುವುದಾಗಿ ಬೆದರಿಕೆ ಹಾಕುತ್ತದೆ",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "ನಿಜವಾದ ಬ್ಯಾಂಕ್, ಪೊಲೀಸ್ ಅಧಿಕಾರಿ ಅಥವಾ ಸರ್ಕಾರಿ ಅಧಿಕಾರಿ ನಿಮ್ಮನ್ನು ಕರೆ ಕಡಿತಗೊಳಿಸಿ ಸ್ವತಂತ್ರವಾಗಿ " +
                    "ಪರಿಶೀಲಿಸುವುದರಿಂದ — ಬ್ಯಾಂಕಿನ ಅಧಿಕೃತ ಸಂಖ್ಯೆಯ ಮೂಲಕ, ಕುಟುಂಬ ಸದಸ್ಯರ ಮೂಲಕ, ಅಥವಾ ಖುದ್ದಾಗಿ ಹೋಗಿ " +
                    "— ಎಂದಿಗೂ ತಡೆಯುವುದಿಲ್ಲ. ಈ ಹಂತವನ್ನು ಬಿಟ್ಟುಬಿಡಲು, ಕರೆ ಮಾಡಿದವರ ಪರವಾಗಿ ನೀವೇ ನಿರ್ವಹಿಸಲು, ಅಥವಾ " +
                    "ಕುಟುಂಬವನ್ನು \"ತೊಂದರೆಗೊಳಿಸಬೇಡಿ\" ಎಂಬ ಯಾವುದೇ ಸೂಚನೆಯೇ ಒಂದು ಎಚ್ಚರಿಕೆಯ ಸಂಕೇತ, ಕರೆ ಮಾಡಿದವರು " +
                    "ಎಷ್ಟೇ ಶಾಂತ ಅಥವಾ ನಂಬಿಕಸ್ಥರಂತೆ ಕಂಡರೂ ಸಹ."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "ಯಾವುದೇ ಬ್ಯಾಂಕ್, ಪೊಲೀಸ್ ಅಧಿಕಾರಿ ಅಥವಾ ಸರ್ಕಾರಿ ಅಧಿಕಾರಿ ಫೋನ್ ಕರೆಯಲ್ಲಿ ನಿಮ್ಮ OTP, ಪಿನ್ ಅಥವಾ CVV " +
                    "ಹೇಳುವಂತೆ ಎಂದಿಗೂ ಕೇಳುವುದಿಲ್ಲ. ಇದನ್ನು ಕೇಳುವ ಯಾರಾದರೂ ನೇರವಾಗಿ ನಿಮ್ಮ ಖಾತೆಯನ್ನು ಪ್ರವೇಶಿಸಲು " +
                    "ಪ್ರಯತ್ನಿಸುತ್ತಿದ್ದಾರೆ."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "ಬ್ಯಾಂಕುಗಳು ಮತ್ತು ಸರ್ಕಾರಿ ಸಂಸ್ಥೆಗಳು ನಿಮ್ಮ ಸಕ್ರಿಯ ಡೆಬಿಟ್ ಅಥವಾ ಕ್ರೆಡಿಟ್ ಕಾರ್ಡ್ ಪಡೆಯಲು ಯಾರನ್ನೂ " +
                    "ನಿಮ್ಮ ಮನೆಗೆ ಕಳುಹಿಸುವುದಿಲ್ಲ. ನಿಮ್ಮ ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡಬೇಕಾದರೆ, ಅದನ್ನು ದೂರದಿಂದಲೇ ಮಾಡಬಹುದು — " +
                    "ಯಾರೂ ಅದನ್ನು ಖುದ್ದಾಗಿ ತೆಗೆದುಕೊಳ್ಳುವ ಅಗತ್ಯವಿಲ್ಲ."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "ಯಾವುದೇ ವಂಚನೆಯ ಲಕ್ಷಣಗಳು ಕಂಡುಬಂದಿಲ್ಲ; ಭಾಷೆ ಸಾಮಾನ್ಯ ಮತ್ತು ನಂಬಲರ್ಹ ಸಂದೇಶದಂತೆ ಕಾಣುತ್ತದೆ.",

        "This looks like a scam. Do not share any code or send money." to
            "ಇದು ವಂಚನೆಯಂತೆ ಕಾಣುತ್ತದೆ. ಯಾವುದೇ ಕೋಡ್ ಹೇಳಬೇಡಿ ಅಥವಾ ಹಣ ಕಳುಹಿಸಬೇಡಿ.",
        "This could be risky. Be careful and verify before doing anything." to
            "ಇದು ಅಪಾಯಕಾರಿಯಾಗಿರಬಹುದು. ಜಾಗರೂಕರಾಗಿರಿ ಮತ್ತು ಏನನ್ನಾದರೂ ಮಾಡುವ ಮೊದಲು ಪರಿಶೀಲಿಸಿ.",
        "This looks safe. Stay alert anyway." to
            "ಇದು ಸುರಕ್ಷಿತವಾಗಿ ಕಾಣುತ್ತದೆ. ಆದರೂ ಜಾಗರೂಕರಾಗಿರಿ.",

        "Multiple risk signals were detected." to
            "ಹಲವಾರು ಅಪಾಯದ ಸಂಕೇತಗಳು ಕಂಡುಬಂದಿವೆ.",
        "Some risk signals were detected. Verify before proceeding." to
            "ಕೆಲವು ಅಪಾಯದ ಸಂಕೇತಗಳು ಕಂಡುಬಂದಿವೆ. ಮುಂದುವರಿಯುವ ಮೊದಲು ಪರಿಶೀಲಿಸಿ.",
        "No risk signals were detected." to
            "ಯಾವುದೇ ಅಪಾಯದ ಸಂಕೇತಗಳು ಕಂಡುಬಂದಿಲ್ಲ.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "ಸ್ಪಷ್ಟ ಮಾದರಿ ಹೊಂದಾಣಿಕೆಯಾಗದಿದ್ದರೂ ಭಾಷಾ ಮಾದರಿಯು ಅಪಾಯವನ್ನು ಸೂಚಿಸುತ್ತದೆ (ವಂಚನೆಯ ಸಾಧ್ಯತೆ %s)."
}
