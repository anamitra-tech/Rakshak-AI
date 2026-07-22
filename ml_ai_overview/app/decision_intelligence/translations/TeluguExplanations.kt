package com.rakshak.ai.intelligence.translations

/**
 * Telugu (te) translations of the fixed explanation strings — see
 * ExplanationTranslations's doc comment. Drafted offline in the same
 * LLM-batch pass as the other non-Hindi languages; NOT yet verified
 * against a real device/voice pack (only Hindi has been device-verified
 * so far — see HindiExplanations).
 */
object TeluguExplanations {
    val MAP: Map<String, String> = mapOf(
        "Impersonates law-enforcement / govt authority" to
            "పోలీసు లేదా ప్రభుత్వ అధికారిగా నటిస్తుంది",
        "Requests OTP/PIN/CVV/KYC credentials" to
            "OTP, పిన్, CVV లేదా KYC వివరాలు అడుగుతుంది",
        "Creates artificial urgency / coercion" to
            "కృత్రిమ తొందర లేదా ఒత్తిడిని సృష్టిస్తుంది",
        "Demands money transfer" to
            "డబ్బు పంపమని డిమాండ్ చేస్తుంది",
        "Offers unrealistic reward / lottery / returns" to
            "అవాస్తవ బహుమతి, లాటరీ లేదా లాభాలను ఆశ చూపిస్తుంది",
        "Discourages independent verification (bank/police/family)" to
            "బ్యాంక్/పోలీస్/కుటుంబంతో స్వతంత్రంగా ధృవీకరించుకోకుండా నిరుత్సాహపరుస్తుంది",
        "Asks you to read out your OTP/PIN/CVV over the call" to
            "కాల్‌లో మీ OTP, పిన్ లేదా CVV చెప్పమని అడుగుతుంది",
        "Arranges in-person collection of your card, or asks you to keep the PIN ready" to
            "మీ కార్డును తీసుకెళ్లడానికి ఇంటికి వస్తామని చెబుతుంది, లేదా పిన్ సిద్ధంగా ఉంచమని అడుగుతుంది",
        "Claims to be a family member/friend in sudden distress asking for urgent money" to
            "అకస్మాత్తుగా కష్టాల్లో ఉన్న కుటుంబ సభ్యుడు లేదా స్నేహితుడిగా చెప్పుకుని తక్షణమే డబ్బు అడుగుతుంది",
        "Impersonates DoT/TRAI/your telecom operator, threatening SIM/number disconnection" to
            "టెలికాం శాఖ, TRAI లేదా మీ మొబైల్ ఆపరేటర్‌గా నటిస్తూ సిమ్/నంబర్ డిస్‌కనెక్ట్ చేస్తామని బెదిరిస్తుంది",
        "Threatens to leak private content unless paid (blackmail/sextortion framing)" to
            "డబ్బు చెల్లించకపోతే వ్యక్తిగత ఫోటోలు లేదా వీడియోలు లీక్ చేస్తామని బెదిరిస్తుంది",

        (
            "A genuine bank, police officer, or government official will never discourage you from " +
                "hanging up and verifying independently — through the bank's official number, a family " +
                "member, or in person. Any instruction to skip that step, handle it yourself on the " +
                "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
                "of how calm or convincing the caller sounds."
            ) to
            (
                "నిజమైన బ్యాంక్, పోలీసు అధికారి లేదా ప్రభుత్వ అధికారి మిమ్మల్ని ఫోన్ పెట్టేసి స్వతంత్రంగా " +
                    "ధృవీకరించుకోకుండా — బ్యాంక్ అధికారిక నంబర్ ద్వారా, కుటుంబ సభ్యుడి ద్వారా, లేదా నేరుగా వెళ్లి — " +
                    "ఎప్పుడూ నిరోధించరు. ఈ దశను దాటవేయమని, కాల్ చేసిన వ్యక్తి తరపున మీరే స్వయంగా చూసుకోమని, లేదా " +
                    "కుటుంబాన్ని \"ఇబ్బంది పెట్టవద్దని\" చెప్పే ఏ సూచన అయినా అదే ఒక హెచ్చరిక సంకేతం, కాల్ చేసిన వ్యక్తి " +
                    "ఎంత ప్రశాంతంగా లేదా నమ్మదగినట్లు అనిపించినా సరే."
                ),
        (
            "No bank, police officer, or government official will ever ask you to read out your OTP, " +
                "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
                "directly."
            ) to
            (
                "ఏ బ్యాంక్, పోలీసు అధికారి లేదా ప్రభుత్వ అధికారి కూడా ఫోన్ కాల్‌లో మీ OTP, పిన్ లేదా CVV చెప్పమని " +
                    "ఎప్పుడూ అడగరు. ఇది అడిగే వారు నేరుగా మీ ఖాతాను యాక్సెస్ చేయడానికి ప్రయత్నిస్తున్నారు."
                ),
        (
            "Banks and government bodies do not send someone to your home to collect your active " +
                "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
                "needs to physically take it from you."
            ) to
            (
                "బ్యాంకులు మరియు ప్రభుత్వ సంస్థలు మీ యాక్టివ్ డెబిట్ లేదా క్రెడిట్ కార్డును తీసుకోవడానికి ఎవరినీ మీ " +
                    "ఇంటికి పంపవు. మీ కార్డును బ్లాక్ చేయాల్సి వస్తే అది రిమోట్‌గానే చేయవచ్చు — ఎవరూ దాన్ని " +
                    "భౌతికంగా తీసుకోవాల్సిన అవసరం లేదు."
                ),

        "No fraud patterns detected; language consistent with legitimate messaging." to
            "మోసం సంకేతాలు ఏవీ కనుగొనబడలేదు; భాష సాధారణ, నమ్మదగిన సందేశంలా ఉంది.",

        "This looks like a scam. Do not share any code or send money." to
            "ఇది మోసంలా కనిపిస్తోంది. ఏ కోడ్ చెప్పకండి లేదా డబ్బు పంపకండి.",
        "This could be risky. Be careful and verify before doing anything." to
            "ఇది ప్రమాదకరం కావచ్చు. జాగ్రత్తగా ఉండండి, ఏదైనా చేసే ముందు నిర్ధారించుకోండి.",
        "This looks safe. Stay alert anyway." to
            "ఇది సురక్షితంగా కనిపిస్తోంది. అయినా అప్రమత్తంగా ఉండండి.",

        "Multiple risk signals were detected." to
            "అనేక ప్రమాద సంకేతాలు కనుగొనబడ్డాయి.",
        "Some risk signals were detected. Verify before proceeding." to
            "కొన్ని ప్రమాద సంకేతాలు కనుగొనబడ్డాయి. కొనసాగించే ముందు నిర్ధారించుకోండి.",
        "No risk signals were detected." to
            "ఎలాంటి ప్రమాద సంకేతాలు కనుగొనబడలేదు.",
    )

    const val ML_LIKELIHOOD_TEMPLATE: String =
        "స్పష్టమైన నియమం సరిపోలకపోయినా భాషా మోడల్ ప్రమాదాన్ని సూచిస్తోంది (మోసం సంభావ్యత %s)."
}
