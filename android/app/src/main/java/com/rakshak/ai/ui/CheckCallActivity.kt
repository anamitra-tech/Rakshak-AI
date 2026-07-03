package com.rakshak.ai.ui

import android.os.Bundle
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityCheckCallBinding
import com.rakshak.ai.intelligence.DecisionAgent
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
        val sessionId = phoneNumber.ifBlank { "manual-check" }

        binding.resultText.visibility = View.VISIBLE
        binding.resultText.text = getString(R.string.check_call_loading)
        binding.analyzeButton.isEnabled = false

        val app = application as RakshakApp
        lifecycleScope.launch {
            try {
                val textAnalysis = app.prahariApiClient.analyzeVoice(transcript)
                val sessionAnalysis = app.prahariApiClient.analyzeSession(sessionId, transcript)
                val lookup = app.callerLookupSource.lookup(phoneNumber)
                val decision = DecisionAgent.decide(lookup, textAnalysis, sessionAnalysis)

                if (decision.riskLevel == RiskLevel.LOW) {
                    binding.resultText.text = decision.headline
                } else {
                    startActivity(
                        WarningActivity.buildIntent(
                            this@CheckCallActivity,
                            phoneNumber,
                            decision,
                            autoSilenced = false,
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
}
