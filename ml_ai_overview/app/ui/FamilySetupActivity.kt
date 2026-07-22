package com.rakshak.ai.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.rakshak.ai.BuildConfig
import com.rakshak.ai.R
import com.rakshak.ai.RakshakApp
import com.rakshak.ai.databinding.ActivityFamilySetupBinding
import com.rakshak.ai.settings.AppSettings

/**
 * One-time family-member setup (CLAUDE.md 9.2) for the settings that were
 * previously write-only preferences with no UI: the trusted contact's phone
 * number (Tier 2 real SMS) and the Tier 3b autonomous-escalation opt-in.
 * Never opened by the elderly/primary user during an actual scam call.
 */
class FamilySetupActivity : AppCompatActivity() {

    /**
     * BCP-47 tag paired with its native-script self-name — the same 12
     * languages CLAUDE.md §11.3 targets and ExplanationTranslations covers.
     * Self-names (not English names) so a non-English-literate user can
     * still recognize their own language in the list.
     */
    private val spokenLanguages = listOf(
        "en-IN" to "English",
        "hi-IN" to "हिन्दी",
        "bn-IN" to "বাংলা",
        "mr-IN" to "मराठी",
        "te-IN" to "తెలుగు",
        "ta-IN" to "தமிழ்",
        "gu-IN" to "ગુજરાતી",
        "ur-IN" to "اردو",
        "kn-IN" to "ಕನ್ನಡ",
        "ml-IN" to "മലയാളം",
        "pa-IN" to "ਪੰਜਾਬੀ",
        "or-IN" to "ଓଡ଼ିଆ",
    )

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

    private val locationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            binding.locationSharingToggle.isChecked = false
            Toast.makeText(
                this,
                "Location permission was not granted — location sharing has stayed off. The trusted-contact alert will not include a location.",
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

        binding.spokenLanguageSpinner.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_item,
            spokenLanguages.map { it.second },
        ).apply { setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
        // No language-selection UI existed before this screen — until now,
        // "unset" silently meant Hindi-first at speak-time (see
        // AutoEscalationCountdownActivity), not AppSettings.DEFAULT_LANGUAGE's
        // "en-IN". Show that same actual default here rather than a
        // technically-true-but-misleading "English" preselection.
        val currentTag = if (settings.hasExplicitSpokenLanguage) settings.spokenLanguageTag else "hi-IN"
        val currentIndex = spokenLanguages.indexOfFirst { it.first == currentTag }.coerceAtLeast(0)
        binding.spokenLanguageSpinner.setSelection(currentIndex)

        binding.contactNameInput.setText(settings.trustedContactName)
        binding.contactPhoneInput.setText(settings.trustedContactPhone)
        binding.contactEmailInput.setText(settings.trustedContactEmail)
        binding.locationSharingExplanation.text = getString(
            R.string.family_setup_location_sharing_explanation, getString(R.string.app_name)
        )
        binding.locationSharingToggle.isChecked = settings.locationSharingEnabled
        binding.tier3bToggle.isChecked = settings.tier3bEnabled
        binding.tier3bNumberInput.setText(settings.tier3bPhoneNumber)
        binding.backendUrlInput.setText(settings.prahariBaseUrl)
        binding.tier3bDebugWarning.visibility = if (BuildConfig.DEBUG) View.VISIBLE else View.GONE

        binding.locationSharingToggle.setOnCheckedChangeListener { _, checked ->
            // Requested only from this toggle, never bundled with any other
            // permission request in this Activity (SMS/CALL_PHONE/READ_PHONE_STATE
            // above and below are each gated behind their own toggle too).
            if (checked && ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED
            ) {
                locationPermissionLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            }
        }

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
        val app = application as RakshakApp
        val settings = app.settings

        val backendUrl = binding.backendUrlInput.text?.toString()?.trim().orEmpty()
        settings.prahariBaseUrl = backendUrl.ifBlank { AppSettings.DEFAULT_BASE_URL }
        binding.backendUrlInput.setText(settings.prahariBaseUrl)
        // Picks up the new base URL immediately — without this the app would
        // keep talking to whatever host was configured at process start until
        // the next cold start, silently ignoring the change just saved above.
        app.refreshPrahariClient()

        // Always written on save, same as every other field here — this is
        // what turns AppSettings.hasExplicitSpokenLanguage true from now on,
        // even if the family picks Hindi itself (identical spoken behavior
        // to the implicit pre-selection default, but now a real, persisted
        // choice rather than a fallback).
        settings.spokenLanguageTag = spokenLanguages[binding.spokenLanguageSpinner.selectedItemPosition].first

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

        // Fail safe, same pattern as Tier 3b below: never persist enabled=true
        // without ACCESS_FINE_LOCATION actually granted, regardless of what
        // the toggle currently shows (e.g. the user could have revoked the
        // permission via system Settings since checking it).
        val wantsLocationSharing = binding.locationSharingToggle.isChecked
        val hasLocationPermission = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED
        val canEnableLocationSharing = wantsLocationSharing && hasLocationPermission
        settings.locationSharingEnabled = canEnableLocationSharing
        binding.locationSharingToggle.isChecked = canEnableLocationSharing
        if (wantsLocationSharing && !canEnableLocationSharing) {
            Toast.makeText(
                this,
                "Location permission is required for location sharing — it has stayed off.",
                Toast.LENGTH_LONG,
            ).show()
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
