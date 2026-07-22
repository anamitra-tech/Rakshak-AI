package com.rakshak.ai.intelligence

/**
 * Shared with [MockCallerLookupSource] so "does this number match the
 * configured trusted contact" (DecisionAgent's trusted-contact weighting)
 * and "does this number match a known-reported entry" use identical
 * normalization — last-10-digits, ignoring country-code/formatting noise.
 */
fun normalizePhoneNumber(raw: String): String =
    raw.filter { it.isDigit() }.takeLast(10).ifEmpty { raw.filter { it.isDigit() } }
