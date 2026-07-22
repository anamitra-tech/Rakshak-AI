package com.rakshak.ai.escalation

import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.location.VictimLocation
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * NCRP (National Cybercrime Reporting Portal)-style complaint draft. This is
 * always a DRAFT for a human to review — it is never submitted anywhere by
 * this app. It's either attached to the Tier 2 trusted-contact SMS, or shown
 * in-app with a copy button when no trusted contact is configured.
 */
object ComplaintDraft {

    fun build(
        phoneNumber: String,
        decision: DecisionResult,
        transcript: String?,
        timestamp: Date = Date(),
        /**
         * The VICTIM'S OWN current location (this device), only ever
         * non-null when the family opted into location sharing in setup
         * AND a fix was actually obtained in time — see
         * VictimLocationProvider. Never the caller/scammer's location;
         * nothing in this app has any way to learn that. Absent by default
         * (existing callers, e.g. MissedEscalationAgent's delayed
         * fallback delivery, are unaffected and simply omit this section).
         */
        location: VictimLocation? = null,
    ): String {
        val df = SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault())
        val lines = mutableListOf<String>()
        lines += "DRAFT complaint — review before submitting to cybercrime.gov.in or calling 1930."
        lines += "(Generated automatically. Please check every detail before sending.)"
        lines += ""
        lines += "Date/time: ${df.format(timestamp)}"
        lines += "Suspect number: ${phoneNumber.ifBlank { "Not available" }}"
        lines += "Risk level: ${decision.riskLevel}"
        lines += ""
        lines += "Reason(s) flagged:"
        if (decision.reasons.isEmpty()) {
            lines += "- (none recorded)"
        } else {
            decision.reasons.forEach { lines += "- $it" }
        }
        lines += ""
        if (!transcript.isNullOrBlank()) {
            lines += "What was said/received:"
            lines += "\"$transcript\""
        } else {
            lines += "What was said/received: not recorded (this app does not capture live call audio)."
        }
        if (location != null) {
            lines += ""
            // Labelled explicitly on every line, not just once at the top —
            // this text is meant to survive being read out of context (SMS
            // preview, a screenshot, a forwarded message).
            lines += "Location of the person who received this call/message (their own phone, NOT the suspect's number):"
            lines += "GPS: ${location.latitude}, ${location.longitude}"
            lines += if (location.humanReadableAddress != null) {
                "Approximate address: ${location.humanReadableAddress}"
            } else {
                "(No address could be resolved for these coordinates — open the GPS coordinates above in a maps app.)"
            }
        }
        return lines.joinToString("\n")
    }
}
