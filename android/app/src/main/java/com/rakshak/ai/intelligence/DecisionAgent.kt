package com.rakshak.ai.intelligence

/**
 * Pure aggregation — no data source of its own, only combines outputs of the
 * lookup + Prahari calls (see CLAUDE.md Section 1, Decision Agent row). Uses
 * the same 0.7/0.4-derived risk vocabulary Prahari already uses everywhere
 * else, so "HIGH" here means the same thing "FRAUD" means server-side.
 */
object DecisionAgent {

    fun decide(
        lookup: LookupResult,
        textAnalysis: PrahariTextAnalysis? = null,
        sessionAnalysis: PrahariSessionAnalysis? = null,
    ): DecisionResult {
        var level = lookup.tier
        val reasons = mutableListOf<String>()
        if (lookup.tier != RiskLevel.LOW) reasons += lookup.reason

        textAnalysis?.let { ta ->
            level = maxOf(level, ta.riskLevel)
            if (ta.signals.isNotEmpty()) {
                reasons += ta.signals
            } else if (ta.riskLevel != RiskLevel.LOW) {
                reasons += ta.reason
            }
        }

        sessionAnalysis?.let { sa ->
            if (sa.activeScamSession) {
                reasons += sa.triggers
                if (sa.severity == "HIGH" || sa.severity == "CRITICAL") {
                    level = RiskLevel.HIGH
                }
            }
        }

        if (reasons.isEmpty()) reasons += defaultReason(level)

        return DecisionResult(
            riskLevel = level,
            headline = headline(level),
            reasons = reasons.distinct(),
            suspectedScamType = lookup.suspectedScamType,
        )
    }

    private fun headline(level: RiskLevel): String = when (level) {
        RiskLevel.HIGH -> "This looks like a scam. Do not share any code or send money."
        RiskLevel.MEDIUM -> "This could be risky. Be careful and verify before doing anything."
        RiskLevel.LOW -> "This looks safe. Stay alert anyway."
    }

    private fun defaultReason(level: RiskLevel): String = when (level) {
        RiskLevel.HIGH -> "Multiple risk signals were detected."
        RiskLevel.MEDIUM -> "Some risk signals were detected. Verify before proceeding."
        RiskLevel.LOW -> "No risk signals were detected."
    }
}
