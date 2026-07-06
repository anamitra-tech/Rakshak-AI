package com.rakshak.ai.intelligence

/**
 * Shared risk vocabulary across the whole app. Mirrors the thresholds Prahari
 * already uses (score >= 0.7 -> FRAUD/HIGH, >= 0.4 -> SUSPICIOUS/MEDIUM, else
 * SAFE/LOW) — see CLAUDE.md Section 1, Decision Agent row.
 */
enum class RiskLevel { LOW, MEDIUM, HIGH }

/** Result of the (mocked) CNAP + Sanchar Saathi number lookup. */
data class LookupResult(
    val tier: RiskLevel,
    val label: String,
    val reason: String,
    val suspectedScamType: String? = null,
)

/** Result of a Prahari `/analyze_voice` or `/analyze_message` call. */
data class PrahariTextAnalysis(
    val riskLevel: RiskLevel,
    val rawLabel: String,
    val score: Double,
    val reason: String,
    val signals: List<String>,
    val recommendedAction: String,
    /** Raw ml/detector.py rule category keys (e.g. "isolation_tactics") — used
     *  to gate Tier 3b precisely, not fuzzy-matched against [signals] text. */
    val ruleCategories: List<String> = emptyList(),
)

/** Result of a Prahari `/analyze_session` call. */
data class PrahariSessionAnalysis(
    val activeScamSession: Boolean,
    val severity: String,
    val triggers: List<String>,
)

/** Output of the Decision Agent: one risk level + plain-language reasons. */
data class DecisionResult(
    val riskLevel: RiskLevel,
    val headline: String,
    val reasons: List<String>,
    val suspectedScamType: String?,
    /** Propagated from the text analysis, if any — empty for the pre-connect
     *  CallScreeningService path, which has no transcript to run rules on. */
    val ruleCategories: List<String> = emptyList(),
    /** Prahari's own SAFE/SUSPICIOUS/FRAUD label when a text analysis ran;
     *  null for the lookup-only pre-connect path, which has no such label.
     *  Used for feedback logging so the recorded verdict matches server
     *  vocabulary, not just the coarser local RiskLevel. */
    val rawLabel: String? = null,
)
