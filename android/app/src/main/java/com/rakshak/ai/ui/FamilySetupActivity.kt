package com.rakshak.ai.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.rakshak.ai.BuildConfig
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityFamilySetupBinding

/**
 * One-time family-member setup (CLAUDE.md 9.2) for the settings that were
 * previously write-only preferences with no UI: the trusted contact's phone
 * number (Tier 2 real SMS) and the Tier 3b autonomous-escalation opt-in.
 * Never opened by the elderly/primary user during an actual scam call.
 */
class FamilySetupActivity : AppCompatActivity() {

    private lateinit var binding: ActivityFamilySetupBinding

    private val smsPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(
                this,
                "SMS permission was not granted — the trusted contact will see the draft in-app instead, no text will be sent.",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    private val callPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        // `results` only contains entries for permissions actually included
        // in the request — the `missing` list below skips whichever one(s)
        // were already granted, so an already-granted permission is silently
        // ABSENT from this map, not present as `true`. Falling back to
        // checkSelfPermission for anything not in the map avoids the bug
        // this had at first: treating an already-granted permission (absent
        // from a single-permission request) as newly denied.
        val callGranted = results[Manifest.permission.CALL_PHONE]
            ?: (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED)
        val phoneStateGranted = results[Manifest.permission.READ_PHONE_STATE]
            ?: (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED)
        // Both are required together, same fail-safe treatment as CALL_PHONE
        // alone used to get. READ_PHONE_STATE used to only gate the missed-
        // escalation evidence agent's call-outcome check and silently no-op
        // without it — that left Tier 3b auto-dialing with no way to ever
        // detect (and alert on) an unanswered call, which is a silent
        // degradation, not an acceptable default. Required up front instead.
        if (!callGranted || !phoneStateGranted) {
            binding.tier3bToggle.isChecked = false
            val subject = when {
                !callGranted && !phoneStateGranted -> "Call and phone-state permissions were"
                !callGranted -> "Call permission was"
                else -> "Phone-state permission was"
            }
            Toast.makeText(
                this,
                "$subject not granted — Tier 3b needs both to auto-dial and to detect a missed/unanswered call, so it has been turned back off.",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityFamilySetupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val settings = (application as RakshakApp).settings

        binding.contactNameInput.setText(settings.trustedContactName)
        binding.contactPhoneInput.setText(settings.trustedContactPhone)
        binding.contactEmailInput.setText(settings.trustedContactEmail)
        binding.tier3bToggle.isChecked = settings.tier3bEnabled
        binding.tier3bNumberInput.setText(settings.tier3bPhoneNumber)
        binding.tier3bDebugWarning.visibility = if (BuildConfig.DEBUG) View.VISIBLE else View.GONE

        binding.tier3bToggle.setOnCheckedChangeListener { _, checked ->
            val missing = mutableListOf<String>()
            if (checked) {
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE)
                    != PackageManager.PERMISSION_GRANTED
                ) missing += Manifest.permission.CALL_PHONE
                if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
                    != PackageManager.PERMISSION_GRANTED
                ) missing += Manifest.permission.READ_PHONE_STATE
            }
            if (missing.isNotEmpty()) {
                callPermissionLauncher.launch(missing.toTypedArray())
            }
        }

        binding.saveButton.setOnClickListener { onSaveTapped() }
    }

    private fun onSaveTapped() {
        val settings = (application as RakshakApp).settings

        val phone = binding.contactPhoneInput.text?.toString()?.trim().orEmpty()
        settings.trustedContactName = binding.contactNameInput.text?.toString()?.trim().orEmpty()
        settings.trustedContactPhone = phone
        // Only used by the missed-escalation evidence agent's email fallback —
        // Tier 2's own SMS notification above doesn't touch this field.
        settings.trustedContactEmail = binding.contactEmailInput.text?.toString()?.trim().orEmpty()
        if (phone.isNotBlank() &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED
        ) {
            smsPermissionLauncher.launch(Manifest.permission.SEND_SMS)
        }

        val tier3bNumber = binding.tier3bNumberInput.text?.toString()?.trim().orEmpty()
        val wantsTier3b = binding.tier3bToggle.isChecked
        val hasCallPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.CALL_PHONE) ==
            PackageManager.PERMISSION_GRANTED
        val hasPhoneStatePermission = ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE) ==
            PackageManager.PERMISSION_GRANTED

        settings.tier3bPhoneNumber = tier3bNumber

        // Fail safe: never persist enabled=true without a configured number
        // and BOTH permissions actually granted. READ_PHONE_STATE used to be
        // optional here — silently degrading the missed-escalation call-
        // outcome check to a no-op — which meant Tier 3b could run with no
        // way to ever flag an unanswered call. Required alongside CALL_PHONE
        // now, not just requested alongside it.
        val canEnable = wantsTier3b && tier3bNumber.isNotBlank() && hasCallPermission && hasPhoneStatePermission
        settings.tier3bEnabled = canEnable
        binding.tier3bToggle.isChecked = canEnable
        if (wantsTier3b && !canEnable) {
            Toast.makeText(
                this,
                "Tier 3b needs a number and both call + phone-state permissions — it has stayed off.",
                Toast.LENGTH_LONG,
            ).show()
        }

        Toast.makeText(this, R.string.family_setup_saved_toast, Toast.LENGTH_SHORT).show()
        finish()
    }
}
