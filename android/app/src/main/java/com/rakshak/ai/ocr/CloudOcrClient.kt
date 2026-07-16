package com.rakshak.ai.ocr

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.rakshak.ai.sarvam.SarvamLanguageCodes
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Online OCR fallback for scripts ML Kit has no on-device recognizer for
 * (Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Odia,
 * Urdu — see [ScreenshotOcrHelper.ScriptFamily.NONE]). Calls Prahari's own
 * self-hosted `/ocr/tesseract` endpoint (webhook/app.py) — Tesseract 5 +
 * the matching tessdata language pack — rather than Google Cloud Vision:
 * GCP Vision needs a billing account, which isn't available for this
 * project (same constraint that ruled out the Meta WhatsApp Business API
 * path earlier). No API key here; only network reachability to Prahari.
 *
 * The image bytes leave the device for this call (to your own Prahari
 * instance, not a third party) — that's exactly why this was only ever
 * invoked when [ScreenshotOcrHelper] reports the script isn't covered
 * on-device, never as a first choice, and only when the caller had already
 * confirmed network connectivity.
 *
 * 2026-07-16: currently unreferenced. A real accuracy audit (CLAUDE.md
 * Section 13) found this exact 9-script Tesseract path unreliable enough
 * (under-called scores, false negatives on Telugu/Tamil, hallucinated
 * translations on Urdu) that `CheckCallActivity`'s
 * `onScriptNotSupportedOnDevice` no longer calls it — those 9 languages
 * redirect straight to typed/voice input instead, same policy as
 * webhook/app.py's `_OCR_RELIABLE_LANGUAGES` gate for WhatsApp. Left in
 * place (not deleted) since the underlying `/ocr/tesseract` endpoint is
 * unchanged and this could be re-wired back in if OCR accuracy for these
 * scripts improves later — see CLAUDE.md Section 13 before doing so.
 */
object CloudOcrClient {
    private const val TAG = "CloudOcrClient"

    interface Callback {
        fun onSuccess(text: String)
        fun onNoTextFound()
        fun onFailure(message: String)
    }

    // Real crash traced live: OkHttp's enqueue() callbacks run on its own
    // internal dispatcher thread, not the caller's (main) thread -- unlike
    // ML Kit's on-device recognizers (Play Services Tasks post completion
    // back to the calling/main thread automatically), so this was the only
    // OCR path in CheckCallActivity where the caller's Callback touched
    // views (setText, status text) off the main thread. Posting through
    // mainHandler makes every Callback method main-thread-safe at the
    // source, so no call site has to remember to do it itself.
    private val mainHandler = Handler(Looper.getMainLooper())

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(40, TimeUnit.SECONDS)
        .build()

    /** Maps this app's BCP-47 spoken-language tag to the 3-letter Tesseract
     *  language code for the 9 scripts this fallback covers. Null for any
     *  tag Tesseract routing doesn't apply to (Latin/Devanagari go through
     *  on-device ScreenshotOcrHelper instead, never reach here). */
    fun tesseractLangFor(languageTag: String): String? = when {
        languageTag.startsWith("bn", ignoreCase = true) -> "ben"
        languageTag.startsWith("ta", ignoreCase = true) -> "tam"
        languageTag.startsWith("te", ignoreCase = true) -> "tel"
        languageTag.startsWith("kn", ignoreCase = true) -> "kan"
        languageTag.startsWith("ml", ignoreCase = true) -> "mal"
        languageTag.startsWith("gu", ignoreCase = true) -> "guj"
        languageTag.startsWith("pa", ignoreCase = true) -> "pan"
        languageTag.startsWith("or", ignoreCase = true) -> "ori"
        languageTag.startsWith("ur", ignoreCase = true) -> "urd"
        else -> null
    }

    /** Every Tesseract lang this fallback covers, paired with the BCP-47
     *  script tag [SarvamLanguageCodes.detectNativeScriptTag] returns for
     *  that script -- used to validate a result actually looks like the
     *  script we asked Tesseract to read, not just "some text came back". */
    private val CLOUD_OCR_LANGS: List<Pair<String, String>> = listOf(
        "ben" to "bn-IN", "tam" to "ta-IN", "tel" to "te-IN", "kan" to "kn-IN",
        "mal" to "ml-IN", "guj" to "gu-IN", "pan" to "pa-IN", "ori" to "or-IN", "urd" to "ur-IN",
    )

    /**
     * [evidenceBaseUrl] is AppSettings.evidenceBaseUrl — webhook/app.py's
     * own base URL, the same server the missed-escalation evidence agent
     * already talks to, not a new third-party endpoint.
     *
     * Real bug traced live: this used to trust [languageTag] (the family's
     * configured spoken language) unconditionally and only ever try that
     * one Tesseract language pack. Three separate tests this session hit
     * the same failure: whenever a screenshot's actual script didn't match
     * whatever the family had last configured (a Bengali test right after
     * a Hindi one, a Telugu test right after that, then Hindi/Bengali
     * screenshots tested right after switching to Tamil), Tesseract still
     * "succeeded" -- it just read the wrong script's glyphs and returned
     * confident-looking garbage in ITS language, not an error. CLAUDE.md's
     * own design principle says language setup is a one-time family task,
     * not something to be re-litigated per message/screenshot -- so this
     * can't rely on the configured language always matching what's being
     * checked. Now: try [languageTag]'s Tesseract lang first (fast path,
     * no extra cost when it's already correct), and if the result's actual
     * detected script doesn't match what was asked for, automatically walk
     * the other 8 covered languages until one produces a script-plausible
     * result -- reusing the same content-based script check
     * (detectNativeScriptTag) already used to fix the same class of bug
     * for OCR-vs-translate routing.
     */
    fun recognizeText(context: Context, imageUri: Uri, evidenceBaseUrl: String, languageTag: String, callback: Callback) {
        val preferredLang = tesseractLangFor(languageTag)
        if (preferredLang == null) {
            callback.onFailure("No Tesseract language mapping for $languageTag")
            return
        }
        val bytes = try {
            context.contentResolver.openInputStream(imageUri)?.use { it.readBytes() }
        } catch (e: Exception) {
            Log.e(TAG, "cloud_ocr_image_read_failed", e)
            null
        }
        if (bytes == null) {
            callback.onFailure("Could not read the selected image.")
            return
        }

        val preferredExpectedTag = CLOUD_OCR_LANGS.firstOrNull { it.first == preferredLang }?.second
        val orderedCandidates = listOfNotNull(preferredExpectedTag?.let { preferredLang to it }) +
            CLOUD_OCR_LANGS.filter { it.first != preferredLang }

        attemptCandidates(bytes, evidenceBaseUrl, orderedCandidates, 0, null, callback)
    }

    /**
     * Tries [candidates][index] against Tesseract; on a script-plausible
     * match, reports success immediately. On "no text"/script-mismatch,
     * moves to the next candidate. On a real network/HTTP error, stops
     * immediately and reports failure rather than burning through the
     * remaining 8 candidates against an unreachable server. [bestGuess] is
     * the first non-empty result seen so far (language, text), kept as a
     * fallback to report once every candidate is exhausted without a
     * script-plausible match -- Tesseract DID find something, so that's a
     * more honest answer than a blanket "no text found".
     */
    private fun attemptCandidates(
        bytes: ByteArray,
        evidenceBaseUrl: String,
        candidates: List<Pair<String, String>>,
        index: Int,
        bestGuess: String?,
        callback: Callback,
    ) {
        if (index >= candidates.size) {
            mainHandler.post {
                if (bestGuess != null) callback.onSuccess(bestGuess) else callback.onNoTextFound()
            }
            return
        }
        val (tesseractLang, expectedScriptTag) = candidates[index]
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", "ocr_upload.jpg", bytes.toRequestBody("image/*".toMediaType()))
            .addFormDataPart("lang", tesseractLang)
            .build()
        val request = Request.Builder()
            .url(evidenceBaseUrl.trimEnd('/') + "/ocr/tesseract")
            .post(multipart)
            .build()

        client.newCall(request).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "cloud_ocr_request_failed lang=$tesseractLang", e)
                mainHandler.post { callback.onFailure(e.message ?: "Online text extraction request failed.") }
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        val msg = "Online text extraction failed (HTTP ${resp.code})"
                        Log.e(TAG, "$msg lang=$tesseractLang body=${resp.body?.string()?.take(500)}")
                        mainHandler.post { callback.onFailure(msg) }
                        return
                    }
                    val json = try {
                        JSONObject(resp.body?.string().orEmpty())
                    } catch (e: Exception) {
                        Log.e(TAG, "cloud_ocr_parse_failed lang=$tesseractLang", e)
                        mainHandler.post { callback.onFailure("Could not parse the text-extraction response.") }
                        return
                    }
                    val found = json.optBoolean("found", false)
                    val text = json.optString("text").trim()
                    if (!found || text.isEmpty()) {
                        attemptCandidates(bytes, evidenceBaseUrl, candidates, index + 1, bestGuess, callback)
                        return
                    }
                    val detected = SarvamLanguageCodes.detectNativeScriptTag(text)
                    if (detected == expectedScriptTag) {
                        Log.i(TAG, "cloud_ocr_script_match lang=$tesseractLang attempt=${index + 1}")
                        mainHandler.post { callback.onSuccess(text) }
                    } else {
                        Log.i(TAG, "cloud_ocr_script_mismatch lang=$tesseractLang expected=$expectedScriptTag detected=$detected")
                        attemptCandidates(bytes, evidenceBaseUrl, candidates, index + 1, bestGuess ?: text, callback)
                    }
                }
            }
        })
    }
}
