package com.rakshak.ai.escalation

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

private const val TAG = "RakshakEscalation"

/**
 * Records whether the Tier 2 trusted-contact SMS was accepted by the carrier
 * and left the device — this, not the separate delivery report, is what
 * [Tier2AckTimeoutWorker] keys its 2-minute miss-detection off. Many Indian
 * carriers don't reliably return delivery reports at all even when a message
 * arrives fine, which would otherwise make a genuinely-successful send look
 * like a miss and needlessly trigger the missed-escalation evidence agent.
 * "Sent" (message handed off to the carrier) is the honest, carrier-independent
 * signal actually available here.
 */
class SmsSentReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val correlationId = intent.getStringExtra(EXTRA_CORRELATION_ID) ?: return
        val sent = resultCode == Activity.RESULT_OK
        Log.i(TAG, "SMS sent-report for $correlationId: sent=$sent (resultCode=$resultCode)")
        if (sent) {
            EscalationDeliveryStore(context).markSent(correlationId)
        }
    }

    companion object {
        const val ACTION_SMS_SENT = "com.rakshak.ai.action.SMS_SENT"
        const val EXTRA_CORRELATION_ID = "correlation_id"
    }
}
