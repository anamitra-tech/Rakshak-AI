package com.rakshak.ai.escalation

import android.content.Context
import android.content.Intent
import android.net.Uri
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
    // Added 2026-09-11 alongside the switch to ACTION_SENDTO (see
    // notifyTrustedContact): this is NOT a confirmed send like [Sent] used
    // to mean for the old direct SmsManager path -- it only means the SMS
    // app was successfully opened, pre-filled, with the user still needing
    // to tap Send themselves. The draft is deliberately still carried here
    // (unlike [Sent]) so the caller keeps offering the in-app copy/draft
    // fallback in case the user never completes the send.
    data class OpenedForUser(val contactName: String, val draft: String) : NotifyResult()
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
     * opens the user's SMS app pre-filled with it, addressed to the trusted
     * contact (ACTION_SENDTO — see the comment inside this function for why,
     * as of 2026-09-11, this is no longer a silent, permission-gated direct
     * send). If no trusted-contact phone is configured, no SMS app exists on
     * the device, or opening it otherwise fails, the draft is still returned
     * so the caller (WarningActivity) can show it in-app with a copy button
     * instead — the draft is never silently dropped.
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

        // Switched 2026-09-11 from a direct SmsManager.sendMultipartTextMessage()
        // call to ACTION_SENDTO, on explicit request: this needs no SEND_SMS
        // permission at all (that permission check that used to live here is
        // gone) and works identically across every Android version, at the
        // real cost of no longer being silent/automatic -- the user must
        // still tap Send themselves in whichever SMS app opens. That also
        // means there is no more carrier sent/delivery confirmation for this
        // path: the old SmsSentReceiver/SmsDeliveryReceiver/
        // scheduleTier2AckTimeout machinery below this function assumed a
        // send WE controlled, and has no signal at all once the SMS app is
        // just handed the pre-filled intent -- deliberately NOT called from
        // here anymore (see the two Receiver classes' remaining use, if any,
        // by MissedEscalationAgent's own separate direct-SmsManager fallback
        // path, which this change does not touch).
        val smsBody = "PraHARI-AI ALERT — possible scam detected.\n\n$draft"
        return try {
            val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$contactPhone")).apply {
                putExtra("sms_body", smsBody)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            if (intent.resolveActivity(context.packageManager) == null) {
                Log.w(TAG, "No SMS app found to handle ACTION_SENDTO — draft available in-app instead.")
                return NotifyResult.Failed(draft, "No SMS app available on this device")
            }
            context.startActivity(intent)
            Log.i(TAG, "SMS app opened, pre-filled, for $name ($contactPhone) — awaiting user to tap Send.")
            NotifyResult.OpenedForUser(name, draft)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open SMS app for $name: ${e.message}")
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
    // UNREACHABLE as of 2026-09-11's switch to ACTION_SENDTO above -- kept,
    // not deleted, since removing it cleanly would cascade into
    // SmsSentReceiver/SmsDeliveryReceiver/EscalationDeliveryStore/
    // Tier2AckTimeoutWorker/MissedEscalationAgent's missed-escalation
    // trigger, none of which this change was scoped to touch or verify.
    // notifyTrustedContact() no longer has any sent/delivery confirmation
    // to schedule an ack-timeout against (see that function's comment) --
    // if this whole missed-escalation-on-no-ack safety net still matters
    // now that the SMS send is a user-completed hand-off, that's a
    // separate, deliberate follow-up, not a byproduct of this change.
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
