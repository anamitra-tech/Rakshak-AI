package com.rakshak.ai.stt

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.io.File
import java.io.IOException

/**
 * Records a short raw-audio clip to a temp file for upload to Sarvam's
 * speech-to-text (see [com.rakshak.ai.sarvam.SarvamApiClient]) — the online
 * fallback used only when Android's on-device [VoiceInputHelper] can't
 * handle the configured language (or the device can't do on-device
 * recognition at all). Records AAC-in-MP4 (.m4a, "audio/mp4") — a format
 * Prahari's own server-side Sarvam integration (webhook/app.py's
 * `_AUDIO_MIME_TO_EXT`) already maps and has exercised against the same
 * Sarvam endpoint.
 *
 * Caps recording at [MAX_DURATION_MS] (120s). Uploads now go through
 * Prahari's own `/stt/sarvam` (webhook/app.py), which transparently falls
 * back to Sarvam's async batch-job API for anything over the sync
 * endpoint's ~30s limit (see `_transcribe_audio_sarvam`'s doc comment) — so
 * this cap is just a sane upper bound for "a spoken phrase on this screen",
 * not a hard technical ceiling the way it was before that proxying was
 * wired up (real bug: recordings used to fail outright past ~25s with no
 * fallback at all, since only the sync endpoint was ever reachable
 * directly from Android).
 */
class SarvamVoiceRecorder(private val context: Context) {

    interface Callback {
        fun onMaxDurationReached()
    }

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null
    private val handler = Handler(Looper.getMainLooper())
    private var maxDurationRunnable: Runnable? = null

    fun startRecording(callback: Callback): Boolean {
        stopAndDiscard()
        val file = try {
            File.createTempFile("sarvam_voice_", ".m4a", context.cacheDir)
        } catch (e: IOException) {
            Log.e(TAG, "temp_file_create_failed", e)
            return false
        }
        val mediaRecorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }
        return try {
            mediaRecorder.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioSamplingRate(16000)
                setOutputFile(file.absolutePath)
                prepare()
                start()
            }
            recorder = mediaRecorder
            outputFile = file
            val runnable = Runnable { callback.onMaxDurationReached() }
            maxDurationRunnable = runnable
            handler.postDelayed(runnable, MAX_DURATION_MS)
            true
        } catch (e: Exception) {
            Log.e(TAG, "start_recording_failed", e)
            mediaRecorder.release()
            file.delete()
            recorder = null
            outputFile = null
            false
        }
    }

    /** Returns the recorded file on success, or null if nothing was
     *  recorded/recording failed to stop cleanly. Caller owns deleting the
     *  file once the upload attempt (success or failure) is done. */
    fun stopRecording(): File? {
        maxDurationRunnable?.let { handler.removeCallbacks(it) }
        maxDurationRunnable = null
        val file = outputFile
        val r = recorder
        recorder = null
        outputFile = null
        if (r == null) return null
        return try {
            r.stop()
            r.release()
            file
        } catch (e: Exception) {
            Log.e(TAG, "stop_recording_failed", e)
            r.release()
            file?.delete()
            null
        }
    }

    /** Discards any in-progress recording without returning a file — used
     *  when the user cancels or a new recording is about to start. */
    fun stopAndDiscard() {
        maxDurationRunnable?.let { handler.removeCallbacks(it) }
        maxDurationRunnable = null
        val r = recorder
        val file = outputFile
        recorder = null
        outputFile = null
        if (r != null) {
            try {
                r.stop()
            } catch (e: Exception) {
                // Not yet started or already stopped -- fine, we're discarding anyway.
            }
            r.release()
        }
        file?.delete()
    }

    companion object {
        private const val TAG = "SarvamVoiceRecorder"
        private const val MAX_DURATION_MS = 120_000L
    }
}
