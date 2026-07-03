package com.rakshak.ai

import android.app.Application
import com.rakshak.ai.intelligence.CallerLookupSource
import com.rakshak.ai.intelligence.MockCallerLookupSource
import com.rakshak.ai.intelligence.PrahariApiClient
import com.rakshak.ai.intelligence.PrahariHttpApiClient
import com.rakshak.ai.settings.AppSettings

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

    override fun onCreate() {
        super.onCreate()
        settings = AppSettings(this)
        callerLookupSource = MockCallerLookupSource()
        prahariApiClient = PrahariHttpApiClient(settings.prahariBaseUrl)
    }

    /** Call after the user changes the Prahari base URL in settings. */
    fun refreshPrahariClient() {
        prahariApiClient = PrahariHttpApiClient(settings.prahariBaseUrl)
    }
}
