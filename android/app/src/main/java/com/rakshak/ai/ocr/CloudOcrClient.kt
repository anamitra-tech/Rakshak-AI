package com.rakshak.ai.ocr

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.File
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
 * instance, not a third party) — that's exactly why this is only ever
 * invoked when [ScreenshotOcrHelper] reports the script isn't covered
 * on-device, never as a first choice, and only when the caller has already
 * confirmed network connectivity.
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
    // views (setText, status text) off the main thread. Never surfaced
    // before this session because this is the first time a real network
    // request to /ocr/tesseract actually completed with a matched result --
    // every earlier attempt either used on-device OCR or errored before
    // reaching a callback. Posting through mainHandler makes every Callback
    // method (onSuccess/onNoTextFound/onFailure) main-thread-safe at the
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

    /** [evidenceBaseUrl] is AppSettings.evidenceBaseUrl — webhook/app.py's
     *  own base URL, the same server the missed-escalation evidence agent
     *  already talks to, not a new third-party endpoint. */
    fun recognizeText(context: Context, imageUri: Uri, evidenceBaseUrl: String, languageTag: String, callback: Callback) {
        val tesseractLang = tesseractLangFor(languageTag)
        if (tesseractLang == null) {
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

        val tempFile = File.createTempFile("ocr_upload_", ".jpg", context.cacheDir).apply {
            writeBytes(bytes)
        }
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", tempFile.name, tempFile.asRequestBody("image/*".toMediaType()))
            .addFormDataPart("lang", tesseractLang)
            .build()
        val request = Request.Builder()
            .url(evidenceBaseUrl.trimEnd('/') + "/ocr/tesseract")
            .post(multipart)
            .build()

        client.newCall(request).enqueue(object : okhttp3.Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e(TAG, "cloud_ocr_request_failed", e)
                tempFile.delete()
                mainHandler.post { callback.onFailure(e.message ?: "Online text extraction request failed.") }
            }

            override fun onResponse(call: Call, response: Response) {
                tempFile.delete()
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        val msg = "Online text extraction failed (HTTP ${resp.code})"
                        Log.e(TAG, "$msg body=${resp.body?.string()?.take(500)}")
                        mainHandler.post { callback.onFailure(msg) }
                        return
                    }
                    val json = try {
                        JSONObject(resp.body?.string().orEmpty())
                    } catch (e: Exception) {
                        Log.e(TAG, "cloud_ocr_parse_failed", e)
                        mainHandler.post { callback.onFailure("Could not parse the text-extraction response.") }
                        return
                    }
                    val found = json.optBoolean("found", false)
                    val text = json.optString("text").trim()
                    mainHandler.post {
                        if (!found || text.isEmpty()) callback.onNoTextFound() else callback.onSuccess(text)
                    }
                }
            }
        })
    }
}
