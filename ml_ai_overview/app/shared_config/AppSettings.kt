package com.rakshak.ai.settings

import android.content.Context
import com.rakshak.ai.BuildConfig

/**
 * Setup is meant to be done once, by a family member, not the elderly user
 * (CLAUDE.md Section 9.2) — this is deliberately a small, flat key set rather
 * than an in-the-moment settings menu.
 */
class AppSettings(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("rakshak_settings", Context.MODE_PRIVATE)

    var prahariBaseUrl: String
        get() = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        set(value) = prefs.edit().putString(KEY_BASE_URL, value).apply()

    /**
     * webhook/app.py's port (chat/graph/evidence-delivery), separate from
     * prahariBaseUrl's api/server.py port — CLAUDE.md Section 5's "two
     * configurable base URLs", the second of which had no Android consumer
     * until the missed-escalation evidence agent's WhatsApp/email endpoints.
     */
    var evidenceBaseUrl: String
        get() = prefs.getString(KEY_EVIDENCE_BASE_URL, DEFAULT_EVIDENCE_BASE_URL) ?: DEFAULT_EVIDENCE_BASE_URL
        set(value) = prefs.edit().putString(KEY_EVIDENCE_BASE_URL, value).apply()

    /** BCP-47 tag, e.g. "en-IN", "hi-IN" — used for the spoken warning. */
    var spokenLanguageTag: String
        get() = prefs.getString(KEY_LANGUAGE, DEFAULT_LANGUAGE) ?: DEFAULT_LANGUAGE
        set(value) = prefs.edit().putString(KEY_LANGUAGE, value).apply()

    /**
     * True only if a family member has actually picked a language somewhere
     * (no UI does this yet — see MainActivity's read-only baseUrlValue for
     * the same class of gap). [spokenLanguageTag] itself can't express "never
     * set" — it silently falls back to [DEFAULT_LANGUAGE] ("en-IN") — so
     * callers that need to distinguish "the family chose English" from
     * "nobody has ever touched this" (e.g. Tier 3b's native-language-first
     * TTS pass) must check this instead of just testing the tag value.
     */
    val hasExplicitSpokenLanguage: Boolean
        get() = prefs.contains(KEY_LANGUAGE)

    var trustedContactName: String
        get() = prefs.getString(KEY_CONTACT_NAME, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CONTACT_NAME, value).apply()

    /** E.164 or local format. Empty means "no trusted contact configured". */
    var trustedContactPhone: String
        get() = prefs.getString(KEY_CONTACT_PHONE, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CONTACT_PHONE, value).apply()

    /** Email fallback destination for the missed-escalation evidence agent
     *  only — Tier 2's own SMS notification doesn't use this. */
    var trustedContactEmail: String
        get() = prefs.getString(KEY_CONTACT_EMAIL, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CONTACT_EMAIL, value).apply()

    /**
     * Tier 3b — autonomous escalation. Off by default; must be explicitly
     * opted into in a one-time family setup flow. Never triggered by the
     * base ML score alone — only near-deterministic rule fires (see
     * DecisionAgent's NEAR_DETERMINISTIC_RULE_CATEGORIES).
     */
    var tier3bEnabled: Boolean
        get() = prefs.getBoolean(KEY_TIER3B_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_TIER3B_ENABLED, value).apply()

    /**
     * The number Tier 3b auto-dials. Deliberately empty by default in debug
     * builds — Tier 3b refuses to trigger without this explicitly configured,
     * so a test build can never accidentally auto-dial the real 1930 line.
     * Release builds default to 1930 (the actual intended target once
     * reviewed).
     */
    var tier3bPhoneNumber: String
        get() = prefs.getString(KEY_TIER3B_NUMBER, DEFAULT_TIER3B_NUMBER) ?: DEFAULT_TIER3B_NUMBER
        set(value) = prefs.edit().putString(KEY_TIER3B_NUMBER, value).apply()

    /**
     * Victim-device location sharing — off by default, same opt-in posture
     * as [tier3bEnabled]. Must be explicitly turned on in family setup, and
     * FamilySetupActivity never persists this true without ACCESS_FINE_LOCATION
     * actually granted (mirrors tier3bEnabled's own permission fail-safe).
     * When true, a Tier 2/3b escalation fetches the VICTIM'S current location
     * (this device, never the caller's) and includes it in the trusted-contact
     * alert — see EscalationOrchestrator.notifyTrustedContact and
     * location/VictimLocationProvider.kt.
     */
    var locationSharingEnabled: Boolean
        get() = prefs.getBoolean(KEY_LOCATION_SHARING_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_LOCATION_SHARING_ENABLED, value).apply()

    companion object {
        private const val KEY_BASE_URL = "prahari_base_url"
        private const val KEY_EVIDENCE_BASE_URL = "evidence_base_url"
        private const val KEY_LANGUAGE = "spoken_language_tag"
        private const val KEY_CONTACT_NAME = "trusted_contact_name"
        private const val KEY_CONTACT_PHONE = "trusted_contact_phone"
        private const val KEY_CONTACT_EMAIL = "trusted_contact_email"
        private const val KEY_TIER3B_ENABLED = "tier3b_enabled"
        private const val KEY_TIER3B_NUMBER = "tier3b_phone_number"
        private const val KEY_LOCATION_SHARING_ENABLED = "location_sharing_enabled"

        // 10.0.2.2 is the emulator's alias for the host machine's localhost.
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
        const val DEFAULT_EVIDENCE_BASE_URL = "http://10.0.2.2:8001"
        const val DEFAULT_LANGUAGE = "en-IN"

        // See tier3bPhoneNumber doc — never defaults to 1930 in a debug build.
        val DEFAULT_TIER3B_NUMBER: String = if (BuildConfig.DEBUG) "" else "1930"
    }
}
