package com.rakshak.ai.ui

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import com.rakshak.ai.databinding.ActivityFsiSetupBinding

/**
 * One-time setup step (CLAUDE.md Section 9.2 — configuration is a
 * family-member task, never re-litigated mid-use): on Android 14+,
 * USE_FULL_SCREEN_INTENT is a special app-op that is NOT auto-granted at
 * install despite being declared in the manifest, so without this screen a
 * risky-call warning could silently degrade to a heads-up banner instead of
 * the full-screen alert. [MainActivity] launches this only from onCreate
 * (not onResume) when the permission is missing, so it surfaces once per
 * cold start rather than trapping the user in a loop if they back out.
 */
class FullScreenIntentSetupActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFsiSetupBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFsiSetupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.fsiOpenSettingsButton.setOnClickListener { openSettings() }
    }

    override fun onResume() {
        super.onResume()
        if (NotificationManagerCompat.from(this).canUseFullScreenIntent()) {
            finish()
        }
    }

    private fun openSettings() {
        binding.fsiWaitingText.visibility = View.VISIBLE
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT).apply {
                data = Uri.fromParts("package", packageName, null)
            }
        } else {
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.fromParts("package", packageName, null)
            }
        }
        startActivity(intent)
    }
}
