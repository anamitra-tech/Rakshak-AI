package com.rakshak.ai.intelligence

/**
 * Client for the parts of Prahari that are genuinely reachable from a bare
 * phone number screening flow — which, per CLAUDE.md Section 3, is none of
 * them; Prahari has no phone-number-reputation endpoint. This client is used
 * by the "Check a call/message" screen instead, where the user has supplied
 * actual transcript text.
 *
 * Deliberately excludes `/assistant/chat` (the LLM/RAG explanation endpoint)
 * — that is Phase 2 by explicit instruction. Only the non-LLM, classifier/
 * rule-based endpoints are called here.
 */
interface PrahariApiClient {
    /** POST /analyze_voice {transcript} on api/server.py. */
    suspend fun analyzeVoice(transcript: String): PrahariTextAnalysis

    /** POST /analyze_session {session_id, text} on api/server.py. */
    suspend fun analyzeSession(sessionId: String, text: String): PrahariSessionAnalysis

    /**
     * POST /feedback on api/server.py — logs a user's correction on a verdict
     * that was shown to them. Read/log only: this never changes any live
     * decision (see feedback/store.py). Best-effort — a failure here must
     * never surface as an error to the user, since it's not on the critical
     * path of anything.
     */
    suspend fun submitFeedback(
        channel: String,
        originalText: String,
        verdict: String,
        ruleCategories: List<String>,
        userCorrection: String,
        sessionId: String? = null,
    )
}

/** Thrown when Prahari is unreachable or returns something unexpected. */
class PrahariUnavailableException(message: String, cause: Throwable? = null) :
    Exception(message, cause)
