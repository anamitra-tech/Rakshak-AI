package com.rakshak.ai.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityCheckCallBinding
import com.rakshak.ai.intelligence.DecisionAgent
import com.rakshak.ai.intelligence.PrahariUnavailableException
import com.rakshak.ai.intelligence.RiskLevel
import com.rakshak.ai.intelligence.normalizePhoneNumber
import com.rakshak.ai.stt.VoiceInputHelper
import kotlinx.coroutines.launch

/**
 * Manual "what did the caller say?" screen — this is where real Prahari
 * calls happen in Phase 1 (see CLAUDE.md Section 3.2). No live audio: the
 * user types/pastes the text themselves, or optionally speaks it via the
 * on-device SpeechRecognizer (VoiceInputHelper) — voice is an input-method
 * option alongside typed text, never a replacement, and still produces the
 * same transcript string sent to the backend. Calls `/analyze_voice` and
 * `/analyze_session` only — never `/assistant/chat` (that's the LLM/RAG
 * explanation, explicitly Phase 2).
 */
class CheckCallActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCheckCallBinding
    private lateinit var voiceInput: VoiceInputHelper
    private var isListening = false

    private val micPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startVoiceInput()
        } else {
            showVoiceStatus(getString(R.string.check_call_voice_permission_denied))
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCheckCallBinding.inflate(layoutInflater)
        setContentView(binding.root)

        voiceInput = VoiceInputHelper(this)
        setUpVoiceInputButton()

        binding.analyzeButton.setOnClickListener { runAnalysis() }
    }

    /** Hides the mic option entirely on devices/OS versions that can't do
     *  genuinely on-device recognition — typed input remains the only path,
     *  never a crash, never a silent cloud fallback. See VoiceInputHelper.
     *  Leaves a one-line explanation behind rather than just disappearing —
     *  a mic button that's simply absent, with no message, reads as a bug
     *  to a user who expected it, not a deliberate device/OS limitation. */
    private fun setUpVoiceInputButton() {
        if (!voiceInput.isDeviceCapable()) {
            binding.voiceInputButton.visibility = View.GONE
            showVoiceStatus(getString(R.string.check_call_voice_unsupported_device))
            return
        }
        binding.voiceInputButton.setOnClickListener {
            if (isListening) {
                voiceInput.stopListening()
                isListening = false
                binding.voiceInputButton.text = getString(R.string.check_call_voice_button)
            } else {
                requestMicAndStart()
            }
        }
    }

    private fun requestMicAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            startVoiceInput()
        } else {
            micPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private fun startVoiceInput() {
        val app = application as RakshakApp
        binding.voiceStatusText.visibility = View.GONE
        voiceInput.startListening(app.settings.spokenLanguageTag, object : VoiceInputHelper.Callback {
            override fun onListeningStateChanged(listening: Boolean) {
                isListening = listening
                binding.voiceInputButton.text = getString(
                    if (listening) R.string.check_call_voice_listening else R.string.check_call_voice_button
                )
            }

            override fun onPartialResult(text: String) {
                binding.transcriptInput.setText(text)
                binding.transcriptInput.setSelection(text.length)
            }

            override fun onFinalResult(text: String) {
                binding.transcriptInput.setText(text)
                binding.transcriptInput.setSelection(text.length)
                isListening = false
                binding.voiceInputButton.text = getString(R.string.check_call_voice_button)
            }

            override fun onTransientError(message: String) {
                isListening = false
                binding.voiceInputButton.text = getString(R.string.check_call_voice_button)
                showVoiceStatus(message)
            }

            override fun onLanguageOrDeviceUnavailable(message: String) {
                isListening = false
                // Don't invite a retry loop against a language/device gap
                // that won't resolve itself — hide the option and let typed
                // input carry the rest of this session.
                binding.voiceInputButton.visibility = View.GONE
                showVoiceStatus(message)
            }
        })
    }

    private fun showVoiceStatus(message: String) {
        binding.voiceStatusText.text = message
        binding.voiceStatusText.visibility = View.VISIBLE
    }

    override fun onDestroy() {
        voiceInput.stopListening()
        super.onDestroy()
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

        val app = application as RakshakApp
        lifecycleScope.launch {
            try {
                val textAnalysis = app.prahariApiClient.analyzeVoice(transcript)
                val sessionAnalysis = app.prahariApiClient.analyzeSession(sessionId, transcript)
                val lookup = app.callerLookupSource.lookup(phoneNumber)
                val isTrustedContact = phoneNumber.isNotBlank() &&
                    app.settings.trustedContactPhone.isNotBlank() &&
                    normalizePhoneNumber(phoneNumber) == normalizePhoneNumber(app.settings.trustedContactPhone)
                val decision = DecisionAgent.decide(lookup, textAnalysis, sessionAnalysis, isTrustedContact)

                if (decision.riskLevel == RiskLevel.LOW) {
                    binding.resultText.text = decision.headline
                } else if (decision.riskLevel == RiskLevel.HIGH) {
                    // Auto-dial + Tier-2 SMS alert together, after a
                    // cancellable countdown — fires for any HIGH verdict from
                    // this screen now, not gated behind the family's Tier 3b
                    // opt-in or a near-deterministic rule match (deliberate
                    // product decision; see head.md for the tradeoff this
                    // accepts). AutoEscalationCountdownActivity still falls
                    // back to the plain WarningActivity on its own if no
                    // number is configured or CALL_PHONE was never granted —
                    // that fallback is unchanged.
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
}
