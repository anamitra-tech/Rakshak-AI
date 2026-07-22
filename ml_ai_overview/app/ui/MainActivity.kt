package com.rakshak.ai.ui

import android.Manifest
import android.app.role.RoleManager
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityMainBinding

/**
 * Home screen: request the CALL_SCREENING role (no manifest permission — a
 * role grant the user approves via the system's own UI) and jump to the
 * manual "Check a call/message" screen. Nothing here runs unattended; this
 * activity is the one-time/occasional setup surface, not something an
 * elderly user needs to open during a call.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val roleRequestLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        updateRoleStatus()
    }

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* no-op: the warning card just won't show if this is denied */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.requestRoleButton.setOnClickListener { requestCallScreeningRole() }
        binding.checkCallButton.setOnClickListener {
            startActivity(Intent(this, CheckCallActivity::class.java))
        }
        binding.familySetupButton.setOnClickListener {
            startActivity(Intent(this, FamilySetupActivity::class.java))
        }
        binding.aiServicesButton.setOnClickListener {
            startActivity(Intent(this, AiServicesActivity::class.java))
        }
        requestNotificationPermissionIfNeeded()
        redirectToFullScreenIntentSetupIfNeeded()
    }

    /**
     * One-time redirect, checked only in onCreate (not onResume) so backing
     * out of the setup screen doesn't trap the user in a loop — see the doc
     * comment on [FullScreenIntentSetupActivity].
     */
    private fun redirectToFullScreenIntentSetupIfNeeded() {
        if (!NotificationManagerCompat.from(this).canUseFullScreenIntent()) {
            startActivity(Intent(this, FullScreenIntentSetupActivity::class.java))
        }
    }

    /** Required at runtime on API 33+ or the warning card's notification never posts. */
    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
        if (!granted) {
            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    override fun onResume() {
        super.onResume()
        updateRoleStatus()
        binding.baseUrlValue.text = (application as RakshakApp).settings.prahariBaseUrl
    }

    private fun requestCallScreeningRole() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            Toast.makeText(this, R.string.role_not_supported, Toast.LENGTH_LONG).show()
            return
        }
        val roleManager = getSystemService(RoleManager::class.java)
        if (roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING) &&
            !roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        ) {
            roleRequestLauncher.launch(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING))
        } else {
            updateRoleStatus()
        }
    }

    private fun updateRoleStatus() {
        val held = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        } else {
            false
        }
        binding.roleStatusText.setText(
            if (held) R.string.role_status_active else R.string.role_status_inactive
        )
        binding.requestRoleButton.isEnabled = !held
    }
}
