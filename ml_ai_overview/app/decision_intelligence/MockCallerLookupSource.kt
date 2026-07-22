package com.rakshak.ai.intelligence

/**
 * Hardcoded stand-in for CNAP + Sanchar Saathi (see [CallerLookupSource]).
 * Numbers are normalized to digits-only before matching so "+91 98765..."
 * and "9876543210..." resolve the same way.
 *
 * [suspectedScamType] values match the `scam_type` vocabulary used by
 * `kb/scams.json` / `rag/retriever.py::_SCAM_AUTHORITY` in Prahari, so the
 * "Why?" panel can (in a later phase) ask the Knowledge Agent to explain that
 * exact type instead of showing static copy.
 */
class MockCallerLookupSource : CallerLookupSource {

    private data class Entry(
        val tier: RiskLevel,
        val label: String,
        val reason: String,
        val suspectedScamType: String? = null,
    )

    private val knownNumbers: Map<String, Entry> = mapOf(
        // Known-good: official bank / government helplines (Sanchar Saathi-style trusted registry)
        normalizePhoneNumber("1800111109") to Entry(
            tier = RiskLevel.LOW,
            label = "State Bank of India — official toll-free helpline",
            reason = "Verified against the trusted-contact registry.",
        ),
        normalizePhoneNumber("1930") to Entry(
            tier = RiskLevel.LOW,
            label = "National Cybercrime Helpline (1930)",
            reason = "Verified official government helpline.",
        ),

        // Known-scam: reported numbers, tagged with a suspected scam type
        normalizePhoneNumber("+911204567890") to Entry(
            tier = RiskLevel.HIGH,
            label = "Reported scam number — impersonates law enforcement",
            reason = "This number has been reported for the \"digital arrest\" scam pattern.",
            suspectedScamType = "digital_arrest",
        ),
        normalizePhoneNumber("+919876500001") to Entry(
            tier = RiskLevel.HIGH,
            label = "Reported scam number — fake bank/KYC calls",
            reason = "This number has been reported for fake bank OTP/KYC-update calls.",
            suspectedScamType = "bank_otp_kyc",
        ),
        normalizePhoneNumber("+919876500002") to Entry(
            tier = RiskLevel.MEDIUM,
            label = "Reported number — investment scheme calls",
            reason = "This number has been reported for guaranteed-return investment offers.",
            suspectedScamType = "investment_fraud",
        ),
    )

    override suspend fun lookup(phoneNumber: String): LookupResult {
        val entry = knownNumbers[normalizePhoneNumber(phoneNumber)]
            ?: return LookupResult(
                tier = RiskLevel.LOW,
                label = "Unknown number",
                reason = "No report on file for this number yet. Stay alert regardless.",
            )
        return LookupResult(
            tier = entry.tier,
            label = entry.label,
            reason = entry.reason,
            suspectedScamType = entry.suspectedScamType,
        )
    }
}
