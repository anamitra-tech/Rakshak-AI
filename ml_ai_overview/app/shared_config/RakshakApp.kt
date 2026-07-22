package com.rakshak.ai

import android.app.Application
import android.speech.tts.TextToSpeech
import android.util.Log
import com.rakshak.ai.intelligence.CallerLookupSource
import com.rakshak.ai.intelligence.MlScamScorer
import com.rakshak.ai.intelligence.MockCallerLookupSource
import com.rakshak.ai.intelligence.PrahariApiClient
import com.rakshak.ai.intelligence.PrahariHttpApiClient
import com.rakshak.ai.settings.AppSettings

private const val TAG = "RakshakApp"
private const val TTS_WARMUP_UTTERANCE_ID = "rakshak_app_tts_warmup"
private const val TTS_WARMUP_SILENCE_MS = 300L

/**
 * Wires the interfaces to their Phase 1 implementations in one place, so
 * swapping `MockCallerLookupSource` for a real CNAP/Sanchar Saathi client
 * later is a one-line change here — nothing else in the app constructs these
 * directly.
 */
class RakshakApp : Application() {

    lateinit var settings: AppSettings
        private set

    lateinit var callerLookupSource: CallerLookupSource
        private set

    lateinit var prahariApiClient: PrahariApiClient
        private set

    /**
     * Constructed once, here, as early as the process allows — before any
     * Activity even exists — and shared by every screen that speaks
     * (WarningActivity, AutoEscalationCountdownActivity) instead of each
     * constructing its own. TextToSpeech's onInit binding + first-utterance
     * warm-up was measured taking multiple seconds; doing that per-Activity
     * meant the delay was visible every single time a warning fired, right
     * when the user most needed to hear it immediately. Doing it once at
     * process start instead means that, by the time any real warning fires
     * — which requires the user to have already opened the app, navigated a
     * screen, typed/pasted text, and waited on a network round-trip — the
     * engine has almost always long since finished binding in the
     * background.
     */
    lateinit var tts: TextToSpeech
        private set

    var ttsReady: Boolean = false
        private set

    /** True once the init callback has run at all, success or failure —
     *  distinct from [ttsReady], which is only true on success. Lets
     *  [onTtsReady] fire immediately for a late registration even after a
     *  failed init, instead of waiting forever for a success that will
     *  never come. */
    private var ttsInitAttempted = false

    private val ttsReadyListeners = mutableListOf<() -> Unit>()

    override fun onCreate() {
        super.onCreate()
        settings = AppSettings(this)
        callerLookupSource = MockCallerLookupSource()
        prahariApiClient = PrahariHttpApiClient(settings.prahariBaseUrl)

        tts = TextToSpeech(this) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            ttsInitAttempted = true
            Log.i(TAG, "app_tts_init status=$status ready=$ttsReady")
            if (ttsReady) {
                // Same cold-audio-pipeline precaution as before, just fired
                // once at process start now instead of per-Activity.
                tts.playSilentUtterance(TTS_WARMUP_SILENCE_MS, TextToSpeech.QUEUE_FLUSH, TTS_WARMUP_UTTERANCE_ID)
            }
            val pending = ttsReadyListeners.toList()
            ttsReadyListeners.clear()
            pending.forEach { it() }
        }
    }

    /**
     * Registers [callback] to run once the shared TTS engine's init attempt
     * has finished — immediately, if it already has by the time this is
     * called. Fires exactly once per registration, on success OR failure;
     * callers must check [ttsReady] themselves inside [callback] rather than
     * assuming success.
     */
    fun onTtsReady(callback: () -> Unit) {
        if (ttsInitAttempted) callback() else ttsReadyListeners += callback
    }

    /** Call after the user changes the Prahari base URL in settings. */
    fun refreshPrahariClient() {
        prahariApiClient = PrahariHttpApiClient(settings.prahariBaseUrl)
    }

    /**
     * Loaded lazily on first use, not at process start — this is only ever
     * read from the Prahari-unreachable fallback path (see
     * CheckCallActivity), which most sessions never hit, so there's no
     * reason to pay the parse cost (~6700 vocabulary entries) on every app
     * launch. `null` on any load failure (missing/corrupt asset) rather than
     * crashing — OfflineEvaluator already degrades to rules-only scoring
     * when handed a null model, same "never appear to hang or crash on a
     * failed dependency" posture as the rest of the offline fallback.
     */
    val offlineMlModel: MlScamScorer.Model? by lazy {
        try {
            assets.open("scam_model.txt").bufferedReader(Charsets.UTF_8).use {
                MlScamScorer.parseModel(it.readText())
            }
        } catch (e: Exception) {
            Log.e(TAG, "offline_ml_model_load_failed", e)
            null
        }
    }
}
