package com.rakshak.ai.intelligence.translations

/**
 * Bengali (bn) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other 10 non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object BengaliExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "পুলিশ বা সরকারি কর্মকর্তা হওয়ার ভান করে",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, পিন, CVV বা KYC তথ্য চায়",
        "Creates artificial urgency / coercion" to
            "কৃত্রিম তাড়াহুড়ো বা চাপ সৃষ্টি করে",
        "Demands money transfer" to
            "টাকা পাঠানোর দাবি করে",
        "Offers unrealistic reward / lottery / returns" to
            "অবাস্তব পুরস্কার, লটারি বা মুনাফার প্রলোভন দেখায়",
        "Discourages independent verification (bank/police/family)" to
            "ব্যাংক, পুলিশ বা পরিবারের সাথে স্বাধীনভাবে যাচাই করতে নিরুৎসাহিত করে",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "কলে আপনার OTP, পিন বা CVV বলতে বলে",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "আপনার কার্ড সংগ্রহ করতে বাড়িতে আসার কথা বলে, বা পিন প্রস্তুত রাখতে বলে",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "হঠাৎ বিপদে পড়া পরিবারের সদস্য বা বন্ধু হওয়ার দাবি করে জরুরি টাকা চায়",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "টেলিকম বিভাগ, TRAI বা আপনার মোবাইল অপারেটর হওয়ার ভান করে সিম বা নম্বর বন্ধ করার হুমকি দেয়",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "টাকা না দিলে ব্যক্তিগত ছবি বা ভিডিও ফাঁস করার হুমকি দেয়",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "প্রকৃত ব্যাংক, পুলিশ অফিসার বা সরকারি কর্মকর্তা কখনও আপনাকে ফোন কেটে স্বাধীনভাবে যাচাই করতে — " +
                    "ব্যাংকের অফিসিয়াল নম্বরে, পরিবারের কারো মাধ্যমে, বা সরাসরি গিয়ে — বাধা দেবে না। এই ধাপ " +
                    "এড়িয়ে যাওয়া, কলকারীর পক্ষে নিজে ব্যবস্থা করা, বা পরিবারকে \"বিরক্ত\" না করার যেকোনো নির্দেশই " +
                    "নিজেই একটি সতর্কতা চিহ্ন, কলকারী যতই শান্ত বা বিশ্বাসযোগ্য শোনাক না কেন।"
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "কোনো ব্যাংক, পুলিশ অফিসার বা সরকারি কর্মকর্তা কখনও ফোনে আপনার OTP, পিন বা CVV বলতে বলবে না। " +
                    "যে কেউ এটি চায়, সে সরাসরি আপনার অ্যাকাউন্টে প্রবেশ করার চেষ্টা করছে।"
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "ব্যাংক এবং সরকারি সংস্থাগুলি আপনার সক্রিয় ডেবিট বা ক্রেডিট কার্ড সংগ্রহ করতে কাউকে আপনার বাড়িতে " +
                    "পাঠায় না। আপনার কার্ড ব্লক করতে হলে তা দূর থেকেই করা যায় — কাউকে শারীরিকভাবে এটি নেওয়ার " +
                    "প্রয়োজন নেই।"
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "কোনো প্রতারণার লক্ষণ পাওয়া যায়নি; ভাষাটি স্বাভাবিক ও বিশ্বাসযোগ্য বার্তার মতো মনে হচ্ছে।",

        "This looks like a scam. Do not share any code or send money." to
            "এটি প্রতারণা বলে মনে হচ্ছে। কোনো কোড বলবেন না বা টাকা পাঠাবেন না।",
        "This could be risky. Be careful and verify before doing anything." to
            "এটি ঝুঁকিপূর্ণ হতে পারে। সতর্ক থাকুন এবং কিছু করার আগে যাচাই করুন।",
        "This looks safe. Stay alert anyway." to
            "এটি নিরাপদ বলে মনে হচ্ছে। তবুও সতর্ক থাকুন।",

        "Multiple risk signals were detected." to
            "একাধিক ঝুঁকির সংকেত পাওয়া গেছে।",
        "Some risk signals were detected. Verify before proceeding." to
            "কিছু ঝুঁকির সংকেত পাওয়া গেছে। এগোনোর আগে যাচাই করুন।",
        "No risk signals were detected." to
            "কোনো ঝুঁকির সংকেত পাওয়া যায়নি।",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "ভাষা মডেল ঝুঁকির সংকেত দিয়েছে (প্রতারণার সম্ভাবনা %s) যদিও কোনো নির্দিষ্ট প্যাটার্ন মেলেনি।"
}
