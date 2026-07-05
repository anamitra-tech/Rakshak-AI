package com.rakshak.ai.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityWarningBinding
import com.rakshak.ai.escalation.EscalationOrchestrator
import com.rakshak.ai.escalation.NotifyResult
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
    private var alertPlayer: MediaPlayer? = null

    // Promoted from onCreate locals to instance fields so onPanicTapped()
    // (fired later, from a button tap) can build the complaint draft.
    private lateinit var riskLevel: RiskLevel
    private var headline: String = ""
    private var reasons: List<String> = emptyList()
    private var phoneNumber: String = ""
    private var transcript: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWarningBinding.inflate(layoutInflater)
        setContentView(binding.root)

        escalation = EscalationOrchestrator(this)
        val app = application as RakshakApp

        riskLevel = RiskLevel.valueOf(intent.getStringExtra(EXTRA_RISK_LEVEL) ?: RiskLevel.MEDIUM.name)
        headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty()
        reasons = intent.getStringArrayListExtra(EXTRA_REASONS).orEmpty()
        phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()
        transcript = intent.getStringExtra(EXTRA_TRANSCRIPT)
        autoSilenced = intent.getBooleanExtra(EXTRA_AUTO_SILENCED, false)

        renderTrafficLight(riskLevel, headline)
        renderPhoneNumber(phoneNumber)
        renderReasons(reasons)
        showWarningState()

        // Fires for every path that reaches this Activity — the manual
        // "check a message" flow (CheckCallActivity) and the automatic
        // CallScreeningService flow both funnel through here, so a single
        // call site covers both. Must not depend on reading/seeing anything
        // (CLAUDE.md 9.2 — elderly/illiterate-first), so this plays on
        // STREAM_ALARM (via AudioAttributes.USAGE_ALARM) specifically so it
        // is audible even with the phone on silent/vibrate, same as the TTS
        // speech below.
        playAlertTone()

        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            Log.i(TAG, "tts_init status=$status ready=$ttsReady")
            if (ttsReady) {
                tts.setLanguage(Locale.forLanguageTag(app.settings.spokenLanguageTag))
                tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {
                        Log.i(TAG, "tts_utterance_start id=$utteranceId")
                    }
                    override fun onDone(utteranceId: String?) {
                        Log.i(TAG, "tts_utterance_done id=$utteranceId")
                    }
                    @Deprecated("Deprecated in Java")
                    override fun onError(utteranceId: String?) {
                        Log.e(TAG, "tts_utterance_error id=$utteranceId")
                    }
                })
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
        val decision = DecisionResult(riskLevel = riskLevel, headline = headline, reasons = reasons, suspectedScamType = null)
        val notifyResult = escalation.notifyTrustedContact(
            (application as RakshakApp).settings, phoneNumber, decision, transcript,
        )
        showHelpState(notifyResult)
        speak(outcome)
        binding.helpActionButton.setOnClickListener { escalation.dialHelpline() }
    }

    /** Only surfaced when Tier 2 did NOT actually reach the trusted contact —
     *  see Part 1 point 2: draft-in-app is the fallback, not a duplicate. */
    private fun renderNotifyResult(result: NotifyResult) {
        val (statusText, draft) = when (result) {
            is NotifyResult.Sent -> getString(R.string.notify_status_sent, result.contactName) to null
            is NotifyResult.NoContactConfigured -> getString(R.string.notify_status_no_contact) to result.draft
            is NotifyResult.PermissionMissing -> getString(R.string.notify_status_permission_missing) to result.draft
            is NotifyResult.Failed -> getString(R.string.notify_status_failed) to result.draft
        }
        binding.statusText.text = "${binding.statusText.text}\n\n$statusText"

        if (draft == null) {
            binding.draftToggle.visibility = View.GONE
            binding.draftText.visibility = View.GONE
            binding.copyDraftButton.visibility = View.GONE
            return
        }

        binding.draftToggle.visibility = View.VISIBLE
        binding.draftText.text = draft
        binding.draftToggle.setOnClickListener {
            val nowVisible = binding.draftText.visibility != View.VISIBLE
            binding.draftText.visibility = if (nowVisible) View.VISIBLE else View.GONE
            binding.copyDraftButton.visibility = if (nowVisible) View.VISIBLE else View.GONE
            binding.draftToggle.text = getString(
                if (nowVisible) R.string.complaint_draft_toggle_hide else R.string.complaint_draft_toggle_show
            )
        }
        binding.copyDraftButton.setOnClickListener {
            val clipboard = getSystemService(ClipboardManager::class.java)
            clipboard.setPrimaryClip(ClipData.newPlainText("NCRP complaint draft", draft))
            Toast.makeText(this, R.string.complaint_draft_copied_toast, Toast.LENGTH_SHORT).show()
        }
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

    private fun showHelpState(notifyResult: NotifyResult) {
        binding.primaryActionButton.visibility = View.GONE
        binding.helpActionButton.visibility = View.VISIBLE
        binding.statusText.visibility = View.VISIBLE
        binding.statusText.text = escalation.describePanicOutcome(autoSilenced)
        renderNotifyResult(notifyResult)
    }

    private fun speak(text: String) {
        if (!ttsReady || text.isBlank()) return
        Log.i(TAG, "tts_speak text_len=${text.length}")
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "rakshak_warning")
    }

    /**
     * Two-tone chime on the ALARM stream — audible even on silent/vibrate,
     * same rationale as the TTS speech: this can't depend on the user
     * reading or looking at the screen. Deliberately NOT NOTIFICATION or
     * MEDIA stream (those respect silent/DND; ALARM is the one category
     * that's meant to interrupt regardless, same as a phone's own alarm
     * clock or emergency alert).
     */
    private fun playAlertTone() {
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_ALARM)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        alertPlayer = MediaPlayer.create(
            this,
            R.raw.alert_chime,
            attrs,
            AudioManager.AUDIO_SESSION_ID_GENERATE,
        )
        if (alertPlayer == null) {
            Log.e(TAG, "alert_tone_create_failed")
            return
        }
        alertPlayer?.setOnCompletionListener {
            Log.i(TAG, "alert_tone_completed stream=ALARM")
            it.release()
            alertPlayer = null
        }
        Log.i(TAG, "alert_tone_start stream=ALARM usage=USAGE_ALARM")
        alertPlayer?.start()
    }

    override fun onDestroy() {
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        alertPlayer?.release()
        alertPlayer = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "RakshakWarning"
        private const val EXTRA_RISK_LEVEL = "risk_level"
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_REASONS = "reasons"
        private const val EXTRA_PHONE_NUMBER = "phone_number"
        private const val EXTRA_AUTO_SILENCED = "auto_silenced"
        private const val EXTRA_TRANSCRIPT = "transcript"

        fun buildIntent(
            context: Context,
            phoneNumber: String,
            decision: DecisionResult,
            autoSilenced: Boolean,
            transcript: String? = null,
        ): Intent = Intent(context, WarningActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(EXTRA_RISK_LEVEL, decision.riskLevel.name)
            putExtra(EXTRA_HEADLINE, decision.headline)
            putStringArrayListExtra(EXTRA_REASONS, ArrayList(decision.reasons))
            putExtra(EXTRA_PHONE_NUMBER, phoneNumber)
            putExtra(EXTRA_AUTO_SILENCED, autoSilenced)
            putExtra(EXTRA_TRANSCRIPT, transcript)
        }
    }
}
