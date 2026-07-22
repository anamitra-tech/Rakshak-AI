package com.rakshak.ai.ui

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
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
import androidx.core.content.ContextCompat
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityWarningBinding
import com.rakshak.ai.escalation.ComplaintDraft
import com.rakshak.ai.escalation.EscalationOrchestrator
import com.rakshak.ai.escalation.NotifyResult
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.ExplanationTranslations
import com.rakshak.ai.intelligence.RiskLevel
import com.rakshak.ai.location.VictimLocation
import com.rakshak.ai.location.VictimLocationProvider
import com.rakshak.ai.settings.AppSettings
import com.rakshak.ai.tts.SpeechLanguageSelector
import java.util.Date

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
    private var ruleCategories: List<String> = emptyList()
    private var phoneNumber: String = ""
    private var transcript: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWarningBinding.inflate(layoutInflater)
        setContentView(binding.root)

        escalation = EscalationOrchestrator(this)
        val app = application as RakshakApp
        tts = app.tts

        applyIntentState(intent)
        playAlertTone()

        // Uses the app-wide shared TTS instance (RakshakApp.tts), constructed
        // and warmed up once at process start, instead of building a fresh
        // TextToSpeech here — that used to make the engine's several-second
        // onInit binding delay visible every time this screen opened, right
        // when the user needed to hear the warning fastest. By now, it has
        // almost always already finished initializing in the background.
        // Registered once, here — ttsReady is an instance field that
        // persists across onNewIntent (below), so a reused singleTask
        // instance doesn't need to re-register this.
        app.onTtsReady {
            ttsReady = app.ttsReady
            Log.i(TAG, "tts_init ready=$ttsReady (shared instance)")
            if (ttsReady) {
                // Language/voice is now chosen per-utterance in speak(), from
                // the actual text being spoken (SpeechLanguageSelector) —
                // no fixed setLanguage() here anymore.
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

    /**
     * WarningActivity is launchMode="singleTask" (AndroidManifest.xml) so a
     * second detection while one warning is already showing reuses this same
     * instance and re-alerts, rather than stacking warning screens. Without
     * this override, that reused instance kept displaying whatever
     * riskLevel/headline/reasons its *original* onCreate() parsed — the new
     * Intent's extras were delivered here but never read — so a stale
     * previous test's reason text (or even just a stale HELP-state button
     * layout) could show through for an unrelated new message. Real bug,
     * not a text-generation bug: every layer that computes the reason string
     * itself was already correct, this is why it never reached the screen.
     */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        applyIntentState(intent)
        playAlertTone()
        if (ttsReady) speak(headline)
    }

    private fun applyIntentState(intent: Intent) {
        riskLevel = RiskLevel.valueOf(intent.getStringExtra(EXTRA_RISK_LEVEL) ?: RiskLevel.MEDIUM.name)
        headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty()
        reasons = intent.getStringArrayListExtra(EXTRA_REASONS).orEmpty()
        ruleCategories = intent.getStringArrayListExtra(EXTRA_RULE_CATEGORIES).orEmpty()
        phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()
        transcript = intent.getStringExtra(EXTRA_TRANSCRIPT)
        autoSilenced = intent.getBooleanExtra(EXTRA_AUTO_SILENCED, false)

        renderTrafficLight(riskLevel, headline)
        renderPhoneNumber(phoneNumber)
        renderReasons(reasons)
        // Reset to the WARNING state even if the reused instance was left in
        // HELP state (primary button already tapped) by a previous, unrelated
        // detection — a fresh Intent means a fresh warning, not a continuation.
        showWarningState()
    }

    private fun onPanicTapped() {
        val outcome = escalation.describePanicOutcome(autoSilenced)
        val decision = DecisionResult(riskLevel = riskLevel, headline = headline, reasons = reasons, suspectedScamType = null)
        val settings = (application as RakshakApp).settings

        // Single-visible-button rule (CLAUDE.md 9.2) must hold the instant
        // this is tapped, not after an up-to-8s location fetch below — so
        // the HELP state is shown immediately, before location sharing
        // (if any) even starts resolving.
        binding.primaryActionButton.visibility = View.GONE
        binding.helpActionButton.visibility = View.VISIBLE
        binding.statusText.visibility = View.VISIBLE
        binding.helpActionButton.setOnClickListener { escalation.dialHelpline() }
        speak(outcome)

        val wantsLocation = settings.locationSharingEnabled &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        if (wantsLocation) {
            binding.statusText.text = "$outcome\n\n${getString(R.string.locating_status)}"
            VictimLocationProvider(this).fetchCurrentLocation { location ->
                completePanicFlow(settings, decision, outcome, location)
            }
        } else {
            binding.statusText.text = outcome
            completePanicFlow(settings, decision, outcome, null)
        }
    }

    /**
     * The actual Tier 2 send + on-screen complaint draft, run once a
     * location fix has been attempted (successfully or not) or wasn't
     * requested at all — the single place both [location]-dependent pieces
     * (the SMS and the draft) are built, so they always agree.
     */
    private fun completePanicFlow(settings: AppSettings, decision: DecisionResult, outcome: String, location: VictimLocation?) {
        val notifyResult = escalation.notifyTrustedContact(settings, phoneNumber, decision, transcript, location)
        binding.statusText.text = outcome
        renderNotifyResult(notifyResult)

        // Same ComplaintDraft text already used for the SMS/copy fallback —
        // NcrpComplaintActivity treats it as the always-available manual
        // fallback alongside its WebView-assisted autofill attempt.
        val now = Date()
        val draftText = ComplaintDraft.build(phoneNumber, decision, transcript, now, location)
        val descriptionText = buildString {
            if (reasons.isNotEmpty()) append(reasons.joinToString("; "))
            if (!transcript.isNullOrBlank()) {
                if (isNotEmpty()) append(" — ")
                append("\"$transcript\"")
            }
        }
        binding.fileComplaintButton.visibility = View.VISIBLE
        binding.fileComplaintButton.setOnClickListener {
            startActivity(
                NcrpComplaintActivity.buildIntent(
                    context = this,
                    suspectPhone = phoneNumber,
                    incidentEpochMillis = now.time,
                    description = descriptionText,
                    ruleCategories = ruleCategories,
                    draftText = draftText,
                )
            )
        }
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

    /**
     * Translates [text] into the family's configured spokenLanguageTag first
     * (via [ExplanationTranslations] — the same fixed-string lookup Tier 3b's
     * countdown screen already uses), then speaks that translation. Without
     * this, [text] here is always DecisionAgent's hardcoded English headline,
     * so ML Kit's language detection inside SpeechLanguageSelector always
     * identified it as English and spoke English regardless of what language
     * was set in Family Setup — the configured language was never actually
     * reachable for the one thing users most need spoken correctly. Falls
     * back to the raw English text (still via SpeechLanguageSelector, so a
     * mismatched-language voice on an unsupported/untranslated string doesn't
     * hard-fail) when no translation exists for this exact string+language,
     * e.g. the configured language is English, or this text isn't in
     * ExplanationTranslations' fixed set (a free-text panic-outcome string).
     */
    private fun speak(text: String) {
        if (!ttsReady || text.isBlank()) return
        Log.i(TAG, "tts_speak text_len=${text.length}")
        val app = application as RakshakApp
        val languageTag = app.settings.spokenLanguageTag
        val spokenText = ExplanationTranslations.translate(text, languageTag) ?: text
        SpeechLanguageSelector.speak(tts, spokenText, languageTag, "rakshak_warning")
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
        // tts is app-wide now (RakshakApp) — stop() cancels this screen's own
        // pending speech, but never shutdown(): that would kill the engine
        // for the whole app, not just this Activity.
        if (::tts.isInitialized) tts.stop()
        alertPlayer?.release()
        alertPlayer = null
        super.onDestroy()
    }

    companion object {
        private const val TAG = "RakshakWarning"
        private const val EXTRA_RISK_LEVEL = "risk_level"
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_REASONS = "reasons"
        private const val EXTRA_RULE_CATEGORIES = "rule_categories"
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
            putStringArrayListExtra(EXTRA_RULE_CATEGORIES, ArrayList(decision.ruleCategories))
            putExtra(EXTRA_PHONE_NUMBER, phoneNumber)
            putExtra(EXTRA_AUTO_SILENCED, autoSilenced)
            putExtra(EXTRA_TRANSCRIPT, transcript)
        }
    }
}
