package com.rakshak.ai.callscreening

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.telecom.Call
import android.telecom.CallScreeningService
import android.telecom.CallScreeningService.CallResponse
import androidx.core.app.NotificationCompat
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.intelligence.DecisionAgent
import com.rakshak.ai.intelligence.DecisionResult
import com.rakshak.ai.intelligence.RiskLevel
import com.rakshak.ai.intelligence.normalizePhoneNumber
import com.rakshak.ai.ui.WarningActivity
import kotlinx.coroutines.runBlocking

/**
 * Pre-connect screening only — see CLAUDE.md Section 0/3. `Call.Details`
 * gives us the number and nothing else; no transcript exists at this point,
 * so the only signal available here is the (mocked) CNAP/Sanchar Saathi
 * lookup. This is also the one place in Phase 1 where the app has any real
 * call-control power: the `CallResponse` built below is the actual Tier-1
 * "silence" action, decided automatically because `onScreenCall` must
 * respond within a short window — there is no time to wait on a user tap.
 */
class RakshakCallScreeningService : CallScreeningService() {

    override fun onScreenCall(callDetails: Call.Details) {
        val number = callDetails.handle?.schemeSpecificPart.orEmpty()
        val app = application as RakshakApp

        val lookup = runBlocking { app.callerLookupSource.lookup(number) }
        val isTrustedContact = number.isNotBlank() &&
            app.settings.trustedContactPhone.isNotBlank() &&
            normalizePhoneNumber(number) == normalizePhoneNumber(app.settings.trustedContactPhone)
        val decision = DecisionAgent.decide(lookup, isTrustedContact = isTrustedContact)

        val autoSilenced = decision.riskLevel == RiskLevel.HIGH
        val response = CallResponse.Builder()
            .setDisallowCall(false)   // never hard-block: false positives must still get through
            .setRejectCall(false)
            .setSilenceCall(autoSilenced)
            .setSkipNotification(false)
            .build()
        respondToCall(callDetails, response)

        // Silent for LOW risk (Section 9.2 — "invisible during normal calls").
        if (decision.riskLevel != RiskLevel.LOW) {
            showWarning(number, decision, autoSilenced)
        }
    }

    private fun showWarning(
        number: String,
        decision: DecisionResult,
        autoSilenced: Boolean,
    ) {
        ensureChannel()

        val fullScreenIntent = WarningActivity.buildIntent(this, number, decision, autoSilenced)
        val pendingIntent = PendingIntent.getActivity(
            this,
            number.hashCode(),
            fullScreenIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.warning_notification_title))
            .setContentText(decision.headline)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setFullScreenIntent(pendingIntent, true)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        val nm = getSystemService(NotificationManager::class.java)
        nm.notify(number.hashCode(), notification)
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.warning_channel_name),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = getString(R.string.warning_channel_description)
        }
        nm.createNotificationChannel(channel)
    }

    companion object {
        private const val CHANNEL_ID = "rakshak_call_warnings"
    }
}
