package com.rakshak.ai.escalation

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import com.rakshak.ai.settings.AppSettings

private const val TAG = "RakshakEscalation"

/**
 * Tiers 1-3 from the original spec (Section 5). Tier 4 — the pre-authorized
 * protective lock — is out of scope for every phase until it exists as an
 * explicit, calm, advance opt-in flow; nothing here implements it.
 *
 * Only [dialHelpline] performs a real action. The other two are honest stubs:
 * see each function's doc for exactly why.
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
     * Tier 2. Real implementation needs a trusted-contact list and a message
     * channel (SMS/push) — neither exists yet, and CLAUDE.md Section 9.2
     * says that setup must be a deliberate, calm, family-member-run flow, not
     * built in a rush. For now this only logs + returns a status string so
     * the flow is visibly wired up end-to-end.
     */
    fun notifyTrustedContact(settings: AppSettings): String {
        val name = settings.trustedContactName.ifBlank { "your trusted contact" }
        Log.i(TAG, "[MOCK] Would notify $name now. No real message was sent.")
        return "$name would be notified now (not yet wired to a real message)."
    }

    /** Tier 3. Opens the dialer pre-filled with 1930 — user still taps call. */
    fun dialHelpline() {
        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:1930")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }
}
