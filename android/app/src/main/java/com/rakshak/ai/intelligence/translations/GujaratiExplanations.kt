package com.rakshak.ai.intelligence.translations

/**
 * Gujarati (gu) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object GujaratiExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "પોલીસ અથવા સરકારી અધિકારી હોવાનો ડોળ કરે છે",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, પિન, CVV અથવા KYC માહિતી માંગે છે",
        "Creates artificial urgency / coercion" to
            "કૃત્રિમ ઉતાવળ અથવા દબાણ ઊભું કરે છે",
        "Demands money transfer" to
            "પૈસા મોકલવાની માંગ કરે છે",
        "Offers unrealistic reward / lottery / returns" to
            "અવાસ્તવિક ઇનામ, લોટરી અથવા નફાની લાલચ આપે છે",
        "Discourages independent verification (bank/police/family)" to
            "બેંક/પોલીસ/પરિવાર સાથે સ્વતંત્ર રીતે ચકાસણી કરવાથી નિરાશ કરે છે",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "કૉલ પર તમારો OTP, પિન અથવા CVV કહેવા માટે કહે છે",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "તમારું કાર્ડ લેવા ઘરે આવવાની વાત કરે છે, અથવા પિન તૈયાર રાખવા કહે છે",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "અચાનક મુશ્કેલીમાં ફસાયેલા પરિવારના સભ્ય કે મિત્ર હોવાનો દાવો કરીને તાત્કાલિક પૈસા માંગે છે",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ટેલિકોમ વિભાગ, TRAI અથવા તમારી મોબાઇલ કંપની હોવાનો ડોળ કરીને સિમ/નંબર બંધ કરવાની ધમકી આપે છે",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "પૈસા ન આપો તો ખાનગી ફોટા કે વીડિયો લીક કરવાની ધમકી આપે છે",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "સાચો બેંક અધિકારી, પોલીસ અધિકારી અથવા સરકારી અધિકારી તમને ફોન કાપીને સ્વતંત્ર રીતે ચકાસણી " +
                    "કરવાથી — બેંકના સત્તાવાર નંબર દ્વારા, પરિવારના કોઈ સભ્ય દ્વારા, અથવા રૂબરૂ જઈને — ક્યારેય " +
                    "રોકશે નહીં. આ પગલું છોડી દેવાની, કૉલ કરનારના વતી જાતે સંભાળી લેવાની, અથવા પરિવારને " +
                    "\"હેરાન\" ન કરવાની કોઈપણ સૂચના પોતે જ ચેતવણીની નિશાની છે, ભલે કૉલ કરનાર ગમે તેટલો શાંત કે " +
                    "વિશ્વાસપાત્ર લાગે."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "કોઈ પણ બેંક, પોલીસ અધિકારી અથવા સરકારી અધિકારી તમને ફોન પર તમારો OTP, પિન અથવા CVV કહેવા માટે " +
                    "ક્યારેય નહીં કહે. જે કોઈ આ માંગે છે, તે સીધો તમારા ખાતામાં પ્રવેશ મેળવવાનો પ્રયાસ કરી રહ્યો છે."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "બેંકો અને સરકારી સંસ્થાઓ તમારું સક્રિય ડેબિટ અથવા ક્રેડિટ કાર્ડ લેવા માટે કોઈને તમારા ઘરે મોકલતી " +
                    "નથી. જો તમારું કાર્ડ બ્લોક કરવાનું હોય, તો તે દૂરથી જ થઈ શકે છે — કોઈને તે રૂબરૂ લેવાની " +
                    "જરૂર નથી."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "કોઈ છેતરપિંડીના સંકેતો મળ્યા નથી; ભાષા સામાન્ય અને વિશ્વાસપાત્ર સંદેશ જેવી લાગે છે.",

        "This looks like a scam. Do not share any code or send money." to
            "આ છેતરપિંડી લાગે છે. કોઈ કોડ ન કહો કે પૈસા ન મોકલો.",
        "This could be risky. Be careful and verify before doing anything." to
            "આ જોખમી હોઈ શકે છે. સાવચેત રહો અને કંઈપણ કરતા પહેલા ચકાસો.",
        "This looks safe. Stay alert anyway." to
            "આ સુરક્ષિત લાગે છે. તેમ છતાં સતર્ક રહો.",

        "Multiple risk signals were detected." to
            "અનેક જોખમના સંકેતો મળ્યા.",
        "Some risk signals were detected. Verify before proceeding." to
            "કેટલાક જોખમના સંકેતો મળ્યા. આગળ વધતા પહેલા ચકાસો.",
        "No risk signals were detected." to
            "કોઈ જોખમનો સંકેત મળ્યો નથી.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "કોઈ ચોક્કસ પેટર્ન મેળ ખાતી ન હોવા છતાં ભાષા મોડેલ જોખમનો સંકેત આપે છે (છેતરપિંડીની શક્યતા %s)."
}
