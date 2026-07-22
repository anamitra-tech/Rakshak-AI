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

    /** Unicode script ranges for the native (non-Latin) scripts of all 12
     *  target languages, mapped to this app's BCP-47 tag convention (not the
     *  Sarvam code directly — [toSarvamCode] handles the Odia exception when
     *  these are actually sent to Sarvam). Devanagari is shared by Hindi and
     *  Marathi and Bengali script by Bengali and Assamese (both ambiguous —
     *  default to the more common of the pair, the same approximation
     *  CheckCallActivity's OCR script routing already makes); Arabic script
     *  covers Urdu. */
    private val SCRIPT_RANGES: List<Pair<IntRange, String>> = listOf(
        // Devanagari (Hindi/Marathi) -- deliberately excludes U+0964/U+0965
        // (danda / double danda). Real bug found testing the server-side
        // twin of this function: those two codepoints live in the
        // Devanagari Unicode block but are shared punctuation reused as a
        // sentence-final mark by several other Brahmic scripts (Bengali in
        // particular) -- a naive full-block check misdetects a Bengali
        // message ending in "।" as Devanagari/Hindi and it never actually
        // gets translated from Bengali at all.
        0x0900..0x0963 to "hi-IN",
        0x0966..0x097F to "hi-IN",
        0x0980..0x09FF to "bn-IN", // Bengali (Bengali/Assamese)
        0x0A00..0x0A7F to "pa-IN", // Gurmukhi (Punjabi)
        0x0A80..0x0AFF to "gu-IN", // Gujarati
        0x0B00..0x0B7F to "or-IN", // Odia
        0x0B80..0x0BFF to "ta-IN", // Tamil
        0x0C00..0x0C7F to "te-IN", // Telugu
        0x0C80..0x0CFF to "kn-IN", // Kannada
        0x0D00..0x0D7F to "ml-IN", // Malayalam
        0x0600..0x06FF to "ur-IN", // Arabic script (Urdu)
        0x0750..0x077F to "ur-IN", // Arabic Supplement (Urdu)
    )

    /**
     * Content-based script detection, used as a fallback when the input path
     * carries no source-language metadata (typed/pasted text — OCR and voice
     * input already tag [transcriptSourceLanguageTag][com.rakshak.ai.ui.CheckCallActivity]
     * explicitly). Scans the raw text for any of the 12 target languages'
     * native scripts and returns the BCP-47 tag to translate from, or null
     * if the text is pure Latin script (English or Romanized Hinglish —
     * already directly usable by ml.detector's patterns, no translation
     * needed).
     *
     * Mirrors webhook/app.py's `_detect_native_script_lang` exactly — same
     * real bug this fixes: a prior check here (and server-side) keyed "skip
     * translation" off *language* (a Devanagari-only regex, treating Hindi
     * as "already handled" since Prahari's classifier docs mention Hindi
     * support) instead of *script* (whether ml.detector's Latin-script-only
     * patterns can match this text at all — they can't, for any native
     * script, not just Devanagari). General across all 12 languages; does
     * not special-case any one of them.
     *
     * Real bug fixed 2026-07-15, traced live via a Hindi OCR test: this used
     * to return on the FIRST script match found while scanning codepoints in
     * text order, so a single stray misread character (ML Kit's Devanagari
     * recognizer hallucinating one Bengali glyph "যা" from a forwarded-
     * message icon at the very start of an otherwise all-Devanagari message
     * — a real, already-diagnosed OCR artifact, not a state leak) overrode
     * the actual, overwhelmingly-dominant script of the real message.
     * Confirmed live: metadataTag=hi-IN (correct) got overridden to
     * contentDetectedTag=bn-IN (wrong) purely because of that one leading
     * character. Now a majority vote across the whole text — whichever
     * script has the most matching codepoints wins — so one stray glyph
     * can't outvote dozens of genuine same-script characters.
     */
    fun detectNativeScriptTag(text: String): String? {
        val counts = mutableMapOf<String, Int>()
        for (codePoint in text.codePoints()) {
            for ((range, tag) in SCRIPT_RANGES) {
                if (codePoint in range) {
                    counts[tag] = (counts[tag] ?: 0) + 1
                    break
                }
            }
        }
        return counts.maxByOrNull { it.value }?.key
    }
}
