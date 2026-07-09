package com.rakshak.ai.intelligence.translations

/**
 * Tamil (ta) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object TamilExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "காவல்துறை அல்லது அரசு அதிகாரி போல் நடிக்கிறது",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, பின், CVV அல்லது KYC தகவல்களை கேட்கிறது",
        "Creates artificial urgency / coercion" to
            "செயற்கையான அவசரம் அல்லது நெருக்கடியை உருவாக்குகிறது",
        "Demands money transfer" to
            "பணம் அனுப்பும்படி கோருகிறது",
        "Offers unrealistic reward / lottery / returns" to
            "நம்பமுடியாத பரிசு, லாட்டரி அல்லது லாபத்தை வாக்குறுதி அளிக்கிறது",
        "Discourages independent verification (bank/police/family)" to
            "வங்கி/காவல்துறை/குடும்பத்திடம் சுயமாக சரிபார்க்காமல் இருக்கத் தடுக்கிறது",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "அழைப்பில் உங்கள் OTP, பின் அல்லது CVV-ஐ சொல்லச் சொல்கிறது",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "உங்கள் கார்டை வீட்டிற்கு வந்து பெற்றுக்கொள்வதாகக் கூறுகிறது, அல்லது பின்னைத் தயாராக வைக்கச் சொல்கிறது",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "திடீரென்று சிக்கலில் சிக்கிய குடும்ப உறுப்பினர்/நண்பர் என்று கூறி அவசர பணம் கேட்கிறது",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "தொலைத்தொடர்பு துறை, TRAI அல்லது உங்கள் மொபைல் நிறுவனம் போல் நடித்து சிம்/எண்ணை துண்டிப்பதாக மிரட்டுகிறது",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "பணம் தராவிட்டால் தனிப்பட்ட புகைப்படங்கள்/வீடியோக்களை வெளியிடுவதாக மிரட்டுகிறது",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "உண்மையான வங்கி, காவல் அதிகாரி அல்லது அரசு அதிகாரி ஒருபோதும் உங்களை அழைப்பைத் துண்டித்து சுயமாக " +
                    "சரிபார்க்க — வங்கியின் அதிகாரப்பூர்வ எண் மூலம், குடும்ப உறுப்பினர் மூலம், அல்லது நேரில் சென்று " +
                    "— தடுக்க மாட்டார். இந்த படியைத் தவிர்க்கச் சொல்வது, அழைப்பாளர் சார்பாக நீங்களே கையாளச் " +
                    "சொல்வது, அல்லது குடும்பத்தை \"தொந்தரவு\" செய்ய வேண்டாம் என்று சொல்வது — இதுவே ஒரு எச்சரிக்கை " +
                    "அறிகுறி, அழைப்பாளர் எவ்வளவு அமைதியாகவோ நம்பகமாகவோ தோன்றினாலும் சரி."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "எந்த வங்கி, காவல் அதிகாரி அல்லது அரசு அதிகாரியும் தொலைபேசி அழைப்பில் உங்கள் OTP, பின் அல்லது " +
                    "CVV-ஐ சொல்லச் சொல்ல மாட்டார். இதைக் கேட்பவர் யாராக இருந்தாலும், அவர் நேரடியாக உங்கள் கணக்கை " +
                    "அணுக முயற்சிக்கிறார்."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "வங்கிகளும் அரசு நிறுவனங்களும் உங்கள் செயலில் உள்ள டெபிட் அல்லது கிரெடிட் கார்டைப் பெற யாரையும் " +
                    "உங்கள் வீட்டிற்கு அனுப்புவதில்லை. உங்கள் கார்டை முடக்க வேண்டுமெனில், அது தொலைநிலையிலேயே " +
                    "செய்யப்படலாம் — யாரும் அதை நேரில் வாங்க வேண்டியதில்லை."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "மோசடி அறிகுறிகள் எதுவும் கண்டறியப்படவில்லை; மொழி பொதுவான, நம்பகமான செய்தி போல் உள்ளது.",

        "This looks like a scam. Do not share any code or send money." to
            "இது மோசடி போல் தெரிகிறது. எந்த குறியீட்டையும் சொல்ல வேண்டாம், பணமும் அனுப்ப வேண்டாம்.",
        "This could be risky. Be careful and verify before doing anything." to
            "இது ஆபத்தானதாக இருக்கலாம். எச்சரிக்கையாக இருங்கள், எதுவும் செய்யும் முன் சரிபார்க்கவும்.",
        "This looks safe. Stay alert anyway." to
            "இது பாதுகாப்பானதாகத் தெரிகிறது. இருந்தாலும் எச்சரிக்கையாக இருங்கள்.",

        "Multiple risk signals were detected." to
            "பல ஆபத்து அறிகுறிகள் கண்டறியப்பட்டன.",
        "Some risk signals were detected. Verify before proceeding." to
            "சில ஆபத்து அறிகுறிகள் கண்டறியப்பட்டன. தொடர்வதற்கு முன் சரிபார்க்கவும்.",
        "No risk signals were detected." to
            "எந்த ஆபத்து அறிகுறியும் கண்டறியப்படவில்லை.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "தெளிவான முறை பொருந்தவில்லை என்றாலும் மொழி மாதிரி ஆபத்தைக் குறிக்கிறது (மோசடி வாய்ப்பு %s)."
}
