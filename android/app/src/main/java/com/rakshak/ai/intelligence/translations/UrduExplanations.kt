package com.rakshak.ai.intelligence.translations

/**
 * Urdu (ur) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object UrduExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "پولیس یا سرکاری اہلکار ہونے کا ڈرامہ کرتا ہے",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP، پن، CVV یا KYC معلومات مانگتا ہے",
        "Creates artificial urgency / coercion" to
            "مصنوعی جلدی یا دباؤ پیدا کرتا ہے",
        "Demands money transfer" to
            "پیسے بھیجنے کا مطالبہ کرتا ہے",
        "Offers unrealistic reward / lottery / returns" to
            "غیر حقیقی انعام، لاٹری یا منافع کا لالچ دیتا ہے",
        "Discourages independent verification (bank/police/family)" to
            "بینک، پولیس یا خاندان سے آزادانہ تصدیق کرنے سے روکتا ہے",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "کال پر آپ کا OTP، پن یا CVV بتانے کو کہتا ہے",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "آپ کا کارڈ لینے گھر آنے کی بات کرتا ہے، یا پن تیار رکھنے کو کہتا ہے",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "اچانک مصیبت میں پھنسے خاندان کے فرد یا دوست ہونے کا دعویٰ کر کے فوری پیسے مانگتا ہے",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "ٹیلی کام ڈیپارٹمنٹ، TRAI یا آپ کی موبائل کمپنی ہونے کا ڈرامہ کر کے سم یا نمبر بند کرنے کی دھمکی دیتا ہے",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "پیسے نہ دینے پر نجی تصاویر یا ویڈیو لیک کرنے کی دھمکی دیتا ہے",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "کوئی حقیقی بینک، پولیس افسر یا سرکاری اہلکار آپ کو کال کاٹ کر آزادانہ طور پر تصدیق کرنے سے — " +
                    "بینک کے سرکاری نمبر پر، خاندان کے کسی فرد کے ذریعے، یا خود جا کر — کبھی نہیں روکے گا۔ یہ " +
                    "قدم چھوڑنے، کال کرنے والے کی طرف سے خود معاملہ سنبھالنے، یا خاندان کو \"پریشان\" نہ کرنے کی " +
                    "کوئی بھی ہدایت خود ایک انتباہ کی علامت ہے، چاہے کال کرنے والا کتنا ہی پرسکون یا قابلِ بھروسہ " +
                    "کیوں نہ لگے۔"
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "کوئی بھی بینک، پولیس افسر یا سرکاری اہلکار آپ سے فون پر کبھی بھی آپ کا OTP، پن یا CVV بتانے " +
                    "کو نہیں کہے گا۔ جو کوئی بھی یہ مانگتا ہے، وہ براہ راست آپ کے اکاؤنٹ تک رسائی حاصل کرنے کی " +
                    "کوشش کر رہا ہے۔"
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "بینک اور سرکاری ادارے آپ کا فعال ڈیبٹ یا کریڈٹ کارڈ لینے کے لیے کسی کو آپ کے گھر نہیں بھیجتے۔ " +
                    "اگر آپ کا کارڈ بلاک کرنا ہو، تو یہ دور سے ہی کیا جا سکتا ہے — کسی کو بھی اسے جسمانی طور پر " +
                    "لینے کی ضرورت نہیں۔"
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "دھوکہ دہی کی کوئی علامت نہیں ملی؛ زبان عام اور قابلِ اعتماد پیغام جیسی لگتی ہے۔",

        "This looks like a scam. Do not share any code or send money." to
            "یہ دھوکہ دہی لگتی ہے۔ کوئی کوڈ نہ بتائیں اور پیسے نہ بھیجیں۔",
        "This could be risky. Be careful and verify before doing anything." to
            "یہ خطرناک ہو سکتا ہے۔ محتاط رہیں اور کچھ بھی کرنے سے پہلے تصدیق کریں۔",
        "This looks safe. Stay alert anyway." to
            "یہ محفوظ لگتا ہے۔ پھر بھی چوکس رہیں۔",

        "Multiple risk signals were detected." to
            "کئی خطرے کی علامات ملی ہیں۔",
        "Some risk signals were detected. Verify before proceeding." to
            "کچھ خطرے کی علامات ملی ہیں۔ آگے بڑھنے سے پہلے تصدیق کریں۔",
        "No risk signals were detected." to
            "خطرے کی کوئی علامت نہیں ملی۔",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "زبان کے ماڈل نے خطرے کی نشاندہی کی ہے (دھوکہ دہی کا امکان %s) حالانکہ کوئی واضح پیٹرن مماثل نہیں ہوا۔"
}
