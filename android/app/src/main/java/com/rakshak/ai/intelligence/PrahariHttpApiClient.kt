package com.rakshak.ai.intelligence

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Talks to Prahari's `api/server.py` (Modules 1/2/5/6/7). Base URL points at
 * whatever host is running `python -m api.server 8000` — `10.0.2.2` reaches
 * the dev machine from the emulator by default (see CLAUDE.md Section 5).
 */
class PrahariHttpApiClient(
    private val baseUrl: String,
    // Tightened from connectTimeout=5s/readTimeout=8s/writeTimeout=10s
    // (OkHttp's unset default) with no overall cap — that combination let a
    // single call wait upwards of 13s (worst case ~5s+10s if the stalling
    // phase happened to be write, not just connect+read) with a static
    // "Checking with Prahari…" spinner and no cancel option, before this
    // was ever tested against anything but instant-refusal (server fully
    // down). callTimeout() is the real fix here — it caps the ENTIRE call
    // (connect+write+read combined) regardless of which phase stalls, so a
    // rural/patchy connection gets a bounded ~5s fallback instead of a
    // best-case-per-phase sum that could still run well past it.
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .writeTimeout(3, TimeUnit.SECONDS)
        .readTimeout(4, TimeUnit.SECONDS)
        .callTimeout(5, TimeUnit.SECONDS)
        .build(),
) : PrahariApiClient {

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    override suspend fun analyzeVoice(transcript: String): PrahariTextAnalysis =
        withContext(Dispatchers.IO) {
            val body = JSONObject().put("transcript", transcript).toString()
            val json = post("/analyze_voice", body)
            PrahariTextAnalysis(
                riskLevel = mapRiskLevel(json.optString("risk_level")),
                rawLabel = json.optString("risk_level"),
                score = json.optDouble("score", 0.0),
                reason = json.optString("reason"),
                signals = json.optJSONArray("signals").toStringList(),
                recommendedAction = json.optString("recommended_action"),
                ruleCategories = json.optJSONArray("rule_categories").toStringList(),
            )
        }

    override suspend fun analyzeSession(sessionId: String, text: String): PrahariSessionAnalysis =
        withContext(Dispatchers.IO) {
            val body = JSONObject()
                .put("session_id", sessionId)
                .put("text", text)
                .toString()
            val json = post("/analyze_session", body)
            PrahariSessionAnalysis(
                activeScamSession = json.optString("active_scam_session") == "YES",
                severity = json.optString("severity", "NONE"),
                triggers = json.optJSONArray("session_triggers").toStringList(),
            )
        }

    override suspend fun submitFeedback(
        channel: String,
        originalText: String,
        verdict: String,
        ruleCategories: List<String>,
        userCorrection: String,
        sessionId: String?,
    ) {
        withContext(Dispatchers.IO) {
            try {
                val body = JSONObject()
                    .put("channel", channel)
                    .put("original_text", originalText)
                    .put("verdict", verdict)
                    .put("rule_categories", org.json.JSONArray(ruleCategories))
                    .put("user_correction", userCorrection)
                    .apply { sessionId?.let { put("session_id", it) } }
                    .toString()
                post("/feedback", body)
            } catch (e: PrahariUnavailableException) {
                // Best-effort, log-only path — never let this surface as an
                // error in the UI (see interface doc).
            }
        }
    }

    private fun post(path: String, jsonBody: String): JSONObject {
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + path)
            .post(jsonBody.toRequestBody(jsonMediaType))
            .build()
        try {
            client.newCall(request).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    throw PrahariUnavailableException("Prahari $path returned HTTP ${response.code}: $raw")
                }
                return JSONObject(raw)
            }
        } catch (e: IOException) {
            throw PrahariUnavailableException("Could not reach Prahari at $baseUrl$path", e)
        }
    }

    private fun mapRiskLevel(raw: String): RiskLevel = when (raw.uppercase()) {
        "FRAUD" -> RiskLevel.HIGH
        "SUSPICIOUS" -> RiskLevel.MEDIUM
        "SAFE", "REAL" -> RiskLevel.LOW
        else -> RiskLevel.LOW
    }

    private fun org.json.JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return (0 until length()).map { getString(it) }
    }
}
