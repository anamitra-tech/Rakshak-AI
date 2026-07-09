package com.rakshak.ai.intelligence.translations

/**
 * Punjabi (pa) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object PunjabiExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "ਪੁਲਿਸ ਜਾਂ ਸਰਕਾਰੀ ਅਧਿਕਾਰੀ ਹੋਣ ਦਾ ਦਿਖਾਵਾ ਕਰਦਾ ਹੈ",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, ਪਿੰਨ, CVV ਜਾਂ KYC ਜਾਣਕਾਰੀ ਮੰਗਦਾ ਹੈ",
        "Creates artificial urgency / coercion" to
            "ਨਕਲੀ ਜਲਦਬਾਜ਼ੀ ਜਾਂ ਦਬਾਅ ਬਣਾਉਂਦਾ ਹੈ",
        "Demands money transfer" to
            "ਪੈਸੇ ਭੇਜਣ ਦੀ ਮੰਗ ਕਰਦਾ ਹੈ",
        "Offers unrealistic reward / lottery / returns" to
            "ਅਸਲੀਅਤ ਤੋਂ ਪਰੇ ਇਨਾਮ, ਲਾਟਰੀ ਜਾਂ ਮੁਨਾਫ਼ੇ ਦਾ ਲਾਲਚ ਦਿੰਦਾ ਹੈ",
        "Discourages independent verification (bank/police/family)" to
            "ਬੈਂਕ/ਪੁਲਿਸ/ਪਰਿਵਾਰ ਨਾਲ ਸੁਤੰਤਰ ਤੌਰ 'ਤੇ ਤਸਦੀਕ ਕਰਨ ਤੋਂ ਰੋਕਦਾ ਹੈ",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "ਕਾਲ 'ਤੇ ਤੁਹਾਡਾ OTP, ਪਿੰਨ ਜਾਂ CVV ਦੱਸਣ ਲਈ ਕਹਿੰਦਾ ਹੈ",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "ਤੁਹਾਡਾ ਕਾਰਡ ਲੈਣ ਲਈ ਘਰ ਆਉਣ ਦੀ ਗੱਲ ਕਰਦਾ ਹੈ, ਜਾਂ ਪਿੰਨ ਤਿਆਰ ਰੱਖਣ ਲਈ ਕਹਿੰਦਾ ਹੈ",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "ਅਚਾਨਕ ਮੁਸੀਬਤ ਵਿੱਚ ਫਸੇ ਪਰਿਵਾਰਕ ਮੈਂਬਰ ਜਾਂ ਦੋਸਤ ਹੋਣ ਦਾ ਦਾਅਵਾ ਕਰਕੇ ਤੁਰੰਤ ਪੈਸੇ ਮੰਗਦਾ ਹੈ",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ਦੂਰਸੰਚਾਰ ਵਿਭਾਗ, TRAI ਜਾਂ ਤੁਹਾਡੀ ਮੋਬਾਈਲ ਕੰਪਨੀ ਹੋਣ ਦਾ ਦਿਖਾਵਾ ਕਰਕੇ ਸਿਮ/ਨੰਬਰ ਬੰਦ ਕਰਨ ਦੀ ਧਮਕੀ ਦਿੰਦਾ ਹੈ",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "ਪੈਸੇ ਨਾ ਦੇਣ 'ਤੇ ਨਿੱਜੀ ਫੋਟੋਆਂ ਜਾਂ ਵੀਡੀਓ ਲੀਕ ਕਰਨ ਦੀ ਧਮਕੀ ਦਿੰਦਾ ਹੈ",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "ਕੋਈ ਵੀ ਅਸਲੀ ਬੈਂਕ, ਪੁਲਿਸ ਅਧਿਕਾਰੀ ਜਾਂ ਸਰਕਾਰੀ ਅਧਿਕਾਰੀ ਤੁਹਾਨੂੰ ਫ਼ੋਨ ਕੱਟ ਕੇ ਸੁਤੰਤਰ ਤੌਰ 'ਤੇ ਤਸਦੀਕ " +
                    "ਕਰਨ ਤੋਂ — ਬੈਂਕ ਦੇ ਅਧਿਕਾਰਤ ਨੰਬਰ ਰਾਹੀਂ, ਪਰਿਵਾਰ ਦੇ ਕਿਸੇ ਮੈਂਬਰ ਰਾਹੀਂ, ਜਾਂ ਖੁਦ ਜਾ ਕੇ — ਕਦੇ " +
                    "ਨਹੀਂ ਰੋਕੇਗਾ। ਇਹ ਕਦਮ ਛੱਡਣ, ਕਾਲ ਕਰਨ ਵਾਲੇ ਦੀ ਤਰਫ਼ੋਂ ਖੁਦ ਸੰਭਾਲਣ, ਜਾਂ ਪਰਿਵਾਰ ਨੂੰ \"ਪਰੇਸ਼ਾਨ\" " +
                    "ਨਾ ਕਰਨ ਦੀ ਕੋਈ ਵੀ ਹਦਾਇਤ ਖੁਦ ਹੀ ਇੱਕ ਚੇਤਾਵਨੀ ਦਾ ਸੰਕੇਤ ਹੈ, ਭਾਵੇਂ ਕਾਲ ਕਰਨ ਵਾਲਾ ਕਿੰਨਾ ਵੀ ਸ਼ਾਂਤ " +
                    "ਜਾਂ ਭਰੋਸੇਯੋਗ ਕਿਉਂ ਨਾ ਲੱਗੇ।"
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "ਕੋਈ ਵੀ ਬੈਂਕ, ਪੁਲਿਸ ਅਧਿਕਾਰੀ ਜਾਂ ਸਰਕਾਰੀ ਅਧਿਕਾਰੀ ਤੁਹਾਨੂੰ ਫ਼ੋਨ 'ਤੇ ਕਦੇ ਵੀ ਤੁਹਾਡਾ OTP, ਪਿੰਨ ਜਾਂ CVV " +
                    "ਦੱਸਣ ਲਈ ਨਹੀਂ ਕਹੇਗਾ। ਜੋ ਕੋਈ ਵੀ ਇਹ ਮੰਗਦਾ ਹੈ, ਉਹ ਸਿੱਧਾ ਤੁਹਾਡੇ ਖਾਤੇ ਤੱਕ ਪਹੁੰਚ ਬਣਾਉਣ ਦੀ ਕੋਸ਼ਿਸ਼ " +
                    "ਕਰ ਰਿਹਾ ਹੈ।"
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "ਬੈਂਕ ਅਤੇ ਸਰਕਾਰੀ ਸੰਸਥਾਵਾਂ ਤੁਹਾਡਾ ਸਰਗਰਮ ਡੈਬਿਟ ਜਾਂ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਲੈਣ ਲਈ ਕਿਸੇ ਨੂੰ ਤੁਹਾਡੇ ਘਰ ਨਹੀਂ " +
                    "ਭੇਜਦੀਆਂ। ਜੇ ਤੁਹਾਡਾ ਕਾਰਡ ਬਲਾਕ ਕਰਨਾ ਹੋਵੇ, ਤਾਂ ਇਹ ਦੂਰੋਂ ਹੀ ਕੀਤਾ ਜਾ ਸਕਦਾ ਹੈ — ਕਿਸੇ ਨੂੰ ਵੀ " +
                    "ਇਸਨੂੰ ਖੁਦ ਲੈਣ ਦੀ ਲੋੜ ਨਹੀਂ।"
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "ਧੋਖਾਧੜੀ ਦਾ ਕੋਈ ਸੰਕੇਤ ਨਹੀਂ ਮਿਲਿਆ; ਭਾਸ਼ਾ ਆਮ ਅਤੇ ਭਰੋਸੇਯੋਗ ਸੁਨੇਹੇ ਵਰਗੀ ਲੱਗਦੀ ਹੈ।",

        "This looks like a scam. Do not share any code or send money." to
            "ਇਹ ਧੋਖਾਧੜੀ ਲੱਗਦੀ ਹੈ। ਕੋਈ ਵੀ ਕੋਡ ਨਾ ਦੱਸੋ ਅਤੇ ਪੈਸੇ ਨਾ ਭੇਜੋ।",
        "This could be risky. Be careful and verify before doing anything." to
            "ਇਹ ਖ਼ਤਰਨਾਕ ਹੋ ਸਕਦਾ ਹੈ। ਸਾਵਧਾਨ ਰਹੋ ਅਤੇ ਕੁਝ ਵੀ ਕਰਨ ਤੋਂ ਪਹਿਲਾਂ ਤਸਦੀਕ ਕਰੋ।",
        "This looks safe. Stay alert anyway." to
            "ਇਹ ਸੁਰੱਖਿਅਤ ਲੱਗਦਾ ਹੈ। ਫਿਰ ਵੀ ਸੁਚੇਤ ਰਹੋ।",

        "Multiple risk signals were detected." to
            "ਕਈ ਖ਼ਤਰੇ ਦੇ ਸੰਕੇਤ ਮਿਲੇ ਹਨ।",
        "Some risk signals were detected. Verify before proceeding." to
            "ਕੁਝ ਖ਼ਤਰੇ ਦੇ ਸੰਕੇਤ ਮਿਲੇ ਹਨ। ਅੱਗੇ ਵਧਣ ਤੋਂ ਪਹਿਲਾਂ ਤਸਦੀਕ ਕਰੋ।",
        "No risk signals were detected." to
            "ਖ਼ਤਰੇ ਦਾ ਕੋਈ ਸੰਕੇਤ ਨਹੀਂ ਮਿਲਿਆ।",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "ਭਾਸ਼ਾ ਮਾਡਲ ਨੇ ਖ਼ਤਰੇ ਦਾ ਸੰਕੇਤ ਦਿੱਤਾ ਹੈ (ਧੋਖਾਧੜੀ ਦੀ ਸੰਭਾਵਨਾ %s) ਭਾਵੇਂ ਕੋਈ ਸਪੱਸ਼ਟ ਪੈਟਰਨ ਮੇਲ ਨਹੀਂ ਖਾਂਦਾ।"
}
