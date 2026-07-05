package com.rakshak.ai.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.CountDownTimer
import android.speech.tts.TextToSpeech
import android.util.Log
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
import com.rakshak.ai.intelligence.RiskLevel
import java.util.Locale

private const val TAG = "RakshakTier3b"
private const val COUNTDOWN_SECONDS = 10

/**
 * Tier 3b — autonomous escalation. Only ever launched when BOTH:
 *  1. the family has explicitly opted in (AppSettings.tier3bEnabled), and
 *  2. a near-deterministic rule fired (DecisionAgent.hasNearDeterministicSignal)
 * — never from the base ML score alone, however high it scored (see
 * CheckCallActivity, the only place that can launch this: the pre-connect
 * CallScreeningService flow has no transcript, so it can never produce a
 * near-deterministic rule match in the first place).
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

    private var phoneNumber: String = ""
    private var transcript: String? = null
    private lateinit var decision: DecisionResult

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAutoEscalationCountdownBinding.inflate(layoutInflater)
        setContentView(binding.root)

        escalation = EscalationOrchestrator(this)
        val app = application as RakshakApp

        phoneNumber = intent.getStringExtra(EXTRA_PHONE_NUMBER).orEmpty()
        transcript = intent.getStringExtra(EXTRA_TRANSCRIPT)
        decision = DecisionResult(
            riskLevel = RiskLevel.valueOf(intent.getStringExtra(EXTRA_RISK_LEVEL) ?: RiskLevel.HIGH.name),
            headline = intent.getStringExtra(EXTRA_HEADLINE).orEmpty(),
            reasons = intent.getStringArrayListExtra(EXTRA_REASONS).orEmpty(),
            suspectedScamType = null,
        )

        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (ttsReady) {
                tts.setLanguage(Locale.forLanguageTag(app.settings.spokenLanguageTag))
                speak(getString(R.string.tier3b_countdown_announcement, COUNTDOWN_SECONDS))
            }
        }

        binding.cancelButton.setOnClickListener { onCancelTapped() }

        startCountdown()
    }

    private fun startCountdown() {
        binding.countdownHeadline.text = getString(
            R.string.tier3b_countdown_announcement, COUNTDOWN_SECONDS
        )
        binding.secondsRemainingText.text = COUNTDOWN_SECONDS.toString()
        binding.shrinkingCircleView.progress = 1f

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

        // "At the same time" — fire both; neither waits on the other.
        escalation.notifyTrustedContact(app.settings, phoneNumber, decision, transcript)

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
        if (::tts.isInitialized) {
            tts.stop()
            tts.shutdown()
        }
        super.onDestroy()
    }

    companion object {
        private const val EXTRA_PHONE_NUMBER = "phone_number"
        private const val EXTRA_RISK_LEVEL = "risk_level"
        private const val EXTRA_HEADLINE = "headline"
        private const val EXTRA_REASONS = "reasons"
        private const val EXTRA_TRANSCRIPT = "transcript"

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
        }
    }
}
