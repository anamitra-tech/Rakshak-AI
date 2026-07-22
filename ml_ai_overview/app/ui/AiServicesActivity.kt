package com.rakshak.ai.ui

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.rakshak.ai.R
import com.rakshak.ai.databinding.ActivityAiServicesBinding
import com.rakshak.ai.sarvam.SarvamApiClient

/**
 * Read-only transparency screen: what AI/cloud services this app actually
 * uses, and what each one costs. Product ask was to stop the free-vs-paid
 * story living only in code comments (llm/client.py's Gemini -> Groq ->
 * Ollama fallback chain, SarvamApiClient's free-trial-then-billed posture)
 * and put it somewhere a family member setting the app up can actually
 * read. Purely informational for now — no toggle to force a provider; that's
 * a separate, optional feature if wanted later (see the task this was built
 * for).
 *
 * Every status line here mirrors real code, not aspirational copy:
 * - Gemini/Groq/Ollama order and model names come straight from
 *   llm/client.py's generate() (Gemini 2.5 Flash, 3 retries -> Groq
 *   llama-3.1-8b-instant -> Ollama gemma3, in that order).
 * - Sarvam's "no live balance" note is real, not a shortcut: Sarvam's public
 *   docs (docs.sarvam.ai) point to their web dashboard for credit tracking
 *   and don't expose a REST endpoint for it, confirmed by search before
 *   writing this screen -- so [sarvamConfiguredText] only reports whether
 *   this build has a key at all ([SarvamApiClient.isConfigured], a real,
 *   local, instant check), not a live balance that doesn't exist to query.
 * - OCR's "always free" claim is real too: on-device ML Kit costs nothing
 *   per use, and the cloud fallback (CloudOcrClient) hits this project's own
 *   self-hosted Tesseract endpoint, not a paid third-party OCR API (GCP
 *   Vision was ruled out early for exactly this reason -- see
 *   CloudOcrClient's own doc comment).
 *
 * Deliberately does NOT live-ping api.server/webhook.app to report which
 * engine last actually served a request -- that would need a real network
 * call (cost, latency, another failure mode to handle) just to populate an
 * informational screen, disproportionate to a static "here's the pricing
 * model" ask. The one live check kept ([SarvamApiClient.isConfigured]) is
 * free, synchronous, and already computed elsewhere in the app.
 */
class AiServicesActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val binding = ActivityAiServicesBinding.inflate(layoutInflater)
        setContentView(binding.root)
        title = getString(R.string.ai_services_title)

        binding.sarvamConfiguredText.setText(
            if (SarvamApiClient.isConfigured()) {
                R.string.ai_services_sarvam_configured_yes
            } else {
                R.string.ai_services_sarvam_configured_no
            }
        )
    }
}
