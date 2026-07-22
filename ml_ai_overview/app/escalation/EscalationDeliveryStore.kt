package com.rakshak.ai.escalation

import android.content.Context

/**
 * Tracks whether a given Tier 2 SMS (by correlation ID) was confirmed sent
 * (accepted by the carrier) and, separately, whether it was confirmed
 * delivered — plus whether a given Tier 3b call (by correlation ID) was
 * likely answered. Checked by the timeout workers/monitors before deciding
 * to hand off to the missed-escalation agent. Plain SharedPreferences: this
 * is a handful of short-lived boolean flags, not data that needs a real DB.
 *
 * "Sent" is the signal [Tier2AckTimeoutWorker] actually keys its miss-detection
 * off of — many carriers don't reliably return delivery reports at all, so
 * "delivered" is kept only as supplementary logging, not a correctness gate.
 */
class EscalationDeliveryStore(context: Context) {
    private val prefs = context.applicationContext
        .getSharedPreferences("rakshak_escalation_delivery", Context.MODE_PRIVATE)

    fun markSent(correlationId: String) {
        prefs.edit().putBoolean(sentKey(correlationId), true).apply()
    }

    fun wasSent(correlationId: String): Boolean =
        prefs.getBoolean(sentKey(correlationId), false)

    /** Supplementary only — see class doc. Not read by any miss-detection logic. */
    fun markDelivered(correlationId: String) {
        prefs.edit().putBoolean(deliveredKey(correlationId), true).apply()
    }

    fun wasDelivered(correlationId: String): Boolean =
        prefs.getBoolean(deliveredKey(correlationId), false)

    fun clear(correlationId: String) {
        prefs.edit()
            .remove(sentKey(correlationId))
            .remove(deliveredKey(correlationId))
            .apply()
    }

    private fun sentKey(correlationId: String) = "sent_$correlationId"
    private fun deliveredKey(correlationId: String) = "delivered_$correlationId"
}
