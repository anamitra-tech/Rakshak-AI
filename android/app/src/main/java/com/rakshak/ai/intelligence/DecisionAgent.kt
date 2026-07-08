package com.rakshak.ai.intelligence

/**
 * Pure aggregation — no data source of its own, only combines outputs of the
 * lookup + Prahari calls (see CLAUDE.md Section 1, Decision Agent row). Uses
 * the same 0.7/0.4-derived risk vocabulary Prahari already uses everywhere
 * else, so "HIGH" here means the same thing "FRAUD" means server-side.
 */
object DecisionAgent {

    /**
     * Mirrors ml/detector.py's NEAR_DETERMINISTIC_RULES keys exactly — raw
     * category strings, not fuzzy-matched signal text. No longer wired into
     * Tier 3b's trigger condition (CheckCallActivity now fires on any HIGH
     * verdict, see AutoEscalationCountdownActivity's doc comment) — kept as
     * the documented cross-platform mirror of the backend's rule set in case
     * a future, more targeted gate is reintroduced. If the backend ever adds
     * a new near-deterministic rule, it must still be added here too so the
     * two stay in sync.
     */
    val NEAR_DETERMINISTIC_RULE_CATEGORIES = setOf(
        "isolation_tactics", "otp_readout_request", "card_collection_request",
    )

    fun decide(
        lookup: LookupResult,
        textAnalysis: PrahariTextAnalysis? = null,
        sessionAnalysis: PrahariSessionAnalysis? = null,
        isTrustedContact: Boolean = false,
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

        // Weighted, not bypassed: a match against the family's configured
        // trusted contact (AppSettings.trustedContactPhone — never a broader
        // contacts/call-log scan, see CLAUDE.md's no-PII-harvesting rule)
        // steps the risk down one level rather than clearing it, so a
        // spoofed/compromised trusted-contact number still surfaces a
        // warning instead of being silently waved through.
        if (isTrustedContact && level != RiskLevel.LOW) {
            reasons += "Number matches your configured trusted contact, so the risk shown here has " +
                "been lowered — it hasn't been cleared. Verify independently if anything still feels off."
            level = stepDown(level)
        }

        if (reasons.isEmpty()) reasons += defaultReason(level)

        return DecisionResult(
            riskLevel = level,
            headline = headline(level),
            reasons = reasons.distinct(),
            suspectedScamType = lookup.suspectedScamType,
            ruleCategories = textAnalysis?.ruleCategories ?: emptyList(),
            rawLabel = textAnalysis?.rawLabel,
        )
    }

    private fun stepDown(level: RiskLevel): RiskLevel = when (level) {
        RiskLevel.HIGH -> RiskLevel.MEDIUM
        RiskLevel.MEDIUM -> RiskLevel.LOW
        RiskLevel.LOW -> RiskLevel.LOW
    }

    /** True only when a near-deterministic rule actually fired — never true
     *  from tone/ML score alone, however high it scored. */
    fun hasNearDeterministicSignal(decision: DecisionResult): Boolean =
        decision.ruleCategories.any { it in NEAR_DETERMINISTIC_RULE_CATEGORIES }

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
