package com.rakshak.ai.tts

import android.speech.tts.TextToSpeech
import android.util.Log
import com.google.mlkit.nl.languageid.LanguageIdentification
import java.util.Locale

/**
 * Auto-selects the Android TTS voice/locale that matches the language of the
 * text actually being spoken, instead of always using one fixed configured
 * language. Detection runs via ML Kit's on-device Language Identification --
 * the model ships bundled in the app, no network call, no text ever leaves
 * the device for this.
 *
 * Fallback chain, never blocks and never throws out of [speak]:
 *   1. the detected language, if confidently identified AND a matching TTS
 *      voice is installed;
 *   2. [fallbackLanguageTag] (the app's configured AppSettings.spokenLanguageTag),
 *      if a matching TTS voice is installed for that;
 *   3. whatever locale the TextToSpeech engine is already using -- left
 *      untouched rather than forced to something unavailable.
 */
object SpeechLanguageSelector {
    private const val TAG = "SpeechLanguageSelector"

    // ML Kit returns bare ISO 639-1 (mostly) codes; mapped here to a BCP-47
    // tag with an Indian region for the 12 languages this app targets -- see
    // CLAUDE.md's STT/TTS coverage section for what's actually installable
    // per language. Anything not in this map falls back to fallbackLanguageTag.
    private val DETECTED_LANGUAGE_TO_TAG: Map<String, String> = mapOf(
        "en" to "en-IN",
        "hi" to "hi-IN",
        "bn" to "bn-IN",
        "mr" to "mr-IN",
        "te" to "te-IN",
        "ta" to "ta-IN",
        "gu" to "gu-IN",
        "ur" to "ur-IN",
        "kn" to "kn-IN",
        "ml" to "ml-IN",
        "pa" to "pa-IN",
        "or" to "or-IN",
    )

    fun speak(tts: TextToSpeech, text: String, fallbackLanguageTag: String, utteranceId: String) {
        if (text.isBlank()) return
        try {
            LanguageIdentification.getClient()
                .identifyLanguage(text)
                .addOnSuccessListener { code ->
                    val detectedTag = if (code != "und") DETECTED_LANGUAGE_TO_TAG[code] else null
                    applyLocaleAndSpeak(tts, text, detectedTag, fallbackLanguageTag, utteranceId)
                }
                .addOnFailureListener { e ->
                    Log.w(TAG, "language identification failed, using fallback language", e)
                    applyLocaleAndSpeak(tts, text, null, fallbackLanguageTag, utteranceId)
                }
        } catch (e: Exception) {
            // Defensive: ML Kit is a third-party dependency; a failure here
            // must never mean the warning goes unspoken.
            Log.e(TAG, "language identification threw, using fallback language", e)
            applyLocaleAndSpeak(tts, text, null, fallbackLanguageTag, utteranceId)
        }
    }

    private fun applyLocaleAndSpeak(
        tts: TextToSpeech,
        text: String,
        detectedTag: String?,
        fallbackLanguageTag: String,
        utteranceId: String,
    ) {
        val chosen = detectedTag?.takeIf { isUsable(tts, it) }
            ?: fallbackLanguageTag.takeIf { isUsable(tts, it) }
        if (chosen != null) {
            tts.setLanguage(Locale.forLanguageTag(chosen))
            Log.i(TAG, "tts_language_selected tag=$chosen detected=$detectedTag fallback=$fallbackLanguageTag")
        } else {
            Log.w(
                TAG,
                "tts_language_unavailable detected=$detectedTag fallback=$fallbackLanguageTag; keeping current tts locale",
            )
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }

    private fun isUsable(tts: TextToSpeech, tag: String): Boolean {
        val result = try {
            tts.isLanguageAvailable(Locale.forLanguageTag(tag))
        } catch (e: Exception) {
            Log.e(TAG, "isLanguageAvailable check failed for $tag", e)
            return false
        }
        return result == TextToSpeech.LANG_AVAILABLE ||
            result == TextToSpeech.LANG_COUNTRY_AVAILABLE ||
            result == TextToSpeech.LANG_COUNTRY_VAR_AVAILABLE
    }
}
