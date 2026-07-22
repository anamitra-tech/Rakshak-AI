package com.rakshak.ai.escalation

import android.content.Context
import android.net.Uri
import android.util.Log
import java.io.File
import java.io.FileOutputStream

/**
 * Saves the original image a user picks on "Check a call/message" (via
 * "Upload screenshot") into the same evidence folder [IncidentSummaryPdf]
 * writes to, so NcrpComplaintActivity's file-chooser dialog can offer the
 * real screenshot as an evidence option — not just the generated summary.
 * CheckCallActivity and NcrpComplaintActivity never talk to each other
 * directly for this; a well-known on-disk location is the handoff.
 */
object ScreenshotEvidenceStore {
    private const val TAG = "ScreenshotEvidenceStore"
    private const val FILE_STEM = "user_screenshot"

    /** Copies [sourceUri]'s bytes into the evidence folder, replacing
     *  whatever screenshot (if any, regardless of its extension) was saved
     *  by a previous call — only one "the screenshot the user picked" is
     *  kept at a time, matching [IncidentSummaryPdf]'s single-file
     *  approach. Returns the saved file, or null if the copy failed. */
    fun save(context: Context, sourceUri: Uri): File? {
        return try {
            val extension = extensionFor(context.contentResolver.getType(sourceUri))
            val dir = EvidenceFiles.dir(context)
            dir.listFiles { f -> f.name.startsWith(FILE_STEM) }?.forEach { it.delete() }
            val destFile = File(dir, "$FILE_STEM.$extension")
            val input = context.contentResolver.openInputStream(sourceUri) ?: return null
            input.use { source -> FileOutputStream(destFile).use { output -> source.copyTo(output) } }
            destFile
        } catch (e: Exception) {
            Log.e(TAG, "screenshot_save_failed", e)
            null
        }
    }

    /** Whatever [save] most recently wrote, if anything — used by
     *  NcrpComplaintActivity to decide whether to offer this as a
     *  file-chooser option at all. */
    fun find(context: Context): File? =
        EvidenceFiles.dir(context).listFiles { f -> f.name.startsWith(FILE_STEM) }?.firstOrNull()

    private fun extensionFor(mimeType: String?): String = when {
        mimeType == null -> "jpg"
        mimeType.contains("png") -> "png"
        mimeType.contains("webp") -> "webp"
        else -> "jpg"
    }
}
