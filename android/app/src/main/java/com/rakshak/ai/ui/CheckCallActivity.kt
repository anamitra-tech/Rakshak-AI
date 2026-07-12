package com.rakshak.ai.ui

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityCheckCallBinding
import com.rakshak.ai.escalation.ScreenshotEvidenceStore
import com.rakshak.ai.intelligence.DecisionAgent
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.OfflineEvaluator
import com.rakshak.ai.intelligence.PrahariTextAnalysis
import com.rakshak.ai.intelligence.PrahariUnavailableException
import com.rakshak.ai.intelligence.RiskLevel
import com.rakshak.ai.intelligence.hasActiveNetworkConnection
import com.rakshak.ai.intelligence.normalizePhoneNumber
import com.rakshak.ai.ocr.ScreenshotOcrHelper
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

    companion object {
        private const val TAG = "RakshakCheckCall"
    }

    private lateinit var binding: ActivityCheckCallBinding
    private lateinit var voiceInput: VoiceInputHelper
    private lateinit var loadingOverlay: LoadingOverlay
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

    // A standard system picker (SAF-mediated) -- no runtime permission
    // needed for a single-image pick, consistent with CLAUDE.md's "system
    // pickers over bulk grants" rule. Null result means the user backed out
    // of the picker; that's not an error, just do nothing.
    private val screenshotPickerLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) handlePickedScreenshot(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCheckCallBinding.inflate(layoutInflater)
        setContentView(binding.root)

        voiceInput = VoiceInputHelper(this)
        setUpVoiceInputButton()
        binding.screenshotUploadButton.setOnClickListener {
            screenshotPickerLauncher.launch("image/*")
        }

        loadingOverlay = LoadingOverlay(
            overlayView = binding.loadingOverlay.root,
            radarSweepView = binding.loadingOverlay.radarSweep,
            phraseView = binding.loadingOverlay.loadingPhrase,
            phrases = resources.getStringArray(R.array.loading_reassuring_phrases).toList(),
        )

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

    /**
     * Runs OCR on the picked image and, on success, replaces
     * [ActivityCheckCallBinding.transcriptInput]'s text with the extracted
     * text — same field typed and voice input use, still fully editable
     * before the user taps Check. Also saves the original image into the
     * shared evidence folder ([ScreenshotEvidenceStore]) regardless of
     * whether OCR found readable text, since the image itself may still be
     * usable evidence on NCRP's form even if this app's on-device OCR
     * (Latin script only — see [ScreenshotOcrHelper]) couldn't read it.
     */
    private fun handlePickedScreenshot(uri: Uri) {
        ScreenshotEvidenceStore.save(this, uri)

        showScreenshotStatus(getString(R.string.check_call_screenshot_processing))
        ScreenshotOcrHelper.recognizeText(this, uri, object : ScreenshotOcrHelper.Callback {
            override fun onSuccess(text: String) {
                binding.transcriptInput.setText(text)
                binding.transcriptInput.setSelection(text.length)
                showScreenshotStatus(getString(R.string.check_call_screenshot_success))
            }

            override fun onNoTextFound() {
                showScreenshotStatus(getString(R.string.check_call_screenshot_no_text_found))
            }

            override fun onFailure(message: String) {
                showScreenshotStatus(getString(R.string.check_call_screenshot_failed, message))
            }
        })
    }

    private fun showScreenshotStatus(message: String) {
        binding.screenshotStatusText.text = message
        binding.screenshotStatusText.visibility = View.VISIBLE
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

        binding.resultText.visibility = View.GONE
        loadingOverlay.show()
        binding.analyzeButton.isEnabled = false

        val app = application as RakshakApp
        val startMs = SystemClock.elapsedRealtime()
        Log.i(TAG, "analysis_start")
        lifecycleScope.launch {
            try {
                // No active network at all (e.g. airplane mode) — skip the
                // HTTP attempt entirely rather than let OkHttp discover this
                // itself after a connect-timeout wait. There's genuinely
                // nothing to reach, so there's nothing to wait for; this
                // throws the same exception the real request would
                // eventually throw anyway, reusing the offline fallback
                // below unchanged rather than duplicating it.
                if (!hasActiveNetworkConnection(this@CheckCallActivity)) {
                    Log.i(TAG, "analysis_no_network_detected elapsed_ms=${SystemClock.elapsedRealtime() - startMs}")
                    throw PrahariUnavailableException("No active network connection")
                }
                val textAnalysis = app.prahariApiClient.analyzeVoice(transcript)
                val sessionAnalysis = app.prahariApiClient.analyzeSession(sessionId, transcript)
                val lookup = app.callerLookupSource.lookup(phoneNumber)
                val isTrustedContact = phoneNumber.isNotBlank() &&
                    app.settings.trustedContactPhone.isNotBlank() &&
                    normalizePhoneNumber(phoneNumber) == normalizePhoneNumber(app.settings.trustedContactPhone)
                val decision = DecisionAgent.decide(lookup, textAnalysis, sessionAnalysis, isTrustedContact)
                Log.i(TAG, "analysis_online_success elapsed_ms=${SystemClock.elapsedRealtime() - startMs}")
                routeToOutcome(decision, phoneNumber, transcript)
            } catch (e: PrahariUnavailableException) {
                Log.i(TAG, "analysis_prahari_unavailable elapsed_ms=${SystemClock.elapsedRealtime() - startMs} msg=${e.message}")
                // Prahari unreachable — fall back to OfflineEvaluator, which
                // combines the same three near-deterministic regex
                // categories the backend treats as certain-scam-on-their-own
                // with MlScamScorer's ported copy of the actual trained
                // model (not just the rules), so a message with no rule hit
                // but a real ML signal (e.g. an expert_scam-style script with
                // no digit-count/OTP wording) still gets flagged instead of
                // silently falling through to "no match". This is strictly a
                // fallback: it never runs when the backend answered, and a
                // LOW verdict here does NOT mean "definitely safe" — it means
                // the full ML/session/graph analysis simply couldn't run,
                // which the shown message says explicitly.
                val offlineEval = OfflineEvaluator.evaluate(transcript, app.offlineMlModel)
                Log.i(TAG, "analysis_offline_result elapsed_ms=${SystemClock.elapsedRealtime() - startMs} riskLevel=${offlineEval.riskLevel} score=${offlineEval.score}")
                if (offlineEval.riskLevel != RiskLevel.LOW) {
                    val offlineAnalysis = PrahariTextAnalysis(
                        riskLevel = offlineEval.riskLevel,
                        rawLabel = if (offlineEval.riskLevel == RiskLevel.HIGH) "FRAUD" else "SUSPICIOUS",
                        score = offlineEval.score,
                        reason = offlineEval.reason,
                        signals = offlineEval.signals,
                        recommendedAction =
                            "Block sender, do NOT share any code/money, report at cybercrime.gov.in / 1930.",
                        ruleCategories = offlineEval.ruleCategories,
                    )
                    val lookup = app.callerLookupSource.lookup(phoneNumber)
                    val isTrustedContact = phoneNumber.isNotBlank() &&
                        app.settings.trustedContactPhone.isNotBlank() &&
                        normalizePhoneNumber(phoneNumber) == normalizePhoneNumber(app.settings.trustedContactPhone)
                    val decision = DecisionAgent.decide(lookup, offlineAnalysis, null, isTrustedContact)
                    routeToOutcome(decision, phoneNumber, transcript)
                } else {
                    binding.resultText.text = getString(R.string.check_call_offline_no_match)
                    binding.resultText.visibility = View.VISIBLE
                }
            } finally {
                loadingOverlay.hide()
                binding.analyzeButton.isEnabled = true
            }
        }
    }

    private fun routeToOutcome(decision: DecisionResult, phoneNumber: String, transcript: String) {
        if (decision.riskLevel == RiskLevel.LOW) {
            binding.resultText.visibility = View.GONE
            startActivity(
                SafeResultActivity.buildIntent(this@CheckCallActivity, phoneNumber, decision)
            )
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
    }
}
