package com.rakshak.ai.ui

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.widget.Toast
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
                // Now mode="transcribe" (native script), not mode="translate"
                // -- no reliable source-language metadata from this path (Saaras
                // auto-detects the spoken language itself, same as before), so
                // leave this null and let runAnalysis's SarvamLanguageCodes
                // .detectNativeScriptTag content-based detection resolve the
                // real script from the transcript text itself, same as typed/
                // pasted native-language input already does.
                transcriptSourceLanguageTag = null
                binding.voiceStatusText.visibility = View.GONE
                Log.i(TAG, "sarvam_stt_success")
            } catch (e: SarvamUnavailableException) {
                Log.i(TAG, "sarvam_stt_failed quotaExceeded=${e.quotaExceeded} msg=${e.message}")
                showVoiceStatus(
                    getString(
                        if (e.quotaExceeded) R.string.check_call_voice_quota_exceeded
                        else R.string.check_call_voice_sarvam_failed
                    )
                )
            } finally {
                file.delete()
            }
        }
    }

    private fun showVoiceStatus(message: String) {
        binding.voiceStatusText.text = message
        binding.voiceStatusText.visibility = View.VISIBLE
    }

    /** Translation is a supporting step, not a user-facing input method
     *  (unlike voice/screenshot), so a full status banner would be
     *  disproportionate — but staying fully silent isn't right either now
     *  that the AI Services screen tells users this can happen. A Toast is
     *  the middle ground: visible, non-blocking, doesn't compete with the
     *  one-button-during-a-warning rule (CLAUDE.md 9.2) since this fires
     *  before any warning card exists yet. */
    private fun showQuotaExceededToast() {
        Toast.makeText(this, R.string.check_call_translate_quota_exceeded, Toast.LENGTH_LONG).show()
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
     * all).
     *
     * 2026-07-18: re-wired [CloudOcrClient] back in for 7 of these 9
     * (Bengali/Gujarati/Kannada/Malayalam/Punjabi/Odia/Urdu) — product
     * decision to accept the audit's "under-called to SUSPICIOUS, not
     * FRAUD" degradation for those, since it's a real but bounded miss, not
     * a silent one. Telugu and Tamil stay redirect-only: the same audit
     * found those two score an outright false negative (SAFE) on a real
     * scam script, a materially worse failure than under-scoring. Urdu is
     * re-enabled here too despite a distinctly worse failure mode than the
     * other 6 in the same audit (84% character-error-rate OCR bad enough
     * that translating it hallucinated a fabricated, unrelated story, not
     * just a mistranslation) — flagged, not silently carried over, since
     * that risk doesn't go away just because Urdu wasn't named as a
     * concern. Same per-language gate as webhook/app.py's
     * `_OCR_RELIABLE_LANGUAGES` for WhatsApp — keep both in sync.
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
                val tag = app.settings.spokenLanguageTag
                // Telugu/Tamil stay redirect-only -- see handlePickedScreenshot's
                // doc comment: the audit found these two score an outright
                // false negative (SAFE), not just under-called, on OCR.
                if (tag.startsWith("te", ignoreCase = true) || tag.startsWith("ta", ignoreCase = true)) {
                    Log.i(TAG, "ocr_skipped_unreliable_language tag=$tag")
                    showScreenshotStatus(
                        getString(R.string.check_call_screenshot_ocr_unreliable, ocrUnreliableLanguageName(tag))
                    )
                    return
                }
                if (!hasActiveNetworkConnection(this@CheckCallActivity)) {
                    Log.i(TAG, "cloud_ocr_skipped_no_network tag=$tag")
                    showScreenshotStatus(getString(R.string.check_call_screenshot_ocr_unreliable, ocrUnreliableLanguageName(tag)))
                    return
                }
                Log.i(TAG, "cloud_ocr_attempt tag=$tag")
                CloudOcrClient.recognizeText(this@CheckCallActivity, uri, app.settings.evidenceBaseUrl, tag, object : CloudOcrClient.Callback {
                    override fun onSuccess(text: String) {
                        Log.i(TAG, "DIAG_cloud_ocr_extracted_text tag=$tag text=${text.replace("\n", "\\n")}")
                        binding.transcriptInput.setText(text)
                        binding.transcriptInput.setSelection(text.length)
                        // No matchedScript signal from CloudOcrClient (unlike
                        // ScreenshotOcrHelper's on-device path) -- leave null and
                        // let runAnalysis's content-based detectNativeScriptTag
                        // resolve the real script from the text itself, same
                        // as the native-transcribe voice-input path does.
                        transcriptSourceLanguageTag = null
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
        })
    }

    private fun showScreenshotStatus(message: String) {
        binding.screenshotStatusText.text = message
        binding.screenshotStatusText.visibility = View.VISIBLE
    }

    /** English display name for [R.string.check_call_screenshot_ocr_unreliable]'s
     *  placeholder -- only reachable for the 9 tags [ScreenshotOcrHelper.scriptFamilyFor]
     *  maps to [ScreenshotOcrHelper.ScriptFamily.NONE] (see CLAUDE.md Section 13's
     *  table); English/Hindi/Marathi never reach this callback at all. */
    private fun ocrUnreliableLanguageName(tag: String): String = when {
        tag.startsWith("bn", ignoreCase = true) -> "Bengali"
        tag.startsWith("gu", ignoreCase = true) -> "Gujarati"
        tag.startsWith("kn", ignoreCase = true) -> "Kannada"
        tag.startsWith("ml", ignoreCase = true) -> "Malayalam"
        tag.startsWith("pa", ignoreCase = true) -> "Punjabi"
        tag.startsWith("or", ignoreCase = true) -> "Odia"
        tag.startsWith("te", ignoreCase = true) -> "Telugu"
        tag.startsWith("ta", ignoreCase = true) -> "Tamil"
        tag.startsWith("ur", ignoreCase = true) -> "Urdu"
        else -> "this language"
    }

    override fun onDestroy() {
        voiceInput.stopListening()
        sarvamRecorder.stopAndDiscard()
        super.onDestroy()
    }

    /**
     * Cleans OCR text before it's handed to Sarvam's translate -- real bug
     * traced live with a Tamil malware-attachment test: Sarvam's Tamil
     * translation reliably (reproduced 3/3) dropped the sentence's trailing
     * action verb ("forward"/"send" -- Tamil is SOV, so the verb sits at
     * the very end) whenever either (a) OCR noise (misread icons/filename/
     * timestamp fragments) was present anywhere in the same translate call,
     * or (b) the real sentence's own line-wrap newlines were sent as
     * literal '\n' rather than spaces -- confirmed independently for each
     * factor, and confirmed the combination below fixes the real failing
     * case (and doesn't change output for Hindi/Bengali/Telugu, verified
     * against every OCR sample captured this session).
     *
     * Noise removal exploits a real, observed OCR-layout artifact: a
     * genuine multi-line sentence Tesseract/ML Kit could actually read
     * comes back as a tightly-packed block with no blank lines between its
     * wrapped lines, while misread fragments it couldn't group into that
     * block each come back as their own isolated single-line "paragraph"
     * surrounded by blank lines. Dropping isolated single-line paragraphs
     * (only when at least one multi-line block exists to prefer) removes
     * the noise without needing to guess at what counts as "real text" --
     * Hindi/Bengali's OCR output here never had blank-line breaks at all,
     * so this step is a no-op for them.
     *
     * Real bug fixed 2026-07-15, traced live with a Punjabi test: Tesseract
     * doesn't always put a blank line between OCR noise (header digits/
     * symbols) and the real sentence -- here it grouped 3 noise lines
     * together with the first real line into a single multi-line
     * "paragraph", so the isolated-single-line check above couldn't isolate
     * them. That noise (near-zero real letters -- Gurmukhi digits and
     * symbols aren't Unicode letters) survived into the translate call and
     * Sarvam's translation dropped the object pronoun ("Forward to the
     * Finance Manager" instead of "Forward this to..."), which no longer
     * matched ml.detector's malware_attachment_delivery pattern. Now also
     * drops individual lines within an already-kept multi-line paragraph
     * if they have fewer than 3 real letters (any script) -- verified
     * against every OCR sample captured this session: removes exactly the
     * 3 noise lines from the Punjabi case, changes nothing for
     * Hindi/Bengali/Telugu/Tamil since every real sentence line in those
     * samples has far more than 3 letters.
     */
    private fun prepareForTranslation(text: String): String {
        val paragraphs = text.split(Regex("\n\\s*\n+")).map { it.trim() }.filter { it.isNotEmpty() }
        val candidate = if (paragraphs.size <= 1) {
            text
        } else {
            val multiLineParagraphs = paragraphs.filter { it.lines().size > 1 }
            if (multiLineParagraphs.isEmpty()) {
                text
            } else {
                multiLineParagraphs.joinToString("\n\n") { paragraph ->
                    val lines = paragraph.lines()
                    val keptLines = lines.filter { line -> line.count { it.isLetter() } >= 3 }
                    if (keptLines.isEmpty()) paragraph else keptLines.joinToString("\n")
                }
            }
        }
        return candidate.replace(Regex("\\s+"), " ").trim()
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
                // Real bug traced live: ScreenshotOcrHelper's on-device
                // recognizers don't reject text that isn't actually in the
                // script they're modeled for -- ML Kit's Devanagari
                // recognizer, tried first because the phone was still
                // configured for Hindi from an earlier test, happily
                // returned real, non-empty BENGALI text for a Bengali
                // screenshot instead of coming back empty. That mislabeled
                // transcriptSourceLanguageTag as "hi-IN" even though the
                // extracted characters were genuinely Bengali, which sent
                // the wrong source language to Sarvam's translate (silently
                // passed the text through untranslated) AND translated the
                // reply back into the wrong language. The actual Unicode
                // content of the text is ground truth here, not which
                // recognizer/metadata claimed to have matched -- so content
                // detection now overrides OCR/voice metadata whenever it
                // finds a native script at all, falling back to the
                // metadata tag only for pure-Latin text (where content
                // detection has nothing to go on, e.g. genuine English OCR
                // or Sarvam STT's mode=translate output).
                val contentDetectedTag = SarvamLanguageCodes.detectNativeScriptTag(transcript)
                val sourceTag = when {
                    contentDetectedTag == null -> transcriptSourceLanguageTag
                    // detectNativeScriptTag can't distinguish Marathi from
                    // Hindi (both Devanagari) -- preserve the existing
                    // disambiguation-by-configured-language for that one
                    // pair, same as the OCR-metadata path used to do.
                    contentDetectedTag == "hi-IN" && app.settings.spokenLanguageTag.startsWith("mr", ignoreCase = true) -> "mr-IN"
                    else -> contentDetectedTag
                }
                Log.i(TAG, "DIAG_source_tag_resolved metadataTag=$transcriptSourceLanguageTag contentDetectedTag=$contentDetectedTag resolvedTag=$sourceTag")
                // Set only once translateToEnglish actually succeeds -- used
                // below to translate the decision's headline/reasons back for
                // display+speech. Left null on failure or "already English"
                // so a translation error can't cascade into translating an
                // English-language decision through a pointless round trip.
                var translatedFromTag: String? = null
                if (sourceTag != null && !sourceTag.startsWith("en", ignoreCase = true)) {
                    if (SarvamApiClient.isConfigured()) {
                        try {
                            val preparedTranscript = prepareForTranslation(transcript)
                            Log.i(TAG, "DIAG_prepared_for_translate text=${preparedTranscript.replace("\n", "\\n")}")
                            textForAnalysis = SarvamApiClient.translateToEnglish(preparedTranscript, sourceTag)
                            translatedFromTag = sourceTag
                            Log.i(TAG, "translate_to_english_success source=$sourceTag")
                            Log.i(TAG, "DIAG_transcript_after_translate text=${textForAnalysis.replace("\n", "\\n")}")
                        } catch (e: SarvamUnavailableException) {
                            Log.i(TAG, "translate_to_english_failed quotaExceeded=${e.quotaExceeded} source=$sourceTag msg=${e.message}")
                            if (e.quotaExceeded) showQuotaExceededToast()
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
                        Log.i(TAG, "translate_from_english_failed quotaExceeded=${e.quotaExceeded} target=$translatedFromTag msg=${e.message}")
                        if (e.quotaExceeded) showQuotaExceededToast()
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
