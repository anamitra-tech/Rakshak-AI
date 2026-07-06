package com.rakshak.ai.ui

import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityCheckCallBinding
import com.rakshak.ai.intelligence.DecisionAgent
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.PrahariUnavailableException
import com.rakshak.ai.intelligence.RiskLevel
import kotlinx.coroutines.launch

/**
 * Manual "what did the caller say?" screen — this is where real Prahari
 * calls happen in Phase 1 (see CLAUDE.md Section 3.2). No live audio, no STT:
 * the user types or pastes the text themselves. Calls `/analyze_voice` and
 * `/analyze_session` only — never `/assistant/chat` (that's the LLM/RAG
 * explanation, explicitly Phase 2).
 */
class CheckCallActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCheckCallBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCheckCallBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.analyzeButton.setOnClickListener { runAnalysis() }
    }

    private fun runAnalysis() {
        val transcript = binding.transcriptInput.text?.toString().orEmpty().trim()
        if (transcript.isEmpty()) {
            binding.resultText.text = getString(R.string.check_call_empty_error)
            binding.resultText.visibility = View.VISIBLE
            return
        }
        val phoneNumber = binding.phoneInput.text?.toString().orEmpty().trim()
        // A fixed fallback id here would let unrelated anonymous checks share
        // server-side session history (see /analyze_session in ml/session.py,
        // which accumulates events per session_id with no TTL) — a scam text
        // checked hours ago would then flag an unrelated, unnamed message
        // tested later as a "repeated"/"sustained" session. Only a real phone
        // number identifies a genuine recurring caller worth tracking across
        // checks; every anonymous check gets its own one-shot id instead.
        val sessionId = phoneNumber.ifBlank { "anon-${java.util.UUID.randomUUID()}" }

        binding.resultText.visibility = View.VISIBLE
        binding.resultText.text = getString(R.string.check_call_loading)
        binding.analyzeButton.isEnabled = false
        // Reset feedback affordance from any previous check on this screen.
        binding.feedbackToggle.visibility = View.GONE
        binding.feedbackButtons.visibility = View.GONE
        binding.feedbackThanksText.visibility = View.GONE

        val app = application as RakshakApp
        lifecycleScope.launch {
            try {
                val textAnalysis = app.prahariApiClient.analyzeVoice(transcript)
                val sessionAnalysis = app.prahariApiClient.analyzeSession(sessionId, transcript)
                val lookup = app.callerLookupSource.lookup(phoneNumber)
                val decision = DecisionAgent.decide(lookup, textAnalysis, sessionAnalysis)

                if (decision.riskLevel == RiskLevel.LOW) {
                    binding.resultText.text = decision.headline
                    setUpFeedback(transcript, phoneNumber, decision)
                } else if (app.settings.tier3bEnabled && DecisionAgent.hasNearDeterministicSignal(decision)) {
                    // Tier 3b — only ever from here: the pre-connect
                    // CallScreeningService flow has no transcript, so it can
                    // never produce a near-deterministic rule match.
                    startActivity(
                        AutoEscalationCountdownActivity.buildIntent(
                            this@CheckCallActivity, phoneNumber, decision,
                        )
                    )
                } else {
                    startActivity(
                        WarningActivity.buildIntent(
                            this@CheckCallActivity,
                            phoneNumber,
                            decision,
                            autoSilenced = false,
                            transcript = transcript,
                        )
                    )
                }
            } catch (e: PrahariUnavailableException) {
                binding.resultText.text = getString(
                    R.string.check_call_backend_error,
                    app.settings.prahariBaseUrl,
                )
            } finally {
                binding.analyzeButton.isEnabled = true
            }
        }
    }

    /** Only reached for a LOW-risk verdict — MEDIUM/HIGH hand off to
     *  WarningActivity, which has its own feedback affordance. */
    private fun setUpFeedback(transcript: String, phoneNumber: String, decision: DecisionResult) {
        binding.feedbackToggle.visibility = View.VISIBLE
        binding.feedbackButtons.visibility = View.GONE
        binding.feedbackThanksText.visibility = View.GONE
        binding.feedbackToggle.setOnClickListener {
            binding.feedbackToggle.visibility = View.GONE
            binding.feedbackButtons.visibility = View.VISIBLE
        }
        binding.feedbackNegativeButton.text = getString(R.string.feedback_negative_should_flag_button)
        binding.feedbackPositiveButton.setOnClickListener {
            recordFeedback(transcript, phoneNumber, decision, "confirmed_correct")
        }
        binding.feedbackNegativeButton.setOnClickListener {
            recordFeedback(transcript, phoneNumber, decision, "should_have_been_flagged")
        }
    }

    private fun recordFeedback(transcript: String, phoneNumber: String, decision: DecisionResult, userCorrection: String) {
        binding.feedbackButtons.visibility = View.GONE
        binding.feedbackThanksText.visibility = View.VISIBLE
        val app = application as RakshakApp
        lifecycleScope.launch {
            app.prahariApiClient.submitFeedback(
                channel = "android_check_call",
                originalText = transcript,
                verdict = decision.rawLabel ?: decision.riskLevel.name,
                ruleCategories = decision.ruleCategories,
                userCorrection = userCorrection,
                sessionId = phoneNumber.ifBlank { null },
            )
        }
    }
}
