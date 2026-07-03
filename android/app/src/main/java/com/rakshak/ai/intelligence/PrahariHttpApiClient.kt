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
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
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
