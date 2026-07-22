package com.rakshak.ai.intelligence

import com.rakshak.ai.intelligence.translations.BengaliExplanations
import com.rakshak.ai.intelligence.translations.GujaratiExplanations
import com.rakshak.ai.intelligence.translations.HindiExplanations
import com.rakshak.ai.intelligence.translations.KannadaExplanations
import com.rakshak.ai.intelligence.translations.MalayalamExplanations
import com.rakshak.ai.intelligence.translations.MarathiExplanations
import com.rakshak.ai.intelligence.translations.OdiaExplanations
import com.rakshak.ai.intelligence.translations.PunjabiExplanations
import com.rakshak.ai.intelligence.translations.TamilExplanations
import com.rakshak.ai.intelligence.translations.TeluguExplanations
import com.rakshak.ai.intelligence.translations.UrduExplanations

/**
 * Static, pre-translated lookup for the fixed, finite set of explanation
 * strings ml/detector.py (build_signals(), NEAR_DETERMINISTIC_RULES,
 * build_reason()'s two rule-less fallbacks) and DecisionAgent.kt's own
 * headline()/defaultReason() can emit. Tier 3b's native-language TTS pass
 * (AutoEscalationCountdownActivity) looks each piece of decision.headline +
 * decision.reasons up here instead of ever feeding raw English text to a
 * non-English voice — doing that produced near-silent audio on this app's
 * target device/voice, not just mispronunciation (see that activity's
 * diagnosis comment).
 *
 * Deliberately NOT live/runtime translation. This table is exhaustive
 * against the fixed string set above and nothing else — an LLM-generated
 * `/assistant/chat`-style explanation, or any future free-text Prahari
 * field, is never in here. [translate] returning null is the expected,
 * routine outcome for those, and callers must treat it as "speak this piece
 * in English instead," never as an error.
 *
 * Per-language coverage: all 12 languages CLAUDE.md §11.3 targets (English,
 * which never needs translation, plus the 11 below) are drafted here, all
 * translated offline in the same LLM-batch pass. **Only Hindi (hi) has been
 * verified against a real device** — normal AudioTrack amplitude speaking
 * these strings through the hi-IN voice, versus the near-silent output that
 * prompted this table's existence (see AutoEscalationCountdownActivity). The
 * other 10 are drafted-but-unverified, same honesty convention as CLAUDE.md
 * §11.3's per-language coverage notes — don't describe them as confirmed
 * working until each is actually checked on a device with that voice
 * installed.
 */
object ExplanationTranslations {

    private val BY_LANGUAGE: Map<String, Map<String, String>> = mapOf(
        "hi" to HindiExplanations.MAP,
        "bn" to BengaliExplanations.MAP,
        "mr" to MarathiExplanations.MAP,
        "te" to TeluguExplanations.MAP,
        "ta" to TamilExplanations.MAP,
        "gu" to GujaratiExplanations.MAP,
        "ur" to UrduExplanations.MAP,
        "kn" to KannadaExplanations.MAP,
        "ml" to MalayalamExplanations.MAP,
        "pa" to PunjabiExplanations.MAP,
        "or" to OdiaExplanations.MAP,
    )

    private val ML_LIKELIHOOD_TEMPLATES: Map<String, String> = mapOf(
        "hi" to HindiExplanations.ML_LIKELIHOOD_TEMPLATE,
        "bn" to BengaliExplanations.ML_LIKELIHOOD_TEMPLATE,
        "mr" to MarathiExplanations.ML_LIKELIHOOD_TEMPLATE,
        "te" to TeluguExplanations.ML_LIKELIHOOD_TEMPLATE,
        "ta" to TamilExplanations.ML_LIKELIHOOD_TEMPLATE,
        "gu" to GujaratiExplanations.ML_LIKELIHOOD_TEMPLATE,
        "ur" to UrduExplanations.ML_LIKELIHOOD_TEMPLATE,
        "kn" to KannadaExplanations.ML_LIKELIHOOD_TEMPLATE,
        "ml" to MalayalamExplanations.ML_LIKELIHOOD_TEMPLATE,
        "pa" to PunjabiExplanations.ML_LIKELIHOOD_TEMPLATE,
        "or" to OdiaExplanations.ML_LIKELIHOOD_TEMPLATE,
    )

    /** Matches ml/detector.py::build_reason()'s only variable-content
     *  fallback: f"Language model flags risk (fraud likelihood {ml:.0%}) ..." */
    private val ML_LIKELIHOOD_PATTERN =
        Regex("""^Language model flags risk \(fraud likelihood (\d+%)\) though no explicit rule pattern matched\.$""")

    /**
     * Returns the pre-translated [englishText] for [languageTag] (matched by
     * BCP-47 base subtag, e.g. "hi-IN" -> "hi"), or null if this exact text
     * isn't in the fixed set for that language — including simply because
     * that language hasn't been added yet. Never throws, never guesses.
     */
    fun translate(englishText: String, languageTag: String): String? {
        val lang = languageTag.substringBefore('-').lowercase()
        BY_LANGUAGE[lang]?.get(englishText)?.let { return it }

        ML_LIKELIHOOD_PATTERN.matchEntire(englishText)?.let { match ->
            val template = ML_LIKELIHOOD_TEMPLATES[lang] ?: return null
            val percent = match.groupValues[1]
            return String.format(template, percent)
        }

        return null
    }
}
