package com.rakshak.ai.intelligence

/**
 * Stands in for CNAP (TRAI caller-name lookup) and the Sanchar Saathi trusted-
 * contact registry — see CLAUDE.md Section 2. Neither has a real API available
 * to this project; [MockCallerLookupSource] is the only implementation until
 * one exists. Swap it out here without touching any caller of this interface.
 */
fun interface CallerLookupSource {
    suspend fun lookup(phoneNumber: String): LookupResult
}
