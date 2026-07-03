package com.rakshak.ai.ui

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityWarningBinding
import com.rakshak.ai.escalation.EscalationOrchestrator
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.RiskLevel
import java.util.Locale

/**
 * Full-screen warning card. Built to CLAUDE.md Section 9.2:
 *  - the warning is spoken (TTS), not just displayed
 *  - exactly one large action button is shown at any moment (the "Why?"
 *    disclosure below it is read-only and reveals no new actions, so it
 *    doesn't compete with that rule)
 *  - this Activity is only ever launched when risk >= MEDIUM — never for a
 *    normal, unflagged call
 *
 * Two states, one button each: WARNING ("I need help") -> HELP ("Call 1930").
 * Tapping "I need help" also fires the Tier-2 mock trusted-contact notify
 * immediately, rather than waiting out the spec's 60-90s timer — a deliberate
 * simplification for this skeleton, not a change in what the button means.
 */
class WarningActivity : AppCompatActivity() {

    private lateinit var binding: ActivityWarningBinding
    private lateinit var tts: TextToSpeech
    private lateinit var escalation: EscalationOrchestrator
    private var autoSilenced: Boolean = false
    private var ttsReady = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWarningBinding.inflate(layoutInflater)
        setContentView(binding.root)

        escalation = EscalationOrchestrator(this)
        val app = application as RakshakApp

        val riskLevel = RiskLevel.valueOf(intent.getStringExtra(EXTRA_RISK_LEVEL) ?: RiskLevel.MEDIUM.name)
        val headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty()
        val reasons = intent.getStringArrayListExtra(EXTRA_REASONS).orEmpty()
        val phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()
        autoSilenced = intent.getBooleanExtra(EXTRA_AUTO_SILENCED, false)

        renderTrafficLight(riskLevel, headline)
        renderPhoneNumber(phoneNumber)
        renderReasons(reasons)
        showWarningState()

        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) {
                tts.setLanguage(Locale.forLanguageTag(app.settings.spokenLanguageTag))
                speak(headline)
            }
        }

        binding.primaryActionButton.setOnClickListener { onPanicTapped() }
        binding.whyToggle.setOnClickListener {
            val nowVisible = binding.reasonsList.visibility != View.VISIBLE
            binding.reasonsList.visibility = if (nowVisible) View.VISIBLE else View.GONE
            binding.whyToggle.text = getString(
                if (nowVisible) R.string.why_toggle_hide else R.string.why_toggle_show
            )
        }
    }

    private fun onPanicTapped() {
        val outcome = escalation.describePanicOutcome(autoSilenced)
        escalation.notifyTrustedContact((application as RakshakApp).settings)
        showHelpState()
        speak(outcome)
        binding.helpActionButton.setOnClickListener { escalation.dialHelpline() }
    }

    private fun renderTrafficLight(riskLevel: RiskLevel, headline: String) {
        val (emoji, colorRes) = when (riskLevel) {
            RiskLevel.HIGH -> "🚨" to R.color.risk_high
            RiskLevel.MEDIUM -> "⚠️" to R.color.risk_medium
            RiskLevel.LOW -> "✅" to R.color.risk_low
        }
        binding.trafficLightEmoji.text = emoji
        binding.headlineText.text = headline
        binding.root.setBackgroundColor(getColor(colorRes))
    }

    private fun renderPhoneNumber(phoneNumber: String) {
        binding.phoneNumberText.visibility = if (phoneNumber.isBlank()) View.GONE else View.VISIBLE
        binding.phoneNumberText.text = getString(R.string.warning_from_number, phoneNumber)
    }

    private fun renderReasons(reasons: List<String>) {
        binding.reasonsList.text = reasons.joinToString(separator = "\n") { "• $it" }
        binding.reasonsList.visibility = View.GONE
        binding.whyToggle.text = getString(R.string.why_toggle_show)
        binding.whyToggle.visibility = if (reasons.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun showWarningState() {
        binding.primaryActionButton.visibility = View.VISIBLE
        binding.helpActionButton.visibility = View.GONE
        binding.statusText.visibility = View.GONE
    }

    private fun showHelpState() {
        binding.primaryActionButton.visibility = View.GONE
        binding.helpActionButton.visibility = View.VISIBLE
        binding.statusText.visibility = View.VISIBLE
        binding.statusText.text = escalation.describePanicOutcome(autoSilenced)
    }

    private fun speak(text: String) {
        if (!ttsReady || text.isBlank()) return
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "rakshak_warning")
    }

    override fun onDestroy() {
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_RISK_LEVEL = "risk_level"
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_REASONS = "reasons"
        private const val EXTRA_PHONE_NUMBER = "phone_number"
        private const val EXTRA_AUTO_SILENCED = "auto_silenced"

        fun buildIntent(
            context: Context,
            phoneNumber: String,
            decision: DecisionResult,
            autoSilenced: Boolean,
        ): Intent = Intent(context, WarningActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(EXTRA_RISK_LEVEL, decision.riskLevel.name)
            putExtra(EXTRA_HEADLINE, decision.headline)
            putStringArrayListExtra(EXTRA_REASONS, ArrayList(decision.reasons))
            putExtra(EXTRA_PHONE_NUMBER, phoneNumber)
            putExtra(EXTRA_AUTO_SILENCED, autoSilenced)
        }
    }
}
