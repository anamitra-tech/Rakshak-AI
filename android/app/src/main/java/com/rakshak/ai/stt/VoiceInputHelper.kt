package com.rakshak.ai.stt

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import com.rakshak.ai.R

/**
 * Wraps Android's on-device SpeechRecognizer for the "Check a call/message"
 * screen's optional voice-input affordance (CLAUDE.md Section 3.2 / 9.2's
 * future STT hook) -- always alongside typed input, never a replacement.
 *
 * Deliberately restricted to API 31+ ([SpeechRecognizer.createOnDeviceSpeechRecognizer]):
 * that is the first platform level with an API that *guarantees* fully local
 * recognition with no network fallback. Below API 31 there is no way to force
 * offline-only behavior -- the regular [SpeechRecognizer.createSpeechRecognizer]
 * plus `EXTRA_PREFER_OFFLINE` is only a hint, and Android may silently use a
 * cloud recognizer instead, which this app's privacy posture (no audio/text
 * leaves the device without the user typing it) treats as unacceptable rather
 * than a case to design around. So on API 29-30, [isDeviceCapable] returns
 * false and callers should hide the mic option entirely, leaving typed input
 * as the only path -- never a crash, never a silent fallback to the cloud.
 *
 * Whether an offline language *pack* is actually installed for a given
 * language is not knowable ahead of time on any API level (there is no public
 * "is this language downloaded" query) -- this class discovers it empirically,
 * at the moment recognition is attempted, via [SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED]
 * / [SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE]. See CLAUDE.md's STT/TTS
 * coverage section for what this means per-language in practice.
 */
class VoiceInputHelper(private val context: Context) {

    private var recognizer: SpeechRecognizer? = null

    interface Callback {
        fun onListeningStateChanged(listening: Boolean)
        fun onPartialResult(text: String)
        fun onFinalResult(text: String)
        /** Transient: no speech caught, timeout, momentarily busy -- safe to let the user retry. */
        fun onTransientError(message: String)
        /** Not transient: no offline pack for this language, or no on-device
         *  recognizer service at all -- caller should stop offering voice
         *  input for this session rather than inviting a retry loop. */
        fun onLanguageOrDeviceUnavailable(message: String)
    }

    /** Whether this device/OS version can even be asked -- does not guarantee
     *  any particular language has an offline pack installed. */
    fun isDeviceCapable(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return false
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
            } else {
                // No upfront probe exists for API 31-32; assume present and
                // let an actual attempt fail gracefully via onError if not.
                true
            }
        } catch (e: Exception) {
            Log.e(TAG, "on-device recognition capability check failed", e)
            false
        }
    }

    /**
     * [languageTag] is a BCP-47 tag, e.g. "hi-IN" -- normally the app's
     * configured AppSettings.spokenLanguageTag, reused here as the assumed
     * language of what the user is about to say.
     */
    fun startListening(languageTag: String, callback: Callback) {
        if (!isDeviceCapable()) {
            callback.onLanguageOrDeviceUnavailable(context.getString(R.string.check_call_voice_unsupported_device))
            return
        }
        stopListening()
        try {
            val r = SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
            recognizer = r
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, context.packageName)
            }
            r.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    callback.onListeningStateChanged(true)
                }

                override fun onResults(results: Bundle?) {
                    callback.onListeningStateChanged(false)
                    val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (text.isNullOrBlank()) {
                        callback.onTransientError(context.getString(R.string.check_call_voice_no_match))
                    } else {
                        callback.onFinalResult(text)
                    }
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    val text = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                    if (!text.isNullOrBlank()) callback.onPartialResult(text)
                }

                override fun onError(error: Int) {
                    callback.onListeningStateChanged(false)
                    val (message, isPersistent) = describeError(error, languageTag)
                    if (isPersistent) callback.onLanguageOrDeviceUnavailable(message)
                    else callback.onTransientError(message)
                }

                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { callback.onListeningStateChanged(false) }
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
            r.startListening(intent)
        } catch (e: Exception) {
            Log.e(TAG, "startListening failed", e)
            callback.onTransientError(context.getString(R.string.check_call_voice_start_failed))
        }
    }

    fun stopListening() {
        try {
            recognizer?.stopListening()
            recognizer?.destroy()
        } catch (e: Exception) {
            Log.e(TAG, "stopListening cleanup failed", e)
        } finally {
            recognizer = null
        }
    }

    /** Returns (user-facing message, isPersistent) -- isPersistent means
     *  "don't invite an immediate retry", not "never usable again this app run". */
    private fun describeError(error: Int, languageTag: String): Pair<String, Boolean> {
        return when (error) {
            SpeechRecognizer.ERROR_NO_MATCH ->
                context.getString(R.string.check_call_voice_no_match) to false
            SpeechRecognizer.ERROR_SPEECH_TIMEOUT ->
                context.getString(R.string.check_call_voice_timeout) to false
            SpeechRecognizer.ERROR_RECOGNIZER_BUSY ->
                context.getString(R.string.check_call_voice_busy) to false
            SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS ->
                context.getString(R.string.check_call_voice_mic_permission_needed) to false
            SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED,
            SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE ->
                context.getString(R.string.check_call_voice_language_unsupported, languageTag) to true
            SpeechRecognizer.ERROR_CLIENT,
            SpeechRecognizer.ERROR_SERVER_DISCONNECTED ->
                context.getString(R.string.check_call_voice_recognizer_unset) to true
            else ->
                context.getString(R.string.check_call_voice_generic_error) to false
        }
    }

    companion object {
        private const val TAG = "VoiceInputHelper"
    }
}
