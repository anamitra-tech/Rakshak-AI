package com.rakshak.ai.escalation

import com.rakshak.ai.intelligence.DecisionResult
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
        return lines.joinToString("\n")
    }
}
