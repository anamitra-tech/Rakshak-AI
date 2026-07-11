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
 * near-instantly — the offline fallback. Continuously rotates the radar-
 * sweep ImageView (radar_sweep.xml over the static radar_rings.xml — see
 * loading_overlay.xml) and rotates through a fixed set of reassuring
 * phrases, crossfading between them. Owns its own Handler/Animator
 * lifecycle so the caller only needs show()/hide() — no coroutine or
 * animation plumbing leaks into CheckCallActivity itself.
 */
class LoadingOverlay(
    private val overlayView: View,
    private val radarSweepView: View,
    private val phraseView: TextView,
    private val phrases: List<String>,
) {
    private val handler = Handler(Looper.getMainLooper())
    private var sweepAnimator: ObjectAnimator? = null
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

        sweepAnimator?.cancel()
        radarSweepView.rotation = 0f
        sweepAnimator = ObjectAnimator.ofFloat(radarSweepView, View.ROTATION, 0f, 360f).apply {
            duration = SWEEP_DURATION_MS
            interpolator = null // linear -- a radar sweep should not ease in/out
            repeatMode = ValueAnimator.RESTART
            repeatCount = ValueAnimator.INFINITE
            start()
        }

        handler.postDelayed(rotatePhrase, PHRASE_INTERVAL_MS)
    }

    fun hide() {
        overlayView.visibility = View.GONE
        sweepAnimator?.cancel()
        sweepAnimator = null
        radarSweepView.rotation = 0f
        handler.removeCallbacks(rotatePhrase)
    }

    private fun crossfadeTo(text: String) {
        phraseView.animate().alpha(0f).setDuration(FADE_MS).withEndAction {
            phraseView.text = text
            phraseView.animate().alpha(1f).setDuration(FADE_MS).start()
        }.start()
    }

    companion object {
        private const val SWEEP_DURATION_MS = 2000L
        private const val PHRASE_INTERVAL_MS = 2600L
        private const val FADE_MS = 220L
    }
}
