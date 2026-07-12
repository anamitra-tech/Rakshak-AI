package com.rakshak.ai.escalation

import android.content.Context
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.net.Uri
import android.text.Layout
import android.text.StaticLayout
import android.text.TextPaint
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream

/**
 * Renders [ComplaintDraft]'s text — the same content already shown in-app and
 * sent in the Tier 2 SMS — as a simple, paginated PDF, so it can be offered
 * as a ready-made evidence attachment on NCRP's own upload control. This is
 * a fallback/convenience option offered alongside the user's own files, never
 * a silent substitute — see NcrpComplaintActivity's file-chooser dialog.
 */
object IncidentSummaryPdf {

    private const val PAGE_WIDTH = 595 // A4 at 72dpi
    private const val PAGE_HEIGHT = 842
    private const val MARGIN = 40f
    private const val LINE_SPACING_EXTRA = 4f

    fun generate(context: Context, title: String, bodyText: String): Uri {
        val titlePaint = TextPaint().apply {
            textSize = 14f
            isAntiAlias = true
            typeface = Typeface.DEFAULT_BOLD
        }
        val bodyPaint = TextPaint().apply {
            textSize = 11f
            isAntiAlias = true
        }
        val contentWidth = (PAGE_WIDTH - 2 * MARGIN).toInt()

        val document = PdfDocument()
        var pageNumber = 1
        var page = document.startPage(PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, pageNumber).create())
        var canvas = page.canvas
        var y = MARGIN

        fun startNewPage() {
            document.finishPage(page)
            pageNumber++
            page = document.startPage(PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, pageNumber).create())
            canvas = page.canvas
            y = MARGIN
        }

        fun drawLine(rawText: String, paint: TextPaint) {
            val safeText = rawText.ifEmpty { " " }
            val layout = StaticLayout.Builder.obtain(safeText, 0, safeText.length, paint, contentWidth)
                .setAlignment(Layout.Alignment.ALIGN_NORMAL)
                .build()
            if (y + layout.height > PAGE_HEIGHT - MARGIN) startNewPage()
            canvas.save()
            canvas.translate(MARGIN, y)
            layout.draw(canvas)
            canvas.restore()
            y += layout.height + LINE_SPACING_EXTRA
        }

        drawLine(title, titlePaint)
        y += LINE_SPACING_EXTRA
        bodyText.split("\n").forEach { drawLine(it, bodyPaint) }
        document.finishPage(page)

        val file = File(EvidenceFiles.dir(context), "incident_summary.pdf")
        FileOutputStream(file).use { document.writeTo(it) }
        document.close()

        return FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
    }
}
