package com.rakshak.ai.escalation

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import android.Manifest
import android.util.Log
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.location.VictimLocation
import com.rakshak.ai.settings.AppSettings
import java.util.UUID
import java.util.concurrent.TimeUnit

private const val TAG = "RakshakEscalation"

/** How long the missed-escalation agent waits for a Tier 2 SMS sent-confirmation
 *  before treating it as a miss and delivering evidence instead. */
private val TIER2_ACK_WINDOW_MINUTES = 2L

/** Result of a Tier 2 notify attempt — the draft is always included so the
 *  caller can show/offer it even when no real SMS was sent. */
sealed class NotifyResult {
    data class Sent(val contactName: String, val draft: String) : NotifyResult()
    data class NoContactConfigured(val draft: String) : NotifyResult()
    data class PermissionMissing(val draft: String) : NotifyResult()
    data class Failed(val draft: String, val error: String) : NotifyResult()
}

/**
 * Tiers 1-3 from the original spec (Section 5), plus Tier 2's real SMS
 * channel and the NCRP-style complaint draft (see [ComplaintDraft]). Tier 4
 * — the pre-authorized protective lock — is still out of scope; nothing here
 * implements it.
 */
class EscalationOrchestrator(private val context: Context) {

    /**
     * Tier 1. Whether the call was actually silenced/held is decided by
     * [com.rakshak.ai.callscreening.RakshakCallScreeningService] at ring-time,
     * via the Telecom `CallResponse` it hands back — that is the only point
     * in Phase 1 where this app has any real call-control power (no
     * InCallService / default-dialer status yet, so an already-answered call
     * can't be muted after the fact; that needs Phase 3/4). This function
     * just reports what already happened, for the warning card to show/speak.
     */
    fun describePanicOutcome(callWasAutoSilenced: Boolean): String = if (callWasAutoSilenced) {
        "This call was automatically silenced when it was detected as risky."
    } else {
        "This app can't yet mute a call in progress — that needs a later phase. " +
            "Please mute or hang up your phone directly if you're still on the call."
    }

    /**
     * Tier 2. Builds the NCRP-style complaint draft ([ComplaintDraft]) and
     * attaches it to the trusted-contact SMS. If no trusted-contact phone is
     * configured, or SEND_SMS isn't granted, or the send fails, the draft is
     * still returned so the caller (WarningActivity) can show it in-app with
     * a copy button instead — the draft is never silently dropped.
     *
     * [location], if provided, must already be resolved by the caller (see
     * VictimLocationProvider) — this function does not fetch it itself, so
     * it stays synchronous and callers control the fetch-then-send ordering
     * (WarningActivity waits for it before calling this; Tier 3b's
     * auto-escalation fires the call intent immediately regardless and lets
     * this run whenever the location callback resolves — see
     * AutoEscalationCountdownActivity.triggerAutoEscalation).
     */
    fun notifyTrustedContact(
        settings: AppSettings,
        phoneNumber: String,
        decision: DecisionResult,
        transcript: String?,
        location: VictimLocation? = null,
    ): NotifyResult {
        val draft = ComplaintDraft.build(phoneNumber, decision, transcript, location = location)
        val contactPhone = settings.trustedContactPhone.trim()
        val name = settings.trustedContactName.ifBlank { "your trusted contact" }

        if (contactPhone.isBlank()) {
            Log.i(TAG, "No trusted-contact phone configured — draft available in-app instead.")
            return NotifyResult.NoContactConfigured(draft)
        }

        if (ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.w(TAG, "SEND_SMS not granted — cannot notify $name. Draft available in-app instead.")
            return NotifyResult.PermissionMissing(draft)
        }

        return try {
            val smsBody = "PraHARI-AI ALERT — possible scam detected.\n\n$draft"
            val smsManager = SmsManager.getDefault()
            val parts = smsManager.divideMessage(smsBody)

            val correlationId = UUID.randomUUID().toString()
            // Explicit component, not just action+setPackage, for both receivers below:
            // neither has a manifest <intent-filter>, so an implicit broadcast can't
            // resolve to them and would silently match zero receivers — the report
            // would vanish with no error anywhere.
            val sentIntents = ArrayList(parts.indices.map { i ->
                val intent = Intent(context, SmsSentReceiver::class.java).apply {
                    action = SmsSentReceiver.ACTION_SMS_SENT
                    putExtra(SmsSentReceiver.EXTRA_CORRELATION_ID, correlationId)
                }
                PendingIntent.getBroadcast(
                    context, correlationId.hashCode() + i, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
            })
            val deliveryIntents = ArrayList(parts.indices.map { i ->
                val intent = Intent(context, SmsDeliveryReceiver::class.java).apply {
                    action = SmsDeliveryReceiver.ACTION_SMS_DELIVERED
                    putExtra(SmsDeliveryReceiver.EXTRA_CORRELATION_ID, correlationId)
                }
                PendingIntent.getBroadcast(
                    context, correlationId.hashCode() + i, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                )
            })
            smsManager.sendMultipartTextMessage(contactPhone, null, parts, sentIntents, deliveryIntents)
            Log.i(TAG, "SMS submitted to carrier for $name ($contactPhone), correlationId=$correlationId — awaiting sent-confirmation.")

            scheduleTier2AckTimeout(correlationId, phoneNumber, decision, transcript)
            NotifyResult.Sent(name, draft)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send SMS to $name: ${e.message}")
            NotifyResult.Failed(draft, e.message ?: "unknown error")
        }
    }

    /**
     * Missed-escalation evidence agent's Tier 2 trigger: schedules a check
     * [TIER2_ACK_WINDOW_MINUTES] minutes out. If [SmsSentReceiver] hasn't
     * confirmed the carrier accepted this SMS by then, [Tier2AckTimeoutWorker]
     * hands off to [MissedEscalationAgent]. Deliberately keyed off "sent," not
     * "delivered": many carriers never return a delivery report even for a
     * message that arrived fine, which would otherwise make every genuine
     * success look like a miss. This runs alongside the SMS send above, never
     * blocking or replacing it.
     */
    private fun scheduleTier2AckTimeout(
        correlationId: String,
        phoneNumber: String,
        decision: DecisionResult,
        transcript: String?,
    ) {
        val data = workDataOf(
            Tier2AckTimeoutWorker.KEY_CORRELATION_ID to correlationId,
            Tier2AckTimeoutWorker.KEY_PHONE_NUMBER to phoneNumber,
            Tier2AckTimeoutWorker.KEY_TRANSCRIPT to transcript,
            Tier2AckTimeoutWorker.KEY_RISK_LEVEL to decision.riskLevel.name,
            Tier2AckTimeoutWorker.KEY_REASONS to decision.reasons.toTypedArray(),
        )
        val request = OneTimeWorkRequestBuilder<Tier2AckTimeoutWorker>()
            .setInitialDelay(TIER2_ACK_WINDOW_MINUTES, TimeUnit.MINUTES)
            .setInputData(data)
            .build()
        WorkManager.getInstance(context).enqueue(request)
    }

    /** Tier 3. Opens the dialer pre-filled with 1930 — user still taps call. */
    fun dialHelpline() {
        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:1930")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
