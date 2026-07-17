package com.rakshak.ai.escalation

import android.app.Activity
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.telephony.SmsManager
import android.util.Base64
import android.util.Log
import androidx.core.content.ContextCompat
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.settings.AppSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume

private const val TAG = "RakshakEscalation"

/**
 * Missed-escalation evidence agent — separate from the fixed Tier 1-4
 * sequence, runs alongside it (never blocking or replacing Tier 2/3b).
 * Triggered by [Tier2AckTimeoutWorker] (SMS not confirmed delivered) or
 * [Tier3bCallOutcomeWorker] (call likely not answered).
 *
 * Compiles the same structured facts as [ComplaintDraft] into a short PDF
 * ([EvidenceCardRenderer]), then tries WhatsApp -> SMS -> email in order,
 * checking the real success/failure of each before moving to the next —
 * not firing all three blindly.
 */
class MissedEscalationAgent(private val context: Context) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    suspend fun deliverEvidence(
        settings: AppSettings,
        phoneNumber: String,
        decision: DecisionResult,
        transcript: String?,
        triggerReason: String,
    ) = withContext(Dispatchers.IO) {
        Log.i(TAG, "Missed-escalation evidence agent triggered: reason=$triggerReason")

        val draftText = ComplaintDraft.build(phoneNumber, decision, transcript)
        val pdfBase64 = try {
            val pdfBytes = EvidenceCardRenderer.renderPdf("PraHARI-AI — EVIDENCE CARD", draftText)
            Base64.encodeToString(pdfBytes, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.e(TAG, "Evidence PDF rendering failed: ${e.message}")
            null
        }

        val contactPhone = settings.trustedContactPhone.trim()
        val contactEmail = settings.trustedContactEmail.trim()

        if (contactPhone.isBlank() && contactEmail.isBlank()) {
            Log.w(TAG, "Missed-escalation evidence agent: no trusted contact phone or email configured — nothing to deliver to.")
            return@withContext
        }

        if (contactPhone.isNotBlank() && pdfBase64 != null && tryWhatsApp(settings, contactPhone, pdfBase64)) {
            Log.i(TAG, "Missed-escalation evidence delivered via WhatsApp to $contactPhone.")
            return@withContext
        }

        if (contactPhone.isNotBlank() && trySms(contactPhone, draftText)) {
            Log.i(TAG, "Missed-escalation evidence delivered via SMS (condensed) to $contactPhone.")
            return@withContext
        }

        if (contactEmail.isNotBlank() && pdfBase64 != null && tryEmail(settings, contactEmail, draftText, pdfBase64)) {
            Log.i(TAG, "Missed-escalation evidence delivered via email to $contactEmail.")
            return@withContext
        }

        Log.e(TAG, "Missed-escalation evidence agent: ALL channels failed or were unavailable (WhatsApp, SMS, email).")
    }

    private fun tryWhatsApp(settings: AppSettings, phone: String, pdfBase64: String): Boolean {
        return try {
            val json = JSONObject().apply {
                put("phone_number", phone)
                put("pdf_base64", pdfBase64)
                put("caption", "PraHARI-AI — missed escalation evidence. See attached.")
            }
            val body = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url(settings.evidenceBaseUrl.trimEnd('/') + "/evidence/whatsapp")
                .post(body)
                .build()
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "WhatsApp evidence delivery HTTP failure: ${resp.code}")
                    return false
                }
                val result = JSONObject(resp.body?.string().orEmpty())
                val success = result.optBoolean("success", false)
                if (!success) {
                    Log.w(TAG, "WhatsApp evidence delivery reported failure: ${result.optString("error")} status=${result.optString("status")}")
                }
                success
            }
        } catch (e: Exception) {
            Log.w(TAG, "WhatsApp evidence delivery threw: ${e.message}")
            false
        }
    }

    /**
     * Unlike Tier 2's own SMS (which schedules a separate 2-minute-later
     * WorkManager check), this leg needs its success/failure known *within*
     * this same decision loop before deciding whether to fall through to
     * email — so it waits directly on the delivery report, with a bounded
     * timeout, rather than just checking that the send call didn't throw.
     */
    private suspend fun trySms(phone: String, draftText: String): Boolean {
        val condensed = "PraHARI-AI EVIDENCE (you may have missed an earlier alert):\n" + condense(draftText)
        return try {
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(condensed)
            val correlationId = UUID.randomUUID().toString()
            val action = "com.rakshak.ai.action.EVIDENCE_SMS_DELIVERED.$correlationId"

            withTimeoutOrNull(SMS_DELIVERY_TIMEOUT_MS) {
                suspendCancellableCoroutine { cont ->
                    val receiver = object : BroadcastReceiver() {
                        override fun onReceive(ctx: Context, intent: Intent) {
                            val delivered = resultCode == Activity.RESULT_OK
                            try {
                                context.unregisterReceiver(this)
                            } catch (_: IllegalArgumentException) {
                                // Already unregistered (e.g. timeout raced this callback) — fine.
                            }
                            if (cont.isActive) cont.resume(delivered)
                        }
                    }
                    ContextCompat.registerReceiver(
                        context, receiver, IntentFilter(action),
                        ContextCompat.RECEIVER_NOT_EXPORTED,
                    )
                    cont.invokeOnCancellation {
                        try {
                            context.unregisterReceiver(receiver)
                        } catch (_: IllegalArgumentException) {
                        }
                    }

                    val deliveryIntents = ArrayList(parts.indices.map { i ->
                        val intent = Intent(action).setPackage(context.packageName)
                        PendingIntent.getBroadcast(
                            context, correlationId.hashCode() + i, intent,
                            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                        )
                    })
                    smsManager.sendMultipartTextMessage(phone, null, parts, null, deliveryIntents)
                }
            } ?: run {
                Log.w(TAG, "SMS evidence delivery: no delivery confirmation within ${SMS_DELIVERY_TIMEOUT_MS}ms.")
                false
            }
        } catch (e: Exception) {
            Log.w(TAG, "SMS evidence delivery threw: ${e.message}")
            false
        }
    }

    private fun tryEmail(settings: AppSettings, email: String, draftText: String, pdfBase64: String): Boolean {
        return try {
            val json = JSONObject().apply {
                put("to_email", email)
                put("subject", "PraHARI-AI — missed escalation evidence")
                put("text_summary", draftText)
                put("pdf_base64", pdfBase64)
                put("pdf_filename", "PraHARI-AI_evidence.pdf")
            }
            val body = json.toString().toRequestBody("application/json".toMediaType())
            val request = Request.Builder()
                .url(settings.evidenceBaseUrl.trimEnd('/') + "/evidence/email")
                .post(body)
                .build()
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "Email evidence delivery HTTP failure: ${resp.code}")
                    return false
                }
                val result = JSONObject(resp.body?.string().orEmpty())
                val success = result.optBoolean("success", false)
                if (!success) {
                    Log.w(TAG, "Email evidence delivery reported failure: ${result.optString("error")}")
                }
                success
            }
        } catch (e: Exception) {
            Log.w(TAG, "Email evidence delivery threw: ${e.message}")
            false
        }
    }

    private fun condense(draftText: String, maxLen: Int = 600): String =
        if (draftText.length <= maxLen) draftText else draftText.take(maxLen) + "…"

    companion object {
        private const val SMS_DELIVERY_TIMEOUT_MS = 15_000L
    }
}
