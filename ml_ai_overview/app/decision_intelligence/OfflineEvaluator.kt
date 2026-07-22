package com.rakshak.ai.intelligence

import kotlin.math.roundToInt

/**
 * Combines OfflineRuleEngine's three near-deterministic rule categories with
 * MlScamScorer's ported ML score, using the same fusion formula as
 * ml.detector.ScamDetector.predict() -- restricted to what's actually visible
 * offline. This closes the structural gap where a Prahari-unreachable check
 * previously returned nothing at all for text that would have scored
 * SUSPICIOUS/FRAUD online purely on the ML signal (no rule pattern), e.g.
 * "send the 3 digit verification code" before its rule fix existed, or any
 * future phrasing that only the trained model -- not a regex -- catches.
 *
 * Deliberately simplified versus the full predict(): predict() also folds in
 * seven other rule categories (money_demand, authority_impersonation,
 * relative_impersonation, telecom_impersonation, extortion_threat,
 * credential_request, urgency_coercion) and their critical-combo boosts
 * (e.g. authority_impersonation + credential_request -> 0.95). None of those
 * are ported to Kotlin -- OfflineRuleEngine only ever covers the three
 * near-deterministic-alone categories, by design (see its own doc comment).
 * Since all three of those are near-deterministic (any single match already
 * forces score >= 0.95 via predict()'s NEAR_DETERMINISTIC_RULES override,
 * independent of rule_categories count), the intermediate "rule_categories
 * >= 2 -> 0.85, == 1 -> 0.55" boosting step in predict() can never be the
 * deciding factor for these three specifically -- so collapsing it to
 * "any match -> >= 0.95" here is an exact fusion match for the categories
 * offline can see, not an approximation.
 */
object OfflineEvaluator {

    data class Evaluation(
        val riskLevel: RiskLevel,
        val score: Double,
        val reason: String,
        val signals: List<String>,
        val ruleCategories: List<String>,
    )

    private const val FRAUD_THRESHOLD = 0.7
    private const val SUSPICIOUS_THRESHOLD = 0.5 // mirrors ml/detector.py's SUSPICIOUS_THRESHOLD

    /**
     * [mlModel] is nullable so a failed/missing asset load degrades to
     * rules-only behavior (the pre-existing offline fallback) rather than
     * crashing -- same "never appear to hang or crash on a failed
     * dependency" posture as the online Prahari-unreachable handling.
     */
    fun evaluate(text: String, mlModel: MlScamScorer.Model?): Evaluation {
        val ruleMatch = OfflineRuleEngine.check(text)
        val mlFraud = if (mlModel != null) MlScamScorer.scoreFraudProbability(mlModel, text) else 0.0

        var score = mlFraud
        if (ruleMatch != null) {
            score = maxOf(score, 0.95)
        }
        score = minOf(1.0, score)

        val level = when {
            score >= FRAUD_THRESHOLD -> RiskLevel.HIGH
            score >= SUSPICIOUS_THRESHOLD -> RiskLevel.MEDIUM
            else -> RiskLevel.LOW
        }

        if (ruleMatch != null) {
            return Evaluation(
                riskLevel = level,
                score = score,
                reason = ruleMatch.explanation,
                signals = listOf(ruleMatch.signalLabel),
                ruleCategories = listOf(ruleMatch.category),
            )
        }

        // No rule matched -- mirrors ScamDetector.build_reason()'s `not rules` branch exactly.
        val reason = if (level == RiskLevel.LOW) {
            "No fraud patterns detected; language consistent with legitimate messaging."
        } else {
            "Language model flags risk (fraud likelihood ${(mlFraud * 100).roundToInt()}%) " +
                "though no explicit rule pattern matched."
        }
        return Evaluation(
            riskLevel = level,
            score = score,
            reason = reason,
            signals = emptyList(),
            ruleCategories = emptyList(),
        )
    }
}
