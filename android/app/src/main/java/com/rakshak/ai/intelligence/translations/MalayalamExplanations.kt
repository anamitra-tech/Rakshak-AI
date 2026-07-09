package com.rakshak.ai.intelligence.translations

/**
 * Malayalam (ml) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object MalayalamExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "പോലീസ് അല്ലെങ്കിൽ സർക്കാർ ഉദ്യോഗസ്ഥനാണെന്ന് നടിക്കുന്നു",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, പിൻ, CVV അല്ലെങ്കിൽ KYC വിവരങ്ങൾ ചോദിക്കുന്നു",
        "Creates artificial urgency / coercion" to
            "കൃത്രിമ തിടുക്കമോ സമ്മർദ്ദമോ സൃഷ്ടിക്കുന്നു",
        "Demands money transfer" to
            "പണം അയക്കാൻ ആവശ്യപ്പെടുന്നു",
        "Offers unrealistic reward / lottery / returns" to
            "യാഥാർത്ഥ്യമല്ലാത്ത സമ്മാനം, ലോട്ടറി അല്ലെങ്കിൽ ലാഭം വാഗ്ദാനം ചെയ്യുന്നു",
        "Discourages independent verification (bank/police/family)" to
            "ബാങ്ക്/പോലീസ്/കുടുംബവുമായി സ്വതന്ത്രമായി പരിശോധിക്കുന്നതിൽ നിന്ന് പിന്തിരിപ്പിക്കുന്നു",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "കോളിൽ നിങ്ങളുടെ OTP, പിൻ അല്ലെങ്കിൽ CVV പറയാൻ ആവശ്യപ്പെടുന്നു",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "നിങ്ങളുടെ കാർഡ് വാങ്ങാൻ വീട്ടിലേക്ക് വരാമെന്ന് പറയുന്നു, അല്ലെങ്കിൽ പിൻ തയ്യാറാക്കി വയ്ക്കാൻ ആവശ്യപ്പെടുന്നു",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "പെട്ടെന്ന് പ്രശ്നത്തിലായ കുടുംബാംഗമോ സുഹൃത്തോ ആണെന്ന് അവകാശപ്പെട്ട് അടിയന്തിര പണം ചോദിക്കുന്നു",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ടെലികോം വകുപ്പ്, TRAI അല്ലെങ്കിൽ നിങ്ങളുടെ മൊബൈൽ കമ്പനി ആണെന്ന് നടിച്ച് സിം/നമ്പർ വിച്ഛേദിക്കുമെന്ന് " +
                "ഭീഷണിപ്പെടുത്തുന്നു",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "പണം നൽകിയില്ലെങ്കിൽ സ്വകാര്യ ഫോട്ടോകളോ വീഡിയോകളോ ചോർത്തുമെന്ന് ഭീഷണിപ്പെടുത്തുന്നു",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "യഥാർത്ഥ ബാങ്ക്, പോലീസ് ഉദ്യോഗസ്ഥൻ അല്ലെങ്കിൽ സർക്കാർ ഉദ്യോഗസ്ഥൻ നിങ്ങളെ കോൾ വിച്ഛേദിച്ച് " +
                    "സ്വതന്ത്രമായി പരിശോധിക്കുന്നതിൽ നിന്ന് — ബാങ്കിന്റെ ഔദ്യോഗിക നമ്പർ വഴി, കുടുംബാംഗം വഴി, " +
                    "അല്ലെങ്കിൽ നേരിട്ട് ചെന്ന് — ഒരിക്കലും തടയില്ല. ഈ ഘട്ടം ഒഴിവാക്കാനോ, വിളിക്കുന്നയാൾക്ക് വേണ്ടി " +
                    "നിങ്ങൾ തന്നെ കൈകാര്യം ചെയ്യാനോ, കുടുംബത്തെ \"ബുദ്ധിമുട്ടിക്കരുത്\" എന്നോ ഉള്ള ഏത് നിർദ്ദേശവും " +
                    "തന്നെ ഒരു മുന്നറിയിപ്പ് അടയാളമാണ്, വിളിക്കുന്നയാൾ എത്ര ശാന്തനോ വിശ്വസനീയനോ ആയി തോന്നിയാലും."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "ഒരു ബാങ്കും, പോലീസ് ഉദ്യോഗസ്ഥനും, സർക്കാർ ഉദ്യോഗസ്ഥനും ഫോൺ കോളിൽ നിങ്ങളുടെ OTP, പിൻ അല്ലെങ്കിൽ " +
                    "CVV പറയാൻ ഒരിക്കലും ആവശ്യപ്പെടില്ല. ഇത് ചോദിക്കുന്ന ആരും നേരിട്ട് നിങ്ങളുടെ അക്കൗണ്ട് " +
                    "ആക്സസ് ചെയ്യാൻ ശ്രമിക്കുകയാണ്."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "ബാങ്കുകളും സർക്കാർ സ്ഥാപനങ്ങളും നിങ്ങളുടെ സജീവ ഡെബിറ്റ് അല്ലെങ്കിൽ ക്രെഡിറ്റ് കാർഡ് വാങ്ങാൻ " +
                    "ആരെയും നിങ്ങളുടെ വീട്ടിലേക്ക് അയക്കില്ല. നിങ്ങളുടെ കാർഡ് ബ്ലോക്ക് ചെയ്യണമെങ്കിൽ, അത് " +
                    "വിദൂരമായി തന്നെ ചെയ്യാം — ആരും അത് നേരിട്ട് വാങ്ങേണ്ട ആവശ്യമില്ല."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "വഞ്ചനയുടെ ലക്ഷണങ്ങളൊന്നും കണ്ടെത്തിയില്ല; ഭാഷ സാധാരണവും വിശ്വസനീയവുമായ സന്ദേശം പോലെയാണ്.",

        "This looks like a scam. Do not share any code or send money." to
            "ഇത് വഞ്ചനയാണെന്ന് തോന്നുന്നു. ഒരു കോഡും പറയരുത്, പണം അയക്കരുത്.",
        "This could be risky. Be careful and verify before doing anything." to
            "ഇത് അപകടകരമായേക്കാം. ജാഗ്രത പാലിക്കുക, എന്തെങ്കിലും ചെയ്യുന്നതിന് മുമ്പ് സ്ഥിരീകരിക്കുക.",
        "This looks safe. Stay alert anyway." to
            "ഇത് സുരക്ഷിതമായി തോന്നുന്നു. എന്നിരുന്നാലും ജാഗ്രത പാലിക്കുക.",

        "Multiple risk signals were detected." to
            "ഒന്നിലധികം അപകട സൂചനകൾ കണ്ടെത്തി.",
        "Some risk signals were detected. Verify before proceeding." to
            "ചില അപകട സൂചനകൾ കണ്ടെത്തി. തുടരുന്നതിന് മുമ്പ് സ്ഥിരീകരിക്കുക.",
        "No risk signals were detected." to
            "അപകട സൂചനകളൊന്നും കണ്ടെത്തിയില്ല.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "വ്യക്തമായ പാറ്റേൺ പൊരുത്തപ്പെട്ടില്ലെങ്കിലും ഭാഷാ മോഡൽ അപകടസാധ്യത സൂചിപ്പിക്കുന്നു (വഞ്ചനാ സാധ്യത %s)."
}
