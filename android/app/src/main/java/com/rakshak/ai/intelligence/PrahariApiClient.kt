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
}

/** Thrown when Prahari is unreachable or returns something unexpected. */
class PrahariUnavailableException(message: String, cause: Throwable? = null) :
    Exception(message, cause)
