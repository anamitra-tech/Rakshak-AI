package com.rakshak.ai.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.CountDownTimer
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityAutoEscalationCountdownBinding
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import com.rakshak.ai.escalation.EscalationOrchestrator
import com.rakshak.ai.escalation.Tier3bCallOutcomeWorker
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.ExplanationTranslations
import com.rakshak.ai.intelligence.RiskLevel
import com.rakshak.ai.location.VictimLocationProvider
import java.util.Locale

private const val TAG = "RakshakTier3b"
private const val COUNTDOWN_SECONDS = 10

/** Utterance IDs for the pre-countdown explanation pass(es) — distinct from
 *  "rakshak_tier3b" (per-second ticks) and "tier3b_calling_message" (spoken
 *  after auto-dial), neither of which should trigger the chaining below. */
private const val UTTERANCE_EXPLANATION_NATIVE = "tier3b_explanation_native"
private const val UTTERANCE_EXPLANATION_ENGLISH = "tier3b_explanation_english"

/**
 * Safety net for requirement 4: if TTS never finishes (engine failure, an
 * unexpectedly long/looping utterance, a device with no usable voice at
 * all), the countdown must still eventually start — a broken TTS engine
 * must never silently block escalation from ever happening. Widened from
 * 22s to 40s after a real cold-start run measured ~17s just for TextToSpeech
 * to bind + load the Hindi voice pack, before either explanation pass had
 * even started speaking — 22s left too little runway for both passes to
 * finish and was observed cutting the English pass off mid-sentence.
 */
private const val EXPLANATION_SAFETY_TIMEOUT_MS = 40_000L

/**
 * Tier 3b — autonomous escalation. Launched for any HIGH-risk verdict from
 * the manual "Check a call/message" screen (CheckCallActivity is the only
 * place that can launch this — the pre-connect CallScreeningService flow has
 * no transcript, so it never reaches a HIGH verdict from text analysis at
 * all). Deliberately **not** gated behind AppSettings.tier3bEnabled or
 * DecisionAgent.hasNearDeterministicSignal — a product decision to trigger
 * on any HIGH verdict, including the base ML score alone, accepting the
 * known false-positive risk documented against the base classifier (see
 * CLAUDE.md §6, head.md). [triggerAutoEscalation] still falls back to the
 * plain warning card if no number is configured or CALL_PHONE was never
 * granted — that safety net is unchanged, it just no longer decides whether
 * this screen is shown in the first place.
 *
 * No reading required to understand what's happening — [ShrinkingCircleView]
 * plus a spoken countdown carry the same information the on-screen text
 * does. Exactly one button (Cancel). If not cancelled: auto-dials the
 * configured number (ACTION_CALL — a real permission, only requested during
 * family setup) and, at the same time, fires the existing Tier 2 trusted-
 * contact alert. No in-call audio injection or TTS into the call itself —
 * once dialed, a human operator takes over, same as the existing Tier 3
 * helpline button.
 */
class AutoEscalationCountdownActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAutoEscalationCountdownBinding
    private lateinit var tts: TextToSpeech
    private lateinit var escalation: EscalationOrchestrator
    private var ttsReady = false
    private var countdownTimer: CountDownTimer? = null

    // Guards a real race: CountDownTimer.onFinish() and a Cancel click can
    // both be queued on the main Looper at nearly the same instant if the
    // user taps right as the timer reaches zero. Without this, both paths
    // could run — a real call already placed, then a redundant WarningActivity
    // launched on top of it. Whichever runs first wins; the other is a no-op.
    private var settled = false

    // Separate from `settled`: guards the TTS-completion callback and the
    // safety-timeout Runnable from both firing (e.g. speech finishes right
    // as the timeout would have fired) and starting the countdown twice.
    private var countdownStarted = false
    private val explanationSafetyHandler = Handler(Looper.getMainLooper())
    private val explanationSafetyTimeout = Runnable {
        Log.w(TAG, "Tier 3b explanation TTS safety timeout reached — starting countdown without waiting further.")
        beginCountdownOnce()
    }

    private var phoneNumber: String = ""
    private var transcript: String? = null
    private lateinit var decision: DecisionResult

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAutoEscalationCountdownBinding.inflate(layoutInflater)
        setContentView(binding.root)

        escalation = EscalationOrchestrator(this)

        phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()
        transcript = intent.getStringExtra(EXTRA_TRANSCRIPT)
        decision = DecisionResult(
            riskLevel = RiskLevel.valueOf(intent.getStringExtra(EXTRA_RISK_LEVEL) ?: RiskLevel.HIGH.name),
            headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty(),
            reasons = intent.getStringArrayListExtra(EXTRA_REASONS).orEmpty(),
            suspectedScamType = null,
            ruleCategories = intent.getStringArrayListExtra(EXTRA_RULE_CATEGORIES).orEmpty(),
        )

        // Requirement 1: risk level + reason are visual and immediate — never
        // wait on TTS init, language detection, or anything audio-related.
        renderImmediateVisual()
        binding.countdownHeadline.text = getString(R.string.tier3b_explaining_message)

        binding.cancelButton.setOnClickListener { onCancelTapped() }

        // Uses the app-wide shared TTS instance (RakshakApp.tts), constructed
        // and warmed up once at process start, instead of building a fresh
        // TextToSpeech here — that used to make the engine's several-second
        // onInit binding delay visible every time this screen opened, right
        // when the user needed to hear the explanation fastest. By now, it
        // has almost always already finished initializing in the background.
        val app = application as RakshakApp
        tts = app.tts
        app.onTtsReady {
            ttsReady = app.ttsReady
            if (ttsReady) {
                tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(utteranceId: String?) {}

                    override fun onDone(utteranceId: String?) {
                        runOnUiThread { onExplanationUtteranceDone(utteranceId) }
                    }

                    @Deprecated("Deprecated in Java")
                    override fun onError(utteranceId: String?) {
                        runOnUiThread {
                            Log.e(TAG, "Tier 3b explanation TTS error on utterance=$utteranceId — proceeding.")
                            onExplanationUtteranceDone(utteranceId)
                        }
                    }
                })
                speakExplanationThenCountdown()
            } else {
                Log.e(TAG, "Shared TTS failed to initialize — starting countdown without a spoken explanation.")
                beginCountdownOnce()
            }
        }

        // Requirement 4: fires regardless of whether TTS ever succeeds/finishes.
        explanationSafetyHandler.postDelayed(explanationSafetyTimeout, EXPLANATION_SAFETY_TIMEOUT_MS)
    }

    private fun renderImmediateVisual() {
        binding.riskLevelText.text = getString(
            when (decision.riskLevel) {
                RiskLevel.HIGH -> R.string.tier3b_risk_label_high
                RiskLevel.MEDIUM -> R.string.tier3b_risk_label_medium
                RiskLevel.LOW -> R.string.tier3b_risk_label_low
            }
        )
        binding.reasonText.text = explanationText()
    }

    private fun explanationText(): String =
        (listOf(decision.headline) + decision.reasons).filter { it.isNotBlank() }.joinToString(". ")

    /**
     * Builds the native-language explanation from ONLY the pieces of
     * decision.headline + decision.reasons that have a pre-translated entry
     * in [ExplanationTranslations] for [languageTag] — never the raw English
     * text (see the near-silent-audio diagnosis this fixes). Returns null if
     * nothing translated (e.g. an unsupported language, or a free-text piece
     * outside the fixed set, such as an LLM-generated `reason`) — callers
     * must speak the English pass instead in that case, not fall back to
     * mismatched-voice English.
     */
    private fun nativeExplanationText(languageTag: String): String? {
        val pieces = (listOf(decision.headline) + decision.reasons)
            .filter { it.isNotBlank() }
            .mapNotNull { ExplanationTranslations.translate(it, languageTag) }
        return pieces.takeIf { it.isNotEmpty() }?.joinToString(". ")
    }

    /**
     * Requirement 2: speaks the explanation in the family's preferred
     * language first, then again in English, back to back — same "native
     * language first, English second" convention as the onboarding intro.
     * Skips the repeat if the preferred language IS English. Only once both
     * passes (or the single pass) finish does [beginCountdownOnce] run — see
     * [onExplanationUtteranceDone].
     *
     * The native pass speaks the pre-translated text from
     * [nativeExplanationText], never the raw English — feeding English text
     * through a non-English voice previously produced near-silent audio
     * (mMaxAmplitude ~170 vs. a normal ~13000+), not just mispronunciation.
     * If nothing translates for this language, the native pass is skipped
     * entirely and English is spoken instead — the (unconditional) English
     * pass below already covers that content either way.
     */
    private fun speakExplanationThenCountdown() {
        val app = application as RakshakApp
        val text = explanationText()
        if (text.isBlank()) {
            beginCountdownOnce()
            return
        }
        // No language-selection UI exists yet (see AppSettings.hasExplicitSpokenLanguage),
        // so "no preference chosen" is the common case today — defaults to Hindi
        // per product decision, not to AppSettings.DEFAULT_LANGUAGE's "en-IN".
        val preferredTag = if (app.settings.hasExplicitSpokenLanguage) {
            app.settings.spokenLanguageTag
        } else {
            "hi-IN"
        }
        if (preferredTag.startsWith("en", ignoreCase = true)) {
            speakForced(text, "en-IN", UTTERANCE_EXPLANATION_ENGLISH)
            return
        }
        val nativeText = nativeExplanationText(preferredTag)
        if (nativeText.isNullOrBlank()) {
            Log.i(TAG, "No $preferredTag translation available for this explanation — speaking English only.")
            speakForced(text, "en-IN", UTTERANCE_EXPLANATION_ENGLISH)
        } else {
            speakForced(nativeText, preferredTag, UTTERANCE_EXPLANATION_NATIVE)
        }
    }

    /** Handles both natural completion (onDone) and onError for the two
     *  explanation utterances, chaining native -> English -> countdown.
     *  (The engine-warmup silent utterance now runs once at app start —
     *  see RakshakApp — not per-screen, so it isn't part of this chain.) */
    private fun onExplanationUtteranceDone(utteranceId: String?) {
        if (settled) return // user already cancelled — don't queue more speech or start the countdown
        when (utteranceId) {
            // Pass 2 is always the full, original English text, regardless
            // of what (if anything) the native pass translated — this is
            // what makes a partial/missing native translation safe: every
            // piece is still guaranteed to be heard in English either way.
            UTTERANCE_EXPLANATION_NATIVE -> speakForced(explanationText(), "en-IN", UTTERANCE_EXPLANATION_ENGLISH)
            UTTERANCE_EXPLANATION_ENGLISH -> beginCountdownOnce()
            // Anything else (per-second ticks, the post-dial "calling now"
            // line) isn't part of this chain — no-op.
        }
    }

    /** Forces a specific TTS locale for this utterance — deliberately not
     *  SpeechLanguageSelector, which auto-detects the text's language and
     *  would just pick English both times here (the text itself is always
     *  English; only the requested voice/locale differs between passes). */
    private fun speakForced(text: String, languageTag: String, utteranceId: String) {
        if (!ttsReady || text.isBlank()) {
            onExplanationUtteranceDone(utteranceId)
            return
        }
        val result = tts.setLanguage(Locale.forLanguageTag(languageTag))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            Log.w(TAG, "Tier 3b explanation voice unavailable for $languageTag (result=$result) — skipping this pass.")
            onExplanationUtteranceDone(utteranceId)
            return
        }
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, utteranceId)
    }

    /** Requirement 3/4: the single gate that starts the countdown, reached
     *  either after the spoken explanation genuinely finishes or via the
     *  safety timeout — never both (guarded by [countdownStarted]), and
     *  never if the user already cancelled during the explanation (guarded
     *  by [settled], same flag [onCancelTapped] and [CountDownTimer.onFinish]
     *  already use). */
    private fun beginCountdownOnce() {
        if (settled || countdownStarted) return
        countdownStarted = true
        explanationSafetyHandler.removeCallbacks(explanationSafetyTimeout)
        startCountdown()
    }

    private fun startCountdown() {
        binding.countdownCircleFrame.visibility = View.VISIBLE
        binding.countdownHeadline.text = getString(
            R.string.tier3b_countdown_announcement, COUNTDOWN_SECONDS
        )
        binding.secondsRemainingText.text = COUNTDOWN_SECONDS.toString()
        binding.shrinkingCircleView.progress = 1f
        speak(getString(R.string.tier3b_countdown_announcement, COUNTDOWN_SECONDS))

        countdownTimer = object : CountDownTimer(COUNTDOWN_SECONDS * 1000L, 1000L) {
            override fun onTick(millisUntilFinished: Long) {
                val secondsLeft = ((millisUntilFinished + 999) / 1000).toInt()
                binding.secondsRemainingText.text = secondsLeft.toString()
                binding.shrinkingCircleView.progress = millisUntilFinished / (COUNTDOWN_SECONDS * 1000f)
                if (secondsLeft in 1..9) speak(secondsLeft.toString())
            }

            override fun onFinish() {
                binding.secondsRemainingText.text = "0"
                binding.shrinkingCircleView.progress = 0f
                if (!settled) {
                    settled = true
                    triggerAutoEscalation()
                }
            }
        }.start()
    }

    private fun onCancelTapped() {
        if (settled) return
        settled = true
        countdownTimer?.cancel()
        explanationSafetyHandler.removeCallbacks(explanationSafetyTimeout)
        // Also cancellable during the pre-countdown explanation (native/English
        // TTS pass) — stop() here prevents the voice droning on after Cancel.
        if (::tts.isInitialized) tts.stop()
        Log.i(TAG, "Tier 3b cancelled by user before auto-dial.")
        // Cancelling the auto-call must not leave the user with nothing —
        // fall back to the normal warning card so help is still one tap away.
        startActivity(
            WarningActivity.buildIntent(this, phoneNumber, decision, autoSilenced = false, transcript = transcript)
        )
        finish()
    }

    private fun triggerAutoEscalation() {
        val app = application as RakshakApp
        val number = app.settings.tier3bPhoneNumber.trim()

        val hasCallPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) ==
            PackageManager.PERMISSION_GRANTED

        if (number.isBlank() || !hasCallPermission) {
            Log.e(
                TAG,
                "Tier 3b fired but cannot auto-dial (number blank=${number.isBlank()}, " +
                    "permission granted=$hasCallPermission) — falling back to the normal warning card.",
            )
            startActivity(
                WarningActivity.buildIntent(this, phoneNumber, decision, autoSilenced = false, transcript = transcript)
            )
            finish()
            return
        }

        Log.i(TAG, "Tier 3b auto-dialing $number and notifying trusted contact simultaneously.")
        speak(getString(R.string.tier3b_calling_message))

        // "At the same time" — fire both; neither waits on the other. That
        // still holds with location sharing on: the call intent below fires
        // immediately regardless, and the trusted-contact SMS goes out
        // whenever the location fetch (or its own timeout) resolves — not
        // gated on the call. VictimLocationProvider deliberately holds only
        // applicationContext, not this Activity, because this Activity calls
        // finish() a few lines down, before that callback can fire.
        val hasLocationPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        if (app.settings.locationSharingEnabled && hasLocationPermission) {
            VictimLocationProvider(this).fetchCurrentLocation { location ->
                escalation.notifyTrustedContact(app.settings, phoneNumber, decision, transcript, location)
            }
        } else {
            escalation.notifyTrustedContact(app.settings, phoneNumber, decision, transcript)
        }

        val callIntent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(callIntent)

        // Missed-escalation evidence agent's Tier 3b trigger — runs alongside
        // the call and the Tier 2 alert above, never blocking either.
        scheduleCallOutcomeCheck()

        finish()
    }

    private fun scheduleCallOutcomeCheck() {
        val data = workDataOf(
            Tier3bCallOutcomeWorker.KEY_PHONE_NUMBER to phoneNumber,
            Tier3bCallOutcomeWorker.KEY_TRANSCRIPT to transcript,
            Tier3bCallOutcomeWorker.KEY_RISK_LEVEL to decision.riskLevel.name,
            Tier3bCallOutcomeWorker.KEY_REASONS to decision.reasons.toTypedArray(),
        )
        val request = OneTimeWorkRequestBuilder<Tier3bCallOutcomeWorker>()
            .setInputData(data)
            .build()
        WorkManager.getInstance(this).enqueue(request)
    }

    private fun speak(text: String) {
        if (!ttsReady || text.isBlank()) return
        tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "rakshak_tier3b")
    }

    override fun onDestroy() {
        countdownTimer?.cancel()
        explanationSafetyHandler.removeCallbacks(explanationSafetyTimeout)
        // tts is app-wide now (RakshakApp) — stop() cancels this screen's own
        // pending speech, but never shutdown(): that would kill the engine
        // for the whole app, not just this Activity.
        if (::tts.isInitialized) tts.stop()
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_PHONE_NUMBER = "phone_number"
        private const val EXTRA_RISK_LEVEL = "risk_level"
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_REASONS = "reasons"
        private const val EXTRA_TRANSCRIPT = "transcript"
        private const val EXTRA_RULE_CATEGORIES = "rule_categories"

        fun buildIntent(
            context: Context,
            phoneNumber: String,
            decision: DecisionResult,
            transcript: String? = null,
        ): Intent = Intent(context, AutoEscalationCountdownActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            putExtra(EXTRA_PHONE_NUMBER, phoneNumber)
            putExtra(EXTRA_RISK_LEVEL, decision.riskLevel.name)
            putExtra(EXTRA_HEADLINE, decision.headline)
            putStringArrayListExtra(EXTRA_REASONS, ArrayList(decision.reasons))
            putExtra(EXTRA_TRANSCRIPT, transcript)
            putStringArrayListExtra(EXTRA_RULE_CATEGORIES, ArrayList(decision.ruleCategories))
        }
    }
}
