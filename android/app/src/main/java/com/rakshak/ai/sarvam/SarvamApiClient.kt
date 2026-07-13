package com.rakshak.ai.sarvam

import com.rakshak.ai.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Thrown when Sarvam is unreachable, unconfigured, or returns something
 *  unexpected — always a best-effort fallback path, never fatal to the
 *  caller's overall flow (typed input / offline evaluator still work). */
class SarvamUnavailableException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Client for Sarvam-backed functionality the Android app uses.
 * `/translate` is called directly against Sarvam (text-only, fast, no
 * length concerns). Speech-to-text is instead proxied through Prahari's own
 * webhook/app.py (`/stt/sarvam`) rather than calling api.sarvam.ai directly
 * — real bug this fixed: a direct-from-Android call has no way to run the
 * sync-endpoint-then-async-batch-job fallback that long audio needs (that
 * logic lives in `_transcribe_audio_sarvam`/`_transcribe_audio_sarvam_batch`,
 * Python-only, using the `sarvamai` SDK's job API), so anything over the
 * sync endpoint's real ~30s limit just failed outright. Proxying reuses the
 * already-working, already-tested WhatsApp media-handling path instead of
 * re-implementing the batch-job flow a second time in Kotlin.
 *
 * SARVAM_API_KEY (for /translate) comes from the gitignored
 * android/local.properties (see build.gradle.kts), not the repo-root .env,
 * since Android builds don't read .env.
 */
object SarvamApiClient {
    private const val BASE_URL = "https://api.sarvam.ai"

    fun isConfigured(): Boolean = BuildConfig.SARVAM_API_KEY.isNotBlank()

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .callTimeout(30, TimeUnit.SECONDS)
        .build()

    // The webhook's own batch-job fallback can legitimately take up to ~180s
    // for long audio (see _transcribe_audio_sarvam_batch's wait_until_complete
    // budget) -- the shared 30s client above would cut that off mid-request.
    private val sttClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .readTimeout(200, TimeUnit.SECONDS)
        .callTimeout(210, TimeUnit.SECONDS)
        .build()

    /** Translates [text] to English via Sarvam's /translate — the bridge
     *  before ml.detector for any non-English/Hindi OCR/STT text, since the
     *  classifier's training data doesn't cover other Indic vocabulary. */
    suspend fun translateToEnglish(text: String, sourceLanguageTag: String): String =
        withContext(Dispatchers.IO) {
            translate(text, SarvamLanguageCodes.toSarvamCode(sourceLanguageTag), "en-IN")
        }

    /** Translates English [text] back to the user's selected language, for
     *  the final spoken/displayed explanation. */
    suspend fun translateFromEnglish(text: String, targetLanguageTag: String): String =
        withContext(Dispatchers.IO) {
            translate(text, "en-IN", SarvamLanguageCodes.toSarvamCode(targetLanguageTag))
        }

    private fun translate(text: String, sourceCode: String, targetCode: String): String {
        requireConfigured()
        val body = JSONObject()
            .put("input", text)
            .put("source_language_code", sourceCode)
            .put("target_language_code", targetCode)
            .toString()
        val request = Request.Builder()
            .url("$BASE_URL/translate")
            .addHeader("api-subscription-key", BuildConfig.SARVAM_API_KEY)
            .post(body.toRequestBody("application/json".toMediaType()))
            .build()
        val json = execute(request)
        return json.optString("translated_text").ifBlank {
            throw SarvamUnavailableException("Sarvam /translate returned no translated_text")
        }
    }

    /**
     * Uploads [audioFile] to Prahari's own `/stt/sarvam` (webhook/app.py) —
     * the online fallback VoiceInputHelper/CheckCallActivity use when
     * Android's on-device SpeechRecognizer reports the language isn't
     * supported (or the device can't do on-device recognition at all).
     * That endpoint's mode=translate returns English text directly (Saaras
     * speech-to-English translation), so callers don't need a separate
     * /translate round trip, and it transparently falls back to Sarvam's
     * async batch-job API for audio over the sync endpoint's ~30s limit
     * (see _transcribe_audio_sarvam's doc comment server-side) — this app
     * doesn't need its own copy of that fallback logic.
     *
     * No language_code is sent (the server-side function doesn't accept
     * one) — real bug hit against a live device test calling Sarvam
     * directly with a forced language hint: the phone was configured for
     * one language (Punjabi) but the person spoke a different one
     * (Bengali) to test it, and Sarvam trusted the forced hint over the
     * actual audio, producing a wrong/garbled transcript. Letting Saaras
     * auto-detect avoids assuming speech always matches whatever the
     * family configured.
     *
     * [evidenceBaseUrl] is AppSettings.evidenceBaseUrl — the same
     * webhook/app.py base URL CloudOcrClient and the missed-escalation
     * evidence agent already talk to.
     */
    suspend fun transcribeAndTranslate(audioFile: File, evidenceBaseUrl: String): String =
        withContext(Dispatchers.IO) {
            val multipart = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", audioFile.name, audioFile.asRequestBody("audio/mp4".toMediaType()))
                .build()
            val request = Request.Builder()
                .url(evidenceBaseUrl.trimEnd('/') + "/stt/sarvam")
                .post(multipart)
                .build()
            val json = execute(request, sttClient)
            if (!json.optBoolean("found", false)) {
                throw SarvamUnavailableException("/stt/sarvam found no transcript")
            }
            json.optString("transcript").ifBlank {
                throw SarvamUnavailableException("/stt/sarvam returned no transcript")
            }
        }

    private fun requireConfigured() {
        if (!isConfigured()) throw SarvamUnavailableException("SARVAM_API_KEY is not configured on this build")
    }

    private fun execute(request: Request, httpClient: OkHttpClient = client): JSONObject {
        try {
            httpClient.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    throw SarvamUnavailableException(
                        "${request.url.encodedPath} returned HTTP ${response.code}: ${raw.take(500)}",
                    )
                }
                return JSONObject(raw)
            }
        } catch (e: IOException) {
            throw SarvamUnavailableException("Could not reach ${request.url}", e)
        }
    }
}
