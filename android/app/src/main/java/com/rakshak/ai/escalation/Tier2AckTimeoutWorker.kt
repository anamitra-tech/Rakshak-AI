package com.rakshak.ai.escalation

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.RiskLevel

private const val TAG = "RakshakEscalation"

/**
 * Fires 2 minutes after a Tier 2 SMS is sent (scheduled by
 * [EscalationOrchestrator.notifyTrustedContact]). If [SmsSentReceiver]
 * already confirmed the carrier accepted this correlation ID, this is a
 * no-op — the missed-escalation agent only runs on a genuine miss, not on
 * every send.
 *
 * Keyed off "sent," not "delivered": many carriers never return a delivery
 * report even when the message arrives fine, which would otherwise make a
 * genuinely-successful send look like a miss on every run. The separate
 * delivery report (if/when it arrives) is still recorded by
 * [SmsDeliveryReceiver], but purely as supplementary information — it's not
 * read here.
 *
 * WorkManager (not a plain Handler.postDelayed) specifically because the
 * triggering Activity is almost certainly gone by the time 2 minutes pass;
 * this needs to survive that.
 */
class Tier2AckTimeoutWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val correlationId = inputData.getString(KEY_CORRELATION_ID) ?: return Result.failure()
        val store = EscalationDeliveryStore(applicationContext)

        if (store.wasSent(correlationId)) {
            Log.i(TAG, "Tier2 ack-timeout for $correlationId: carrier accepted the SMS in time — no evidence agent needed.")
            store.clear(correlationId)
            return Result.success()
        }

        Log.i(TAG, "Tier2 ack-timeout for $correlationId: no sent-confirmation within window — handing off to missed-escalation agent.")

        val phoneNumber = inputData.getString(KEY_PHONE_NUMBER).orEmpty()
        val transcript = inputData.getString(KEY_TRANSCRIPT)
        val riskLevel = RiskLevel.valueOf(inputData.getString(KEY_RISK_LEVEL) ?: RiskLevel.HIGH.name)
        val reasons = inputData.getStringArray(KEY_REASONS)?.toList().orEmpty()
        val decision = DecisionResult(riskLevel = riskLevel, headline = "", reasons = reasons, suspectedScamType = null)

        val app = applicationContext as RakshakApp
        MissedEscalationAgent(applicationContext).deliverEvidence(
            settings = app.settings,
            phoneNumber = phoneNumber,
            decision = decision,
            transcript = transcript,
            triggerReason = "tier2_sms_undelivered",
        )
        store.clear(correlationId)
        return Result.success()
    }

    companion object {
        const val KEY_CORRELATION_ID = "correlation_id"
        const val KEY_PHONE_NUMBER = "phone_number"
        const val KEY_TRANSCRIPT = "transcript"
        const val KEY_RISK_LEVEL = "risk_level"
        const val KEY_REASONS = "reasons"
    }
}
