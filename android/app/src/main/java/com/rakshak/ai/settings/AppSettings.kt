package com.rakshak.ai.settings

import android.content.Context

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

    /** BCP-47 tag, e.g. "en-IN", "hi-IN" — used for the spoken warning. */
    var spokenLanguageTag: String
        get() = prefs.getString(KEY_LANGUAGE, DEFAULT_LANGUAGE) ?: DEFAULT_LANGUAGE
        set(value) = prefs.edit().putString(KEY_LANGUAGE, value).apply()

    var trustedContactName: String
        get() = prefs.getString(KEY_CONTACT_NAME, "") ?: ""
        set(value) = prefs.edit().putString(KEY_CONTACT_NAME, value).apply()

    companion object {
        private const val KEY_BASE_URL = "prahari_base_url"
        private const val KEY_LANGUAGE = "spoken_language_tag"
        private const val KEY_CONTACT_NAME = "trusted_contact_name"

        // 10.0.2.2 is the emulator's alias for the host machine's localhost.
        const val DEFAULT_BASE_URL = "http://10.0.2.2:8000"
        const val DEFAULT_LANGUAGE = "en-IN"
    }
}
