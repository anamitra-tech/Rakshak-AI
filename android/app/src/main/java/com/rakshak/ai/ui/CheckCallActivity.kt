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
import com.rakshak.ai.ocr.CloudOcrClient
import com.rakshak.ai.ocr.ScreenshotOcrHelper
import com.rakshak.ai.sarvam.SarvamApiClient
import com.rakshak.ai.sarvam.SarvamLanguageCodes
import com.rakshak.ai.sarvam.SarvamUnavailableException
import com.rakshak.ai.stt.SarvamVoiceRecorder
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
    private lateinit var sarvamRecorder: SarvamVoiceRecorder
    private lateinit var loadingOverlay: LoadingOverlay
    private var isListening = false

    /** True once native on-device recognition has been ruled out (device
     *  incapable, or a language/device error mid-session) and Sarvam's
     *  online STT is being used instead — see [setUpVoiceInputButton] and
     *  [VoiceInputHelper.Callback.onLanguageOrDeviceUnavailable] below. */
    private var usingSarvamVoice = false

    /**
     * Language of whatever currently populates [ActivityCheckCallBinding.transcriptInput],
     * for the Sarvam translate-to-English bridge in [runAnalysis] — Prahari's
     * classifier training data doesn't cover Indic vocabulary outside
     * English/Hindi (CLAUDE.md Section 6). Null means "assume compatible,
     * don't translate" (typed/pasted input, or Sarvam-STT text that's
     * already English via mode=translate). Set explicitly whenever OCR
     * (on-device or cloud) fills the field with text in a specific script.
     */
    private var transcriptSourceLanguageTag: String? = null

    private val micPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            if (usingSarvamVoice) startSarvamRecording() else startVoiceInput()
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
        sarvamRecorder = SarvamVoiceRecorder(this)
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

    /**
     * On-device recognition is tried first (free, no network, no audio ever
     * leaves the device). If the device can't do on-device recognition at
     * all, or a language/device error surfaces mid-session (see
     * [onLanguageOrDeviceUnavailable] below), this switches to Sarvam's
     * online STT ([usingSarvamVoice]) rather than just hiding the mic —
     * only when online and [SarvamApiClient.isConfigured]. Only when neither
     * path is available does the mic option disappear, with a one-line
     * explanation left behind rather than just vanishing (a mic button
     * that's simply absent, with no message, reads as a bug to a user who
     * expected it, not a deliberate device/OS/connectivity limitation).
     */
    private fun setUpVoiceInputButton() {
        if (!voiceInput.isDeviceCapable() && !SarvamApiClient.isConfigured()) {
            binding.voiceInputButton.visibility = View.GONE
            showVoiceStatus(getString(R.string.check_call_voice_unsupported_device))
            return
        }
        if (!voiceInput.isDeviceCapable()) {
            // Sarvam-only from the start (device incapable of on-device
            // recognition at all) -- usingSarvamVoice is set up front here,
            // same as the mid-session switch in onLanguageOrDeviceUnavailable
            // below, so the single click listener below stays correct either way.
            usingSarvamVoice = true
            showVoiceStatus(getString(R.string.check_call_voice_sarvam_only_device))
        }
        // One listener, checking current mode at tap time -- NOT two
        // separate closures bound once at setup. Real bug this replaced: a
        // native-recognition attempt that fails mid-session flips
        // usingSarvamVoice to true from inside onLanguageOrDeviceUnavailable,
        // but the click listener registered here at onCreate time never got
        // reassigned, so tapping "stop" still called voiceInput.stopListening()
        // (a no-op on an already-dead recognizer) instead of
        // stopSarvamRecordingAndUpload() -- the Sarvam recording ran to its
        // full MAX_DURATION_MS cap every time instead of stopping on tap.
        binding.voiceInputButton.setOnClickListener {
            when {
                isListening && usingSarvamVoice -> stopSarvamRecordingAndUpload()
                isListening -> {
                    voiceInput.stopListening()
                    isListening = false
                    binding.voiceInputButton.text = getString(R.string.check_call_voice_button)
                }
                else -> requestMicAndStart()
            }
        }
    }

    private fun requestMicAndStart() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            if (usingSarvamVoice) startSarvamRecording() else startVoiceInput()
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
                // Native recognizer echoes back text in whatever language it
                // was asked to listen for -- same translate-before-Prahari
                // rule as OCR applies here too (see runAnalysis).
                transcriptSourceLanguageTag = app.settings.spokenLanguageTag
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
                if (SarvamApiClient.isConfigured() && hasActiveNetworkConnection(this@CheckCallActivity)) {
                    Log.i(TAG, "voice_input_switching_to_sarvam_fallback")
                    usingSarvamVoice = true
                    showVoiceStatus(getString(R.string.check_call_voice_sarvam_fallback_notice))
                    startSarvamRecording()
                } else {
                    // No online fallback possible -- don't invite a retry
                    // loop against a gap that won't resolve itself this
                    // session; hide the option and let typed input carry
                    // the rest of this session.
                    binding.voiceInputButton.visibility = View.GONE
                    showVoiceStatus(message)
                }
            }
        })
    }

    /** Starts recording for [SarvamApiClient] upload (see [SarvamVoiceRecorder]) --
     *  only reached once RECORD_AUDIO is already granted, either directly
     *  (device incapable of on-device recognition) or after native
     *  recognition itself failed mid-session. */
    private fun startSarvamRecording() {
        binding.voiceStatusText.visibility = View.GONE
        val started = sarvamRecorder.startRecording(object : SarvamVoiceRecorder.Callback {
            override fun onMaxDurationReached() {
                Log.i(TAG, "sarvam_recording_max_duration_reached")
                stopSarvamRecordingAndUpload()
            }
        })
        if (!started) {
            showVoiceStatus(getString(R.string.check_call_voice_start_failed))
            return
        }
        isListening = true
        binding.voiceInputButton.text = getString(R.string.check_call_voice_listening)
    }

    private fun stopSarvamRecordingAndUpload() {
        isListening = false
        binding.voiceInputButton.text = getString(R.string.check_call_voice_button)
        val file = sarvamRecorder.stopRecording()
        if (file == null) {
            showVoiceStatus(getString(R.string.check_call_voice_no_match))
            return
        }
        val app = application as RakshakApp
        showVoiceStatus(getString(R.string.check_call_voice_sarvam_uploading))
        lifecycleScope.launch {
            try {
                val transcript = SarvamApiClient.transcribeAndTranslate(file, app.settings.evidenceBaseUrl)
                binding.transcriptInput.setText(transcript)
                binding.transcriptInput.setSelection(transcript.length)
                // mode=translate already returns English -- no further
                // translation needed before this reaches Prahari.
                transcriptSourceLanguageTag = "en-IN"
                binding.voiceStatusText.visibility = View.GONE
                Log.i(TAG, "sarvam_stt_success")
            } catch (e: SarvamUnavailableException) {
                Log.i(TAG, "sarvam_stt_failed msg=${e.message}")
                showVoiceStatus(getString(R.string.check_call_voice_sarvam_failed))
            } finally {
                file.delete()
            }
        }
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
     * usable evidence on NCRP's form even if no OCR path here could read it.
     *
     * Script routing: [ScreenshotOcrHelper.scriptFamilyFor] maps the app's
     * configured spoken language to Latin/Devanagari (on-device, free, no
     * network) or NONE (Bengali/Tamil/Telugu/Kannada/Malayalam/Gujarati/
     * Punjabi/Odia/Urdu — ML Kit has no recognizer for these scripts at
     * all). NONE routes to [CloudOcrClient] only when online; offline it
     * shows the honest "needs internet" message rather than silently
     * failing or guessing at Latin/Devanagari text that isn't there.
     */
    private fun handlePickedScreenshot(uri: Uri) {
        ScreenshotEvidenceStore.save(this, uri)

        val app = application as RakshakApp
        val preferredScript = ScreenshotOcrHelper.scriptFamilyFor(app.settings.spokenLanguageTag)

        showScreenshotStatus(getString(R.string.check_call_screenshot_processing))
        ScreenshotOcrHelper.recognizeText(this, uri, preferredScript, object : ScreenshotOcrHelper.Callback {
            override fun onSuccess(text: String, matchedScript: ScreenshotOcrHelper.ScriptFamily) {
                Log.i(TAG, "DIAG_ocr_extracted_text script=$matchedScript text=${text.replace("\n", "\\n")}")
                binding.transcriptInput.setText(text)
                binding.transcriptInput.setSelection(text.length)
                // Which recognizer actually matched decides the source
                // language for runAnalysis's translate-before-Prahari bridge
                // -- NOT necessarily preferredScript (see recognizeText's
                // doc comment: a Latin-language-configured phone can still
                // successfully OCR a forwarded Devanagari screenshot, and
                // vice versa). Devanagari is ambiguous between Hindi and
                // Marathi (ML Kit's recognizer doesn't distinguish); the
                // app's own configured language disambiguates when it's
                // one of the two, else defaults to Hindi (the more common
                // case, and the one CLAUDE.md already documents as at least
                // partially classifier-covered) -- a known, accepted
                // approximation, not a guarantee.
                transcriptSourceLanguageTag = when (matchedScript) {
                    ScreenshotOcrHelper.ScriptFamily.LATIN -> "en-IN"
                    ScreenshotOcrHelper.ScriptFamily.DEVANAGARI ->
                        if (app.settings.spokenLanguageTag.startsWith("mr", ignoreCase = true)) "mr-IN" else "hi-IN"
                    ScreenshotOcrHelper.ScriptFamily.NONE -> null // unreachable here
                }
                showScreenshotStatus(getString(R.string.check_call_screenshot_success))
            }

            override fun onNoTextFound() {
                showScreenshotStatus(getString(R.string.check_call_screenshot_no_text_found))
            }

            override fun onFailure(message: String) {
                showScreenshotStatus(getString(R.string.check_call_screenshot_failed, message))
            }

            override fun onScriptNotSupportedOnDevice() {
                if (!hasActiveNetworkConnection(this@CheckCallActivity)) {
                    Log.i(TAG, "ocr_script_unsupported_offline")
                    showScreenshotStatus(getString(R.string.check_call_screenshot_needs_internet))
                    return
                }
                Log.i(TAG, "ocr_cloud_fallback_start")
                showScreenshotStatus(getString(R.string.check_call_screenshot_cloud_processing))
                CloudOcrClient.recognizeText(
                    this@CheckCallActivity,
                    uri,
                    app.settings.evidenceBaseUrl,
                    app.settings.spokenLanguageTag,
                    object : CloudOcrClient.Callback {
                        override fun onSuccess(text: String) {
                            Log.i(TAG, "ocr_cloud_fallback_success")
                            binding.transcriptInput.setText(text)
                            binding.transcriptInput.setSelection(text.length)
                            // Unambiguous here: cloud OCR was only ever reached
                            // because preferredScript (the app's configured
                            // language) has no on-device recognizer.
                            transcriptSourceLanguageTag = app.settings.spokenLanguageTag
                            showScreenshotStatus(getString(R.string.check_call_screenshot_success))
                        }

                        override fun onNoTextFound() {
                            showScreenshotStatus(getString(R.string.check_call_screenshot_no_text_found))
                        }

                        override fun onFailure(message: String) {
                            Log.i(TAG, "ocr_cloud_fallback_failed msg=$message")
                            showScreenshotStatus(getString(R.string.check_call_screenshot_cloud_failed, message))
                        }
                    },
                )
            }
        })
    }

    private fun showScreenshotStatus(message: String) {
        binding.screenshotStatusText.text = message
        binding.screenshotStatusText.visibility = View.VISIBLE
    }

    override fun onDestroy() {
        voiceInput.stopListening()
        sarvamRecorder.stopAndDiscard()
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
                // Real bug fixed here: this used to also skip translation for
                // sourceTag == "hi-IN", on the mistaken assumption that
                // "Prahari's classifier covers Hindi" meant *any* Hindi input
                // was already usable. It doesn't -- ml.detector's patterns
                // (CLAUDE.md Section 6.2's second documented gap) are
                // Latin-script Hinglish only, zero native-script examples for
                // any of the 12 target languages, not just Devanagari. Since
                // Devanagari-matched OCR/native-recognizer text is tagged
                // "hi-IN" (see onSuccess's matchedScript handling above), that
                // old check sent genuine Devanagari Hindi straight to the
                // classifier unmodified -- it never matched any pattern,
                // Latin or otherwise. Only "en-IN" (already English, from a
                // Latin OCR match or Sarvam STT's mode=translate output) skips
                // translation now.
                //
                // Generalized further: typed/pasted text used to be sent as-is
                // whenever transcriptSourceLanguageTag was null (no OCR/voice
                // metadata to key off), on the theory that "the user is
                // responsible for what they type." That was still keying the
                // decision off *input source* rather than *script* -- a user
                // pasting a forwarded Bengali/Tamil/etc. scam message directly
                // into the field hit the exact same bug this comment
                // originally described for Devanagari, just via a different
                // path. SarvamLanguageCodes.detectNativeScriptTag scans the
                // actual text content for any of the 12 languages' native
                // scripts as a fallback when there's no source-tag metadata,
                // so this is now genuinely script-based, not source-based. A
                // translation failure here degrades to analyzing the
                // untranslated text rather than blocking the whole check --
                // worse classifier accuracy on that one check, not a broken
                // flow.
                var textForAnalysis = transcript
                Log.i(TAG, "DIAG_transcript_before_translate text=${transcript.replace("\n", "\\n")}")
                val sourceTag = transcriptSourceLanguageTag
                    ?: SarvamLanguageCodes.detectNativeScriptTag(transcript)
                // Set only once translateToEnglish actually succeeds -- used
                // below to translate the decision's headline/reasons back for
                // display+speech. Left null on failure or "already English"
                // so a translation error can't cascade into translating an
                // English-language decision through a pointless round trip.
                var translatedFromTag: String? = null
                if (sourceTag != null && !sourceTag.startsWith("en", ignoreCase = true)) {
                    if (SarvamApiClient.isConfigured()) {
                        try {
                            textForAnalysis = SarvamApiClient.translateToEnglish(transcript, sourceTag)
                            translatedFromTag = sourceTag
                            Log.i(TAG, "translate_to_english_success source=$sourceTag")
                            Log.i(TAG, "DIAG_transcript_after_translate text=${textForAnalysis.replace("\n", "\\n")}")
                        } catch (e: SarvamUnavailableException) {
                            Log.i(TAG, "translate_to_english_failed source=$sourceTag msg=${e.message}")
                        }
                    } else {
                        Log.i(TAG, "translate_to_english_skipped_not_configured source=$sourceTag")
                    }
                }
                val textAnalysis = app.prahariApiClient.analyzeVoice(textForAnalysis)
                Log.i(TAG, "DIAG_analyze_voice_result rawLabel=${textAnalysis.rawLabel} score=${textAnalysis.score} reason=${textAnalysis.reason}")
                val sessionAnalysis = app.prahariApiClient.analyzeSession(sessionId, textForAnalysis)
                val lookup = app.callerLookupSource.lookup(phoneNumber)
                val isTrustedContact = phoneNumber.isNotBlank() &&
                    app.settings.trustedContactPhone.isNotBlank() &&
                    normalizePhoneNumber(phoneNumber) == normalizePhoneNumber(app.settings.trustedContactPhone)
                val decision = DecisionAgent.decide(lookup, textAnalysis, sessionAnalysis, isTrustedContact)
                // Translate the decision back into the source language here,
                // once, right after it's built -- every downstream consumer
                // (WarningActivity's TTS speak() + on-screen text,
                // SafeResultActivity, AutoEscalationCountdownActivity) just
                // reads decision.headline/reasons already, so this is the
                // only place this needs wiring in, not each of them.
                // WarningActivity's ML-Kit language-id-driven voice selection
                // (CLAUDE.md Section 11.2) already picks the right TTS voice
                // for whatever script the text turns out to be in.
                val finalDecision = if (translatedFromTag != null) {
                    try {
                        val translatedHeadline = SarvamApiClient.translateFromEnglish(decision.headline, translatedFromTag)
                        val translatedReasons = decision.reasons.map {
                            SarvamApiClient.translateFromEnglish(it, translatedFromTag)
                        }
                        Log.i(TAG, "translate_from_english_success target=$translatedFromTag")
                        decision.copy(headline = translatedHeadline, reasons = translatedReasons)
                    } catch (e: SarvamUnavailableException) {
                        Log.i(TAG, "translate_from_english_failed target=$translatedFromTag msg=${e.message}")
                        decision
                    }
                } else {
                    decision
                }
                Log.i(TAG, "analysis_online_success elapsed_ms=${SystemClock.elapsedRealtime() - startMs}")
                routeToOutcome(finalDecision, phoneNumber, transcript)
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
