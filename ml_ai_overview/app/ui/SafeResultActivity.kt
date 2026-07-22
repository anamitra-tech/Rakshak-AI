package com.rakshak.ai.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivitySafeResultBinding
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.tts.NativeThenEnglishSpeaker

/**
 * Calm, reassuring counterpart to WarningActivity — shown for a LOW-risk
 * (Prahari's "SAFE") verdict from the manual "Check a call/message" screen.
 * Deliberately NOT wired into RakshakCallScreeningService's pre-connect
 * flow: CLAUDE.md §9.2 requires the app stay silent and invisible during a
 * normal, unflagged call, and that constraint stays in force here — this
 * screen only exists for the user-initiated manual check, where the user
 * explicitly asked "is this safe?" and is owed a clear, calm answer, not
 * silence.
 *
 * Mirrors WarningActivity's card structure (immediate visual text, TTS
 * spoken aloud, single large action button) but green instead of
 * red/orange, and with no countdown, no escalation, and only one thing to
 * do: dismiss. Speaks via [NativeThenEnglishSpeaker] — same native-
 * language-first-then-English convention as Tier 3b's explanation, using
 * the same app-wide shared TTS instance (RakshakApp.tts) so there's no
 * per-screen engine-binding delay here either.
 */
class SafeResultActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySafeResultBinding
    private lateinit var tts: TextToSpeech
    private var ttsReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySafeResultBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty()
        val phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()

        // Text renders immediately — never gated on TTS, same rule as the
        // Tier 3b explanation card.
        binding.safeHeadlineText.text = headline
        binding.safePhoneNumberText.visibility = if (phoneNumber.isBlank()) View.GONE else View.VISIBLE
        binding.safePhoneNumberText.text = getString(R.string.warning_from_number, phoneNumber)

        binding.safeOkButton.setOnClickListener { finish() }

        val app = application as RakshakApp
        tts = app.tts
        app.onTtsReady {
            ttsReady = app.ttsReady
            if (ttsReady && headline.isNotBlank()) {
                val preferredTag = if (app.settings.hasExplicitSpokenLanguage) {
                    app.settings.spokenLanguageTag
                } else {
                    "hi-IN"
                }
                // Nothing further is gated on completion — there's no
                // countdown here, so unlike Tier 3b there's no onComplete
                // work to do beyond letting the two passes finish speaking.
                NativeThenEnglishSpeaker(tts).speak(headline, preferredTag) {}
            }
        }
    }

    override fun onDestroy() {
        // tts is app-wide now (RakshakApp) — stop() cancels this screen's own
        // pending speech, but never shutdown(): that would kill the engine
        // for the whole app, not just this Activity.
        if (::tts.isInitialized) tts.stop()
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_PHONE_NUMBER = "phone_number"

        fun buildIntent(
            context: Context,
            phoneNumber: String,
            decision: DecisionResult,
        ): Intent = Intent(context, SafeResultActivity::class.java).apply {
            putExtra(EXTRA_HEADLINE, decision.headline)
            putExtra(EXTRA_PHONE_NUMBER, phoneNumber)
        }
    }
}
