package com.rakshak.ai.escalation

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

private const val TAG = "RakshakEscalation"

/**
 * Records whether the Tier 2 trusted-contact SMS was actually delivered to
 * the recipient's device — supplementary information only. [Tier2AckTimeoutWorker]
 * does NOT key its miss-detection off this: many carriers (notably several
 * Indian ones) never return a delivery report at all even when the message
 * arrives fine, so treating its absence as a miss would misfire on every
 * genuinely-successful send. See [SmsSentReceiver] for the signal actually
 * used for that decision.
 *
 * Delivery != acknowledged/read — this is the honest, low-permission signal
 * actually available (SmsManager's delivery report), not a claim that the
 * contact saw or understood the message.
 */
class SmsDeliveryReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val correlationId = intent.getStringExtra(EXTRA_CORRELATION_ID) ?: return
        val delivered = resultCode == Activity.RESULT_OK
        Log.i(TAG, "SMS delivery report for $correlationId: delivered=$delivered (resultCode=$resultCode)")
        if (delivered) {
            EscalationDeliveryStore(context).markDelivered(correlationId)
        }
    }

    companion object {
        const val ACTION_SMS_DELIVERED = "com.rakshak.ai.action.SMS_DELIVERED"
        const val EXTRA_CORRELATION_ID = "correlation_id"
    }
}
