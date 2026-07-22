package com.rakshak.ai.tts

import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import com.rakshak.ai.intelligence.ExplanationTranslations
import java.util.Locale

private const val TAG = "NativeThenEnglishTts"
private const val UTTERANCE_NATIVE = "native_then_english_native"
private const val UTTERANCE_ENGLISH = "native_then_english_english"

/**
 * Speaks a piece of English text in a preferred non-English language first
 * (via [ExplanationTranslations]' pre-translated lookup, forcing the
 * matching TTS voice), then in English — the "native language first,
 * English second" convention established for Tier 3b
 * (AutoEscalationCountdownActivity), extracted here so other screens (e.g.
 * the SAFE-state result card) get identical behavior instead of a
 * re-implementation.
 *
 * Skips the English repeat if [preferredTag] IS English, and falls back
 * straight to English if nothing in [ExplanationTranslations] matches
 * [englishText] for that language — never feeds raw English text through a
 * mismatched voice (see AutoEscalationCountdownActivity's near-silent-audio
 * diagnosis: forcing English text through the Hindi voice measured
 * mMaxAmplitude ~170 vs. a normal ~13000+).
 *
 * Callers own [tts]'s lifecycle and must confirm it's ready
 * (RakshakApp.onTtsReady) before calling [speak]. This class takes over
 * [tts]'s utterance-progress listener while speaking, overwriting whatever
 * was previously set — safe because only one screen is ever actively
 * speaking through the shared instance at a time.
 */
class NativeThenEnglishSpeaker(private val tts: TextToSpeech) {

    private var onComplete: (() -> Unit)? = null
    private var englishText: String = ""

    fun speak(englishText: String, preferredTag: String, onComplete: () -> Unit) {
        if (englishText.isBlank()) {
            onComplete()
            return
        }
        this.onComplete = onComplete
        this.englishText = englishText

        tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}

            override fun onDone(utteranceId: String?) = onUtteranceDone(utteranceId)

            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {
                Log.e(TAG, "TTS error on utterance=$utteranceId — proceeding.")
                onUtteranceDone(utteranceId)
            }
        })

        if (preferredTag.startsWith("en", ignoreCase = true)) {
            speakForced(englishText, "en-IN", UTTERANCE_ENGLISH)
            return
        }
        val nativeText = ExplanationTranslations.translate(englishText, preferredTag)
        if (nativeText.isNullOrBlank()) {
            speakForced(englishText, "en-IN", UTTERANCE_ENGLISH)
        } else {
            speakForced(nativeText, preferredTag, UTTERANCE_NATIVE)
        }
    }

    private fun onUtteranceDone(utteranceId: String?) {
        when (utteranceId) {
            UTTERANCE_NATIVE -> speakForced(englishText, "en-IN", UTTERANCE_ENGLISH)
            UTTERANCE_ENGLISH -> onComplete?.invoke()
            // Anything else isn't part of this chain — no-op.
        }
    }

    private fun speakForced(text: String, languageTag: String, utteranceId: String) {
        val result = tts.setLanguage(Locale.forLanguageTag(languageTag))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            Log.w(TAG, "Voice unavailable for $languageTag (result=$result) — skipping this pass.")
            onUtteranceDone(utteranceId)
            return
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }
}
