package com.rakshak.ai.escalation

import android.content.Context

/**
 * Tracks whether a given Tier 2 SMS (by correlation ID) was confirmed
 * delivered, and whether a given Tier 3b call (by correlation ID) was likely
 * answered — checked by the timeout workers/monitors before deciding to hand
 * off to the missed-escalation agent. Plain SharedPreferences: this is a
 * handful of short-lived boolean flags, not data that needs a real DB.
 */
class EscalationDeliveryStore(context: Context) {
    private val prefs = context.applicationContext
        .getSharedPreferences("rakshak_escalation_delivery", Context.MODE_PRIVATE)

    fun markDelivered(correlationId: String) {
        prefs.edit().putBoolean(key(correlationId), true).apply()
    }

    fun wasDelivered(correlationId: String): Boolean =
        prefs.getBoolean(key(correlationId), false)

    fun clear(correlationId: String) {
        prefs.edit().remove(key(correlationId)).apply()
    }

    private fun key(correlationId: String) = "delivered_$correlationId"
}
