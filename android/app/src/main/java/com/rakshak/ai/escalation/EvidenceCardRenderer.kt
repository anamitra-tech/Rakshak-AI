package com.rakshak.ai.escalation

import android.graphics.Color
import android.graphics.pdf.PdfDocument
import android.text.StaticLayout
import android.text.TextPaint
import java.io.ByteArrayOutputStream

/**
 * Renders the same structured facts as [ComplaintDraft] into a short,
 * single-page PDF — an "evidence card" a family member can actually open and
 * read on any device, not just raw SMS text. Uses android.graphics.pdf
 * (built into the SDK, no new dependency).
 */
object EvidenceCardRenderer {

    private const val PAGE_WIDTH = 595  // A4 @ 72dpi
    private const val PAGE_HEIGHT = 842
    private const val MARGIN = 40

    fun renderPdf(title: String, bodyText: String): ByteArray {
        val document = PdfDocument()
        val pageInfo = PdfDocument.PageInfo.Builder(PAGE_WIDTH, PAGE_HEIGHT, 1).create()
        val page = document.startPage(pageInfo)
        val canvas = page.canvas

        val titlePaint = TextPaint().apply {
            isAntiAlias = true
            textSize = 18f
            isFakeBoldText = true
            color = Color.BLACK
        }
        val bodyPaint = TextPaint().apply {
            isAntiAlias = true
            textSize = 11f
            color = Color.BLACK
        }

        canvas.drawText(title, MARGIN.toFloat(), MARGIN.toFloat(), titlePaint)

        val availableWidth = PAGE_WIDTH - 2 * MARGIN
        val layout = StaticLayout.Builder.obtain(bodyText, 0, bodyText.length, bodyPaint, availableWidth)
            .setLineSpacing(4f, 1.1f)
            .build()

        canvas.save()
        canvas.translate(MARGIN.toFloat(), (MARGIN + 30).toFloat())
        layout.draw(canvas)
        canvas.restore()

        document.finishPage(page)

        val output = ByteArrayOutputStream()
        document.writeTo(output)
        document.close()
        return output.toByteArray()
    }
}
