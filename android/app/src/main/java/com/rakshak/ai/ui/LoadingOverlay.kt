package com.rakshak.ai.ui

import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.TextView

/**
 * Drives the full-screen loading state shown while CheckCallActivity waits
 * on a Prahari call (bounded to ~5s now, see PrahariHttpApiClient) or —
 * near-instantly — the offline fallback. Pulses the wordmark (fade
 * 1.0<->0.4, looping) and rotates through a fixed set of reassuring phrases,
 * crossfading between them. Owns its own Handler/Animator lifecycle so the
 * caller only needs show()/hide() — no coroutine or animation plumbing
 * leaks into CheckCallActivity itself.
 */
class LoadingOverlay(
    private val overlayView: View,
    private val wordmarkView: View,
    private val phraseView: TextView,
    private val phrases: List<String>,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var pulseAnimator: ObjectAnimator? = null
    private var phraseIndex = 0

    private val rotatePhrase = object : Runnable {
        override fun run() {
            phraseIndex = (phraseIndex + 1) % phrases.size
            crossfadeTo(phrases[phraseIndex])
            handler.postDelayed(this, PHRASE_INTERVAL_MS)
        }
    }

    fun show() {
        overlayView.visibility = View.VISIBLE
        phraseIndex = 0
        phraseView.alpha = 1f
        phraseView.text = phrases.firstOrNull().orEmpty()

        pulseAnimator?.cancel()
        pulseAnimator = ObjectAnimator.ofFloat(wordmarkView, View.ALPHA, 1f, 0.4f).apply {
            duration = PULSE_DURATION_MS
            repeatMode = ValueAnimator.REVERSE
            repeatCount = ValueAnimator.INFINITE
            start()
        }

        handler.postDelayed(rotatePhrase, PHRASE_INTERVAL_MS)
    }

    fun hide() {
        overlayView.visibility = View.GONE
        pulseAnimator?.cancel()
        pulseAnimator = null
        wordmarkView.alpha = 1f
        handler.removeCallbacks(rotatePhrase)
    }

    private fun crossfadeTo(text: String) {
        phraseView.animate().alpha(0f).setDuration(FADE_MS).withEndAction {
            phraseView.text = text
            phraseView.animate().alpha(1f).setDuration(FADE_MS).start()
        }.start()
    }

    companion object {
        private const val PULSE_DURATION_MS = 900L
        private const val PHRASE_INTERVAL_MS = 2600L
        private const val FADE_MS = 220L
    }
}
