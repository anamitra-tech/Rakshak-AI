package com.rakshak.ai.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.View

/**
 * Purely visual countdown ring — no text required to understand it. Starts
 * as a full circle and shrinks clockwise from the top as [progress] falls
 * from 1f (all time left) to 0f (time's up). Used by
 * [AutoEscalationCountdownActivity]; CLAUDE.md 9.2 — must not depend on
 * reading anything.
 */
class ShrinkingCircleView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = 28f
        color = Color.WHITE
        strokeCap = Paint.Cap.ROUND
    }

    /** 1f = full circle (countdown just started), 0f = empty (time's up). */
    var progress: Float = 1f
        set(value) {
            field = value.coerceIn(0f, 1f)
            invalidate()
        }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val size = minOf(width, height).toFloat()
        val inset = paint.strokeWidth / 2
        val rect = RectF(inset, inset, size - inset, size - inset)
        canvas.drawArc(rect, -90f, 360f * progress, false, paint)
    }
}
