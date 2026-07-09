package com.rakshak.ai.intelligence.translations

/**
 * Odia (or) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object OdiaExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "ପୋଲିସ୍ କିମ୍ବା ସରକାରୀ ଅଧିକାରୀ ବୋଲି ଛଦ୍ମବେଶ ଧାରଣ କରେ",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, ପିନ୍, CVV କିମ୍ବା KYC ସୂଚନା ମାଗେ",
        "Creates artificial urgency / coercion" to
            "କୃତ୍ରିମ ତରବରତା କିମ୍ବା ଚାପ ସୃଷ୍ଟି କରେ",
        "Demands money transfer" to
            "ଟଙ୍କା ପଠାଇବାକୁ ଦାବି କରେ",
        "Offers unrealistic reward / lottery / returns" to
            "ଅବାସ୍ତବ ପୁରସ୍କାର, ଲଟେରୀ କିମ୍ବା ଲାଭର ଲୋଭ ଦେଖାଏ",
        "Discourages independent verification (bank/police/family)" to
            "ବ୍ୟାଙ୍କ/ପୋଲିସ୍/ପରିବାର ସହିତ ସ୍ୱାଧୀନ ଭାବରେ ଯାଞ୍ଚ କରିବାରୁ ନିରୁତ୍ସାହିତ କରେ",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "କଲ୍‌ରେ ଆପଣଙ୍କ OTP, ପିନ୍ କିମ୍ବା CVV କହିବାକୁ କୁହନ୍ତି",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "ଆପଣଙ୍କ କାର୍ଡ ନେବାକୁ ଘରକୁ ଆସିବେ ବୋଲି କୁହନ୍ତି, କିମ୍ବା ପିନ୍ ପ୍ରସ୍ତୁତ ରଖିବାକୁ କୁହନ୍ତି",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "ହଠାତ୍ ବିପଦରେ ପଡ଼ିଥିବା ପରିବାର ସଦସ୍ୟ କିମ୍ବା ବନ୍ଧୁ ବୋଲି ଦାବି କରି ତୁରନ୍ତ ଟଙ୍କା ମାଗନ୍ତି",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ଟେଲିକମ୍ ବିଭାଗ, TRAI କିମ୍ବା ଆପଣଙ୍କ ମୋବାଇଲ୍ କମ୍ପାନୀ ବୋଲି ଛଦ୍ମବେଶ ଧାରଣ କରି ସିମ୍/ନମ୍ବର ବନ୍ଦ କରିବାକୁ " +
                "ଧମକ ଦିଅନ୍ତି",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "ଟଙ୍କା ନ ଦେଲେ ବ୍ୟକ୍ତିଗତ ଫଟୋ କିମ୍ବା ଭିଡିଓ ଲିକ୍ କରିବାକୁ ଧମକ ଦିଅନ୍ତି",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "ପ୍ରକୃତ ବ୍ୟାଙ୍କ, ପୋଲିସ୍ ଅଧିକାରୀ କିମ୍ବା ସରକାରୀ ଅଧିକାରୀ ଆପଣଙ୍କୁ କଲ୍ କାଟି ସ୍ୱାଧୀନ ଭାବରେ ଯାଞ୍ଚ " +
                    "କରିବାରୁ — ବ୍ୟାଙ୍କର ସରକାରୀ ନମ୍ବର ମାଧ୍ୟମରେ, ପରିବାରର କୌଣସି ସଦସ୍ୟ ମାଧ୍ୟମରେ, କିମ୍ବା ନିଜେ ଯାଇ — " +
                    "କେବେ ବି ରୋକିବେ ନାହିଁ। ଏହି ପଦକ୍ଷେପ ଛାଡିବାକୁ, କଲ୍ କରୁଥିବା ବ୍ୟକ୍ତିଙ୍କ ପକ୍ଷରୁ ନିଜେ ପରିଚାଳନା " +
                    "କରିବାକୁ, କିମ୍ବା ପରିବାରକୁ \"ବିରକ୍ତ\" ନ କରିବାକୁ ଥିବା ଯେକୌଣସି ନିର୍ଦ୍ଦେଶ ନିଜେ ଏକ ଚେତାବନୀ ସଙ୍କେତ, " +
                    "କଲ୍ କରୁଥିବା ବ୍ୟକ୍ତି ଯେତେ ଶାନ୍ତ କିମ୍ବା ବିଶ୍ୱାସଯୋଗ୍ୟ ଲାଗନ୍ତୁ ନା କାହିଁକି।"
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "କୌଣସି ବ୍ୟାଙ୍କ, ପୋଲିସ୍ ଅଧିକାରୀ କିମ୍ବା ସରକାରୀ ଅଧିକାରୀ ଫୋନ୍ କଲ୍‌ରେ ଆପଣଙ୍କ OTP, ପିନ୍ କିମ୍ବା CVV " +
                    "କହିବାକୁ କେବେ ବି କହିବେ ନାହିଁ। ଏହା ମାଗୁଥିବା ଯେକେହି ସିଧାସଳଖ ଆପଣଙ୍କ ଆକାଉଣ୍ଟ ପ୍ରବେଶ କରିବାକୁ " +
                    "ଚେଷ୍ଟା କରୁଛନ୍ତି।"
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "ବ୍ୟାଙ୍କ ଏବଂ ସରକାରୀ ସଂସ୍ଥାଗୁଡ଼ିକ ଆପଣଙ୍କ ସକ୍ରିୟ ଡେବିଟ୍ କିମ୍ବା କ୍ରେଡିଟ୍ କାର୍ଡ ନେବାକୁ କାହାରିକୁ ଆପଣଙ୍କ " +
                    "ଘରକୁ ପଠାନ୍ତି ନାହିଁ। ଯଦି ଆପଣଙ୍କ କାର୍ଡ ବ୍ଲକ୍ କରିବାକୁ ପଡ଼େ, ତାହା ଦୂରରୁ ହିଁ କରାଯାଇପାରେ — " +
                    "କାହାରିକୁ ବି ଏହାକୁ ପ୍ରତ୍ୟକ୍ଷ ଭାବେ ନେବାର ଆବଶ୍ୟକତା ନାହିଁ।"
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "କୌଣସି ଠକେଇର ଲକ୍ଷଣ ମିଳିଲା ନାହିଁ; ଭାଷା ସାଧାରଣ ଏବଂ ବିଶ୍ୱାସଯୋଗ୍ୟ ସନ୍ଦେଶ ପରି ଲାଗୁଛି।",

        "This looks like a scam. Do not share any code or send money." to
            "ଏହା ଠକେଇ ପରି ଲାଗୁଛି। କୌଣସି କୋଡ୍ କୁହନ୍ତୁ ନାହିଁ କିମ୍ବା ଟଙ୍କା ପଠାନ୍ତୁ ନାହିଁ।",
        "This could be risky. Be careful and verify before doing anything." to
            "ଏହା ବିପଜ୍ଜନକ ହୋଇପାରେ। ସତର୍କ ରୁହନ୍ତୁ ଏବଂ କିଛି କରିବା ପୂର୍ବରୁ ଯାଞ୍ଚ କରନ୍ତୁ।",
        "This looks safe. Stay alert anyway." to
            "ଏହା ସୁରକ୍ଷିତ ଲାଗୁଛି। ତଥାପି ସତର୍କ ରୁହନ୍ତୁ।",

        "Multiple risk signals were detected." to
            "ଅନେକ ବିପଦ ସଙ୍କେତ ମିଳିଛି।",
        "Some risk signals were detected. Verify before proceeding." to
            "କିଛି ବିପଦ ସଙ୍କେତ ମିଳିଛି। ଆଗକୁ ବଢ଼ିବା ପୂର୍ବରୁ ଯାଞ୍ଚ କରନ୍ତୁ।",
        "No risk signals were detected." to
            "କୌଣସି ବିପଦ ସଙ୍କେତ ମିଳିଲା ନାହିଁ।",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "ସ୍ପଷ୍ଟ ପାଟର୍ନ ମେଳ ନ ଖାଇଲେ ମଧ୍ୟ ଭାଷା ମଡେଲ୍ ବିପଦର ସଙ୍କେତ ଦେଇଛି (ଠକେଇର ସମ୍ଭାବନା %s)।"
}
