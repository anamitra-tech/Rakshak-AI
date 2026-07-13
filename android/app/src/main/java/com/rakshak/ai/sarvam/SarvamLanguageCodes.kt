package com.rakshak.ai.sarvam

/**
 * Maps this app's BCP-47 spoken-language tag convention (AppSettings,
 * SpeechLanguageSelector — "or-IN" for Odia) to Sarvam's own language codes,
 * which are identical for 11 of the 12 target languages but use "od-IN" for
 * Odia instead of the standard BCP-47 "or-IN". A real, easy-to-miss mismatch
 * confirmed against Sarvam's published speech-to-text docs — not a 1:1
 * pass-through.
 */
object SarvamLanguageCodes {
    fun toSarvamCode(appLanguageTag: String): String =
        if (appLanguageTag.equals("or-IN", ignoreCase = true)) "od-IN" else appLanguageTag

    fun fromSarvamCode(sarvamLanguageCode: String): String =
        if (sarvamLanguageCode.equals("od-IN", ignoreCase = true)) "or-IN" else sarvamLanguageCode

    /** Sarvam's Bulbul TTS model covers only 11 of the 12 target languages —
     *  Urdu has no Sarvam TTS voice at all (confirmed against Sarvam's Bulbul
     *  docs). Native Android TTS is the only option for Urdu speech output. */
    val TTS_SUPPORTED_TAGS: Set<String> = setOf(
        "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "or-IN", "pa-IN", "ta-IN", "te-IN", "en-IN", "gu-IN",
    )
}
