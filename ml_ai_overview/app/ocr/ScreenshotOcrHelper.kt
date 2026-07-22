package com.rakshak.ai.ocr

import android.content.Context
import android.net.Uri
import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

/**
 * On-device OCR for the "Upload screenshot" option on the "Check a
 * call/message" screen — alongside typed and voice input, never a
 * replacement. Uses ML Kit's bundled on-device text-recognition models: the
 * image never leaves the device, no network call, no API key, for the two
 * scripts ML Kit actually ships a recognizer for that this app targets
 * (Latin, Devanagari).
 *
 * ML Kit v2 has NO recognizer at all — not a config gap, a hard product
 * limitation — for Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati,
 * Gurmukhi (Punjabi), Odia, or Perso-Arabic (Urdu) scripts. [ScriptFamily.NONE]
 * tells the caller so it can react explicitly rather than silently getting
 * nothing back — as of 2026-07-16 `CheckCallActivity` treats NONE as
 * "OCR unreliable for this language, redirect to typed/voice input" (CLAUDE.md
 * Section 13), not "try the online OCR fallback" ([ocr.CloudOcrClient], left
 * in place but currently unreferenced — see its doc comment).
 */
object ScreenshotOcrHelper {
    private const val TAG = "ScreenshotOcrHelper"

    enum class ScriptFamily { LATIN, DEVANAGARI, NONE }

    /** Maps the app's BCP-47 spoken-language tag to the on-device script
     *  family it implies. Unknown/unset tags default to LATIN (English). */
    fun scriptFamilyFor(languageTag: String): ScriptFamily = when {
        languageTag.startsWith("hi", ignoreCase = true) ||
            languageTag.startsWith("mr", ignoreCase = true) -> ScriptFamily.DEVANAGARI
        languageTag.startsWith("en", ignoreCase = true) -> ScriptFamily.LATIN
        languageTag.startsWith("bn", ignoreCase = true) ||
            languageTag.startsWith("ta", ignoreCase = true) ||
            languageTag.startsWith("te", ignoreCase = true) ||
            languageTag.startsWith("kn", ignoreCase = true) ||
            languageTag.startsWith("ml", ignoreCase = true) ||
            languageTag.startsWith("gu", ignoreCase = true) ||
            languageTag.startsWith("pa", ignoreCase = true) ||
            languageTag.startsWith("or", ignoreCase = true) ||
            languageTag.startsWith("ur", ignoreCase = true) -> ScriptFamily.NONE
        else -> ScriptFamily.LATIN
    }

    interface Callback {
        /** [matchedScript] is whichever recognizer actually found the text —
         *  not necessarily [preferredScript] passed to [recognizeText] (see
         *  its doc comment) — callers use this to decide whether the result
         *  needs translating before reaching Prahari's classifier. */
        fun onSuccess(text: String, matchedScript: ScriptFamily)
        /** Ran fine, found nothing readable — different from [onFailure],
         *  which means the recognizer itself errored. */
        fun onNoTextFound()
        fun onFailure(message: String)
        /** Neither on-device recognizer applies to [preferredScript] — as of
         *  2026-07-16 (CLAUDE.md Section 13) callers treat this as "OCR is
         *  unreliable for this language," redirecting to typed/voice input,
         *  rather than trying an online OCR fallback. */
        fun onScriptNotSupportedOnDevice()
    }

    /**
     * Tries the on-device recognizer matching [preferredScript] first (the
     * language the family configured, via [scriptFamilyFor]); if that finds
     * nothing, tries the other on-device recognizer too, since a screenshot's
     * actual script isn't guaranteed to match the app's configured spoken
     * language (e.g. an English-language-app-user forwarded a Hindi scam
     * text). Only calls [Callback.onScriptNotSupportedOnDevice] when
     * [preferredScript] is [ScriptFamily.NONE] — for LATIN/DEVANAGARI we
     * always have an on-device option to try, even if it comes up empty.
     */
    fun recognizeText(context: Context, imageUri: Uri, preferredScript: ScriptFamily, callback: Callback) {
        val image = try {
            InputImage.fromFilePath(context, imageUri)
        } catch (e: Exception) {
            Log.e(TAG, "ocr_image_load_failed", e)
            callback.onFailure(e.message ?: "Could not read the selected image.")
            return
        }

        if (preferredScript == ScriptFamily.NONE) {
            callback.onScriptNotSupportedOnDevice()
            return
        }

        val primary = recognizerFor(preferredScript)
        primary.process(image)
            .addOnSuccessListener { result ->
                val text = result.text.trim()
                if (text.isNotEmpty()) {
                    callback.onSuccess(text, preferredScript)
                } else {
                    tryOtherRecognizer(image, preferredScript, callback)
                }
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "ocr_recognition_failed script=$preferredScript", e)
                tryOtherRecognizer(image, preferredScript, callback)
            }
    }

    private fun tryOtherRecognizer(image: InputImage, alreadyTried: ScriptFamily, callback: Callback) {
        val other = if (alreadyTried == ScriptFamily.LATIN) ScriptFamily.DEVANAGARI else ScriptFamily.LATIN
        recognizerFor(other).process(image)
            .addOnSuccessListener { result ->
                val text = result.text.trim()
                if (text.isEmpty()) callback.onNoTextFound() else callback.onSuccess(text, other)
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "ocr_recognition_failed script=$other", e)
                callback.onFailure(e.message ?: "Text recognition failed.")
            }
    }

    private fun recognizerFor(script: ScriptFamily) = when (script) {
        ScriptFamily.DEVANAGARI -> TextRecognition.getClient(DevanagariTextRecognizerOptions.Builder().build())
        else -> TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }
}
