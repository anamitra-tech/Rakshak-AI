package com.rakshak.ai.intelligence

/**
 * On-device port of ml/detector.py's NEAR_DETERMINISTIC_RULES (isolation_tactics,
 * otp_readout_request, card_collection_request; see DecisionAgent's
 * NEAR_DETERMINISTIC_RULE_CATEGORIES, which this must stay in sync with),
 * plus malware_attachment_delivery — added 2026-07-12 as an explicit,
 * deliberate exception to the "near-deterministic only" rule below: unlike
 * relative_impersonation/telecom_impersonation/extortion_threat (ordinary
 * contributing categories left off this list on purpose), every pattern in
 * malware_attachment_delivery already requires two conditions combined (a
 * forward-to-someone instruction plus either a computer-specific open
 * instruction or a risky attachment extension) — the same structural
 * certainty as the three NEAR_DETERMINISTIC_RULES categories, and
 * ml/detector.py's own critical-combo score bump already treats it as
 * FRAUD-alone (score = max(score, 0.85)), so mirroring it here for the
 * offline fallback doesn't diverge from what the real backend would say.
 * Patterns below are copied verbatim from HIGH_RISK_PATTERNS in
 * ml/detector.py — do not add, remove, or reword a pattern here without
 * updating both files. Deliberately excludes every other category
 * (money_demand, authority_impersonation, telecom_impersonation,
 * relative_impersonation, extortion_threat, malicious_link_bait, ...) —
 * none of those are deterministic-alone in Python (they only reach FRAUD in
 * combination with a second category), so treating a lone match as
 * automatic FRAUD offline would diverge from what the real backend would
 * say about the same text.
 *
 * Deliberately does NOT port ml/detector.py's BENIGN_CONTEXT guard (which
 * can strip an otp_readout_request-only hit on a legitimate "do not share
 * your OTP" bank SMS) — that guard only ever affects otp_readout_request,
 * and only when it is the *sole* rule hit with no other HIGH_RISK_PATTERNS
 * category also matching, which none of the patterns below plausibly
 * trigger on plain informational OTP text. Flagged as a known gap, not
 * silently designed around.
 *
 * This engine only ever runs as a Prahari-unreachable fallback (see
 * CheckCallActivity) — it never runs when the backend is reachable, and it
 * never overrides or downgrades a server verdict. No ML score, no fusion,
 * no thresholds: a single regex match here is exactly as certain offline as
 * it is online, by construction.
 */
object OfflineRuleEngine {

    data class Match(val category: String, val signalLabel: String, val explanation: String)

    private const val ISOLATION_TACTICS_EXPLANATION =
        "A genuine bank, police officer, or government official will never discourage you from " +
        "hanging up and verifying independently — through the bank's official number, a family " +
        "member, or in person. Any instruction to skip that step, handle it yourself on the " +
        "caller's behalf, or avoid \"disturbing\" family is itself the warning sign, regardless " +
        "of how calm or convincing the caller sounds."

    private const val OTP_READOUT_EXPLANATION =
        "No bank, police officer, or government official will ever ask you to read out your OTP, " +
        "PIN, or CVV over a phone call. Anyone asking for this is trying to access your account " +
        "directly."

    private const val CARD_COLLECTION_EXPLANATION =
        "Banks and government bodies do not send someone to your home to collect your active " +
        "debit or credit card. If your card needs to be blocked, it can be done remotely — no one " +
        "needs to physically take it from you."

    private const val MALWARE_ATTACHMENT_EXPLANATION =
        "A genuine colleague or organisation does not need an attachment relayed to someone else " +
        "unopened, or opened specifically on a computer rather than your phone — that combination " +
        "is a common way malware in a .zip, .exe, or macro-enabled file gets past a phone's more " +
        "limited execution environment and onto a real desktop where it can actually run."

    private val ISOLATION_TACTICS_PATTERNS = listOf(
        """(that|the) (line|number) is (always )?busy""",
        """(line|number) is (currently |always )?(overloaded|busy)""",
        """(staying|stay) on (this|the) call is (actually |really )?faster""",
        """(will|would|can) cause (a )?delay""",
        """duplicate (report|complaint|fir)""",
        """put you on hold""",
        """walk (you )?through .{0,40}(right now|on this call)""",
        """no need to (call|contact|inform) (the|your) (bank|police|branch|customer care)""",
        """don'?t (call|contact) (the|your) (bank|police|branch|customer care)""",
        """no (need|reason) to (worry|tell|inform|disturb|trouble) (your|the) (family|son|daughter|husband|wife|parents)""",
        """don'?t (tell|inform) (your )?family""",
        """pareshan (mat karo|karne ki zaroorat nahi)""",
        """batane ki zaroorat nahi""",
        """i (will|'ll) handle (it|this|everything) (for|so) you""",
        """i (will|'ll) (do|take care of) (it|this) (myself|for you|on your behalf)""",
        """on (your |my |our )?behalf""",
        """give me the phone,? i (will|'ll)""",
        """khud (kar dunga|sambhal lunga|karne do)""",
        """(agent|representative|executive|courier) will (come|visit|be sent)""",
        """((come|visit|aayega) (to|at)? ?(your|the|aapke) (home|house|residence|ghar).{0,60}""" +
            """(collect|take|le jaane|lene|surrender|hand over).{0,20}(card|documents?|papers?|cash|pin|cheque))""" +
            """|""" +
            """((collect|take|le jaane|lene|surrender|hand over).{0,20}(card|documents?|papers?|cash|pin|cheque).{0,60}""" +
            """(come|visit|aayega) (to|at)? ?(your|the|aapke) (home|house|residence|ghar))""",
        """no need to (visit|go to) the (bank|branch)""",
        """bank jaane ki zaroorat nahi""",
        """someone will come (to )?collect""",
        """collect karne""",
        """(don'?t|do not) hang up""",
        """stay on the line""",
        """disconnect.{0,20}(reset|invalidate|restart)""",
        """(shouldn'?t|should not|don'?t|avoid).{0,15}(involve|discuss|contact).{0,15}(third part|anyone else|others)""",
        """(main|hum) (khud |sab (kuch )?)?(kar dunga|karwa dunga|kar lunga|dekh lunga|manage kar (lenge|lunga))""",
        """(call cut|phone rakh(a|o)|disconnect kiya) (kiya |toh)""",
        """(parivaar|family) ko.{0,15}mat (laiye|batao|bataiye)""",
        """kisi (ko|se).{0,20}mat (kariyega|karna|bolna|batana)""",
        """(sensitive|confidential|gopniya|गोपनीय) (mamla|matter|मामला)""",
        """batane ki (zaroorat|permission) nahi""",
        """(kahin|police station|thane) jane ki (koi )?zar[ou]rat nahi""",
        """contact karne ki (koi )?need nahi""",
    ).map { Regex(it) }

    private val OTP_READOUT_PATTERNS = listOf(
        """read\s+(out\s+|me\s+)?(the\s+|your\s+)?(otp|pin|cvv|code|digits|one-?time code)""",
        """(tell|share|say|speak|send)\s+(me\s+|us\s+)?(the\s+|your\s+)?(otp|pin|cvv|code|verification code|one-?time code)""",
        """(code|digits)\s+(that\s+)?(just\s+)?arrived""",
        """(code|digits)\s+you'?re\s+seeing""",
        """(confirm|send|share|tell)\s+the\s+(six|four|\d+)[- ]?digit""",
        """(otp|pin|cvv|code)\s+(bata|bol|bhej|de\s?do)(o|iye|na|do)?""",
        // "de do"/"dedo" ("give [it]") added 2026-07-13, mirroring the same
        // fix in ml/detector.py — see that file's comment for why.
        """((bata|bol|bhej)(o|iye|do)|de\s?do)\s+(mujhe\s+)?(the\s+)?(otp|pin|cvv|code)""",
        """(provide|give|share|state|relay|pass on) (us |me )?(the |your )?""" +
            """(otp|one-time password|verification code|security code|authentication code|one-time key)""",
        """(code|digits|number|figures|password|key) (that |which )?(is |are )?""" +
            """(showing|displaying|received|got so far|came|mila)""",
        """what('s| is) the (code|number|digits|figures) (that |you )?(received|got|showing|displaying)""",
        """(aapke|aapka) (mobile|phone|number) par (aaya|aayi|mila) hua""",
        """(chh|chaar|char)-?ankiya (number|pin|code)""",
        """ओटीपी.{0,12}(बताएं|बताइए|दें|सूचित करें|चाहिए)""",
        """confirm\s+the\s+(verification|security|authentication|transaction)\s+code""",
        """confirm\s+the\s+code\s+(that'?s\s+|currently\s+|showing\s+)?on\s+(your|the)\s+screen""",
    ).map { Regex(it) }

    private val CARD_COLLECTION_PATTERNS = listOf(
        """(collect|come (to|and) collect|pick up|take)\s+(your|the)\s+.{0,25}card""",
        """hand over\s+(your|the)\s+.{0,25}card""",
        """give\s+.{0,10}(your|the) card to""",
        """keep\s+(the|your) pin (ready|written down)""",
        """card\s+(collect|le)\s+karne""",
        """pin\s+likh\s+kar\s+rakho""",
        """(representative|executive|agent|associate|staff member|individual).{0,20}""" +
            """(collect|receive|obtain|acquire|procure).{0,15}card""",
        """(dispatch|send|bhej rahe).{0,15}(executive|agent|representative|banda|aadmi|ladka|kisi ko).{0,20}card""",
        """surrender (your |the )?.{0,15}card""",
        """present your card to""",
        """card.{0,10}(jama|deposit|surrender).{0,10}(karna|karana) hoga""",
        """(hamara|humara) (banda|aadmi) .{0,15}card""",
        """pin.{0,15}(jot(ted)? down|note(d)? (down|on)|likh (lo|lena|kar))""",
        """pin.{0,10}(kagaz|paper|diary) par""",
        """कार्ड.{0,15}(लेने आएगा|लेने आएंगे|सुपुर्द|जमा|दें)""",
        """पिन.{0,10}(नोट कर|लिख)""",
    ).map { Regex(it) }

    private val MALWARE_ATTACHMENT_PATTERNS = listOf(
        """(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,60}""" +
            """(finance (manager|team|department)|accounts (team|department|manager)|""" +
            """(your |the )?(manager|boss|supervisor|hr( team)?)).{0,120}open.{0,20}(on|in).{0,10}""" +
            """(your |the )?(computer|pc|laptop|desktop)""",
        """open.{0,20}(on|in).{0,10}(your |the )?(computer|pc|laptop|desktop).{0,120}(forward|send|email).{0,25}""" +
            """(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,60}(finance (manager|team|department)|""" +
            """accounts (team|department|manager)|(your |the )?(manager|boss|supervisor|hr( team)?))""",
        """(finance manager|accounts (team|department|manager)|(company|apni company) ke (finance|accounts))""" +
            """.{0,50}(ko|ke liye)?.{0,25}forward kar ?(dijiye|do|kijiye|karein|ke)?.{0,120}""" +
            """(computer|pc|laptop|desktop) (par|pe) open ?(kijiye|karo|kariye|kar dijiye|karein)?""",
        """(computer|pc|laptop|desktop) (par|pe) open ?(kijiye|karo|kariye|kar dijiye|karein)?.{0,120}""" +
            """(finance manager|accounts (team|department|manager)|(company|apni company) ke (finance|accounts))""" +
            """.{0,50}(ko|ke liye)?.{0,25}forward kar ?(dijiye|do|kijiye|karein|ke)?""",
        """(forward|send|email).{0,25}(this|it|the.{0,15}(attachment|file|document|statement|zip)).{0,150}""" +
            """\.(zip|exe|scr|js|docm|xlsm|bat)\b""",
        """\.(zip|exe|scr|js|docm|xlsm|bat)\b.{0,150}(forward|send|email).{0,25}""" +
            """(this|it|the.{0,15}(attachment|file|document|statement|zip))""",
        """forward kar ?(dijiye|do|kijiye|karein|ke)?.{0,150}\.(zip|exe|scr|js|docm|xlsm|bat)\b""",
        """\.(zip|exe|scr|js|docm|xlsm|bat)\b.{0,150}forward kar ?(dijiye|do|kijiye|karein|ke)?""",
    ).map { Regex(it) }

    /**
     * Returns the first matching near-deterministic category, or null if
     * none matched. Order (isolation_tactics, otp_readout_request,
     * card_collection_request, malware_attachment_delivery) mirrors
     * HIGH_RISK_PATTERNS' dict order in ml/detector.py; since any single
     * match is already treated as certain, which one is reported first has
     * no effect on the resulting risk level.
     */
    fun check(text: String): Match? {
        val lowered = text.lowercase()
        if (ISOLATION_TACTICS_PATTERNS.any { it.containsMatchIn(lowered) }) {
            return Match(
                "isolation_tactics",
                "Discourages independent verification (bank/police/family)",
                ISOLATION_TACTICS_EXPLANATION,
            )
        }
        if (OTP_READOUT_PATTERNS.any { it.containsMatchIn(lowered) }) {
            return Match(
                "otp_readout_request",
                "Asks you to read out your OTP/PIN/CVV over the call",
                OTP_READOUT_EXPLANATION,
            )
        }
        if (CARD_COLLECTION_PATTERNS.any { it.containsMatchIn(lowered) }) {
            return Match(
                "card_collection_request",
                "Arranges in-person collection of your card, or asks you to keep the PIN ready",
                CARD_COLLECTION_EXPLANATION,
            )
        }
        if (MALWARE_ATTACHMENT_PATTERNS.any { it.containsMatchIn(lowered) }) {
            return Match(
                "malware_attachment_delivery",
                "Asks you to forward an attachment (e.g. to a finance/accounts contact) and open it " +
                    "on a computer, or names a risky file type (.zip/.exe/.docm/etc.)",
                MALWARE_ATTACHMENT_EXPLANATION,
            )
        }
        return null
    }
}
