package com.rakshak.ai.escalation

import android.content.Context
import java.io.File

/** Single source of truth for where NCRP evidence files live on-device —
 *  [IncidentSummaryPdf]'s generated PDF and [ScreenshotEvidenceStore]'s
 *  saved screenshot both write here, and NcrpComplaintActivity's file
 *  chooser reads from here. Everything in this directory is only ever
 *  offered to the user as a choice, never attached silently. */
object EvidenceFiles {
    private const val DIR_NAME = "ncrp_evidence"

    fun dir(context: Context): File = File(context.cacheDir, DIR_NAME).apply { mkdirs() }
}
