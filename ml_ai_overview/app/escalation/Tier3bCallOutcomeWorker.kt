package com.rakshak.ai.escalation

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.PhoneStateListener
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.RiskLevel
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withTimeoutOrNull

private const val TAG = "RakshakEscalation"

/**
 * Observes system call state right after a Tier 3b auto-dial to estimate
 * whether the call was likely answered.
 *
 * This is a HEURISTIC, not certain detection. Plain TelephonyManager call
 * state (IDLE/RINGING/OFFHOOK) does not distinguish "our outgoing call is
 * ringing at the far end" from "our outgoing call just connected" — both
 * report OFFHOOK. Real answered/unanswered detection needs an
 * InCallService/Connection binding, which means being (or being bound as)
 * the default dialer — that's Phase 3/4 per CLAUDE.md, not this feature.
 * Proxy used here: if the call returns to IDLE within
 * [SHORT_CALL_THRESHOLD_MS] of first going OFFHOOK, treat it as likely
 * unanswered (quick reject / busy / no answer); a longer OFFHOOK duration is
 * treated as likely answered. This is flagged as a heuristic in the report,
 * not claimed as ground truth.
 */
class Tier3bCallOutcomeWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    private class OutcomeObserved(val outcome: CallOutcome) : Exception()
    private data class CallOutcome(val offhookDurationMs: Long, val likelyAnswered: Boolean)

    override suspend fun doWork(): Result {
        if (ContextCompat.checkSelfPermission(applicationContext, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.w(TAG, "READ_PHONE_STATE not granted — cannot estimate Tier3b call outcome.")
            return Result.success()
        }

        val outcome = withTimeoutOrNull(OVERALL_TIMEOUT_MS) { observeCallOutcome() }
        if (outcome == null) {
            Log.w(TAG, "Tier3b call-outcome observation timed out with no clear signal — not triggering evidence agent.")
            return Result.success()
        }

        Log.i(
            TAG,
            "Tier3b call outcome: offhookDurationMs=${outcome.offhookDurationMs}, " +
                "likelyAnswered=${outcome.likelyAnswered} (heuristic, not certain)",
        )
        if (!outcome.likelyAnswered) {
            val phoneNumber = inputData.getString(KEY_PHONE_NUMBER).orEmpty()
            val transcript = inputData.getString(KEY_TRANSCRIPT)
            val riskLevel = RiskLevel.valueOf(inputData.getString(KEY_RISK_LEVEL) ?: RiskLevel.HIGH.name)
            val reasons = inputData.getStringArray(KEY_REASONS)?.toList().orEmpty()
            val decision = DecisionResult(riskLevel = riskLevel, headline = "", reasons = reasons, suspectedScamType = null)

            val app = applicationContext as RakshakApp
            MissedEscalationAgent(applicationContext).deliverEvidence(
                settings = app.settings,
                phoneNumber = phoneNumber,
                decision = decision,
                transcript = transcript,
                triggerReason = "tier3b_call_likely_unanswered",
            )
        }
        return Result.success()
    }

    private suspend fun observeCallOutcome(): CallOutcome {
        val tm = applicationContext.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        var offhookStartedAt = 0L
        var sawOffhook = false

        val flow = callbackFlow {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val callback = object : TelephonyCallback(), TelephonyCallback.CallStateListener {
                    override fun onCallStateChanged(state: Int) {
                        trySend(state)
                    }
                }
                tm.registerTelephonyCallback(applicationContext.mainExecutor, callback)
                awaitClose { tm.unregisterTelephonyCallback(callback) }
            } else {
                @Suppress("DEPRECATION")
                val listener = object : PhoneStateListener() {
                    @Suppress("DEPRECATION")
                    override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                        trySend(state)
                    }
                }
                @Suppress("DEPRECATION")
                tm.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
                awaitClose { @Suppress("DEPRECATION") tm.listen(listener, PhoneStateListener.LISTEN_NONE) }
            }
        }

        return try {
            flow.collect { state ->
                when {
                    state == TelephonyManager.CALL_STATE_OFFHOOK && !sawOffhook -> {
                        sawOffhook = true
                        offhookStartedAt = System.currentTimeMillis()
                    }
                    state == TelephonyManager.CALL_STATE_IDLE && sawOffhook -> {
                        val duration = System.currentTimeMillis() - offhookStartedAt
                        throw OutcomeObserved(CallOutcome(duration, duration >= SHORT_CALL_THRESHOLD_MS))
                    }
                }
            }
            CallOutcome(0, true)
        } catch (e: OutcomeObserved) {
            e.outcome
        }
    }

    companion object {
        const val KEY_PHONE_NUMBER = "phone_number"
        const val KEY_TRANSCRIPT = "transcript"
        const val KEY_RISK_LEVEL = "risk_level"
        const val KEY_REASONS = "reasons"

        private const val SHORT_CALL_THRESHOLD_MS = 8_000L
        private const val OVERALL_TIMEOUT_MS = 90_000L
    }
}
