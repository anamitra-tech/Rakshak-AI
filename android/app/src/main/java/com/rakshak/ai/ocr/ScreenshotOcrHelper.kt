package com.rakshak.ai.ocr

import android.content.Context
import android.net.Uri
import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions

/**
 * On-device OCR for the "Upload screenshot" option on the "Check a
 * call/message" screen — alongside typed and voice input, never a
 * replacement. Uses ML Kit's bundled on-device text-recognition model (Latin
 * script only, same posture as language-id's bundled model elsewhere in this
 * app): the image never leaves the device, no network call, no API key.
 *
 * Latin-script-only is a real, disclosed gap for now — the same one
 * CLAUDE.md Section 11.3 already documents for on-device STT: a screenshot
 * of a scam message in Devanagari/Tamil/Telugu/etc. script will not OCR
 * correctly with this dependency. ML Kit ships separate script-specific
 * artifacts (text-recognition-devanagari, etc.) that could close this later;
 * not added now since it wasn't asked for and would need its own real-device
 * verification before claiming it works.
 */
object ScreenshotOcrHelper {
    private const val TAG = "ScreenshotOcrHelper"

    interface Callback {
        fun onSuccess(text: String)
        /** Ran fine, found nothing readable — different from [onFailure],
         *  which means the recognizer itself errored. */
        fun onNoTextFound()
        fun onFailure(message: String)
    }

    fun recognizeText(context: Context, imageUri: Uri, callback: Callback) {
        val image = try {
            InputImage.fromFilePath(context, imageUri)
        } catch (e: Exception) {
            Log.e(TAG, "ocr_image_load_failed", e)
            callback.onFailure(e.message ?: "Could not read the selected image.")
            return
        }

        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        recognizer.process(image)
            .addOnSuccessListener { result ->
                val text = result.text.trim()
                if (text.isEmpty()) callback.onNoTextFound() else callback.onSuccess(text)
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "ocr_recognition_failed", e)
                callback.onFailure(e.message ?: "Text recognition failed.")
            }
    }
}
