package com.rakshak.ai.location

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Address
import android.location.Geocoder
import android.location.Location
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import java.io.IOException
import java.util.Locale

private const val TAG = "RakshakLocation"

/**
 * A single current-location fix for the VICTIM'S OWN device, fetched only at
 * the moment a Tier 2/3b escalation actually fires — never polled in the
 * background, never used for anything but this. This is the victim's
 * location; nothing in this app has any way to learn the caller/scammer's
 * location, and no caller of this class may present it as such.
 *
 * @param latitude / longitude raw GPS fix from FusedLocationProviderClient.
 * @param humanReadableAddress best-effort reverse-geocoded address (see
 *   [VictimLocationProvider.reverseGeocode]'s doc for what this can and
 *   can't actually resolve) — null if reverse geocoding failed or is
 *   unavailable on this device. Callers must still have the GPS coordinates
 *   in that case, not silently drop the location entirely.
 */
data class VictimLocation(
    val latitude: Double,
    val longitude: Double,
    val humanReadableAddress: String?,
)

/**
 * Fetches [VictimLocation] for the escalation flows (WarningActivity's panic
 * button, AutoEscalationCountdownActivity's auto-escalation). Callback-based,
 * not suspend — matches this codebase's existing async style for one-shot
 * hardware/OS calls (see e.g. VoiceInputHelper), and lets Tier 3b fire this
 * without needing a coroutine scope that survives past its own `finish()`.
 *
 * Deliberately holds only [Context.getApplicationContext] — Tier 3b's
 * trigger path calls [fetchCurrentLocation] and then immediately finishes its
 * Activity (see AutoEscalationCountdownActivity.triggerAutoEscalation's "fire
 * both, neither waits on the other" comment), so this must not hold or leak
 * an Activity reference across the async callback below.
 */
class VictimLocationProvider(context: Context) {

    private val appContext = context.applicationContext
    private val fusedClient = LocationServices.getFusedLocationProviderClient(appContext)

    /**
     * Resolves with a [VictimLocation], or null if location sharing can't
     * produce one right now (permission missing, no fix within [timeoutMs],
     * or the fused provider itself failed) — callers must treat null as "send
     * the alert without a location," never block indefinitely on this.
     *
     * The callback fires on the main looper, but is NOT tied to any
     * Activity/Lifecycle — see class doc.
     */
    fun fetchCurrentLocation(timeoutMs: Long = DEFAULT_TIMEOUT_MS, onResult: (VictimLocation?) -> Unit) {
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.ACCESS_FINE_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            Log.i(TAG, "location_fetch_skipped reason=permission_not_granted")
            onResult(null)
            return
        }

        val cancellationSource = CancellationTokenSource()
        val mainHandler = Handler(Looper.getMainLooper())
        var settled = false

        val timeoutRunnable = Runnable {
            if (!settled) {
                settled = true
                Log.w(TAG, "location_fetch_timeout after ${timeoutMs}ms — proceeding without location")
                cancellationSource.cancel()
                onResult(null)
            }
        }
        mainHandler.postDelayed(timeoutRunnable, timeoutMs)

        try {
            fusedClient.getCurrentLocation(Priority.PRIORITY_BALANCED_POWER_ACCURACY, cancellationSource.token)
                .addOnSuccessListener { location: Location? ->
                    if (settled) return@addOnSuccessListener
                    settled = true
                    mainHandler.removeCallbacks(timeoutRunnable)
                    if (location == null) {
                        Log.w(TAG, "location_fetch_result=null (no recent fix available on this device)")
                        onResult(null)
                        return@addOnSuccessListener
                    }
                    Log.i(TAG, "location_fetch_success accuracy_m=${location.accuracy}")
                    reverseGeocode(location.latitude, location.longitude) { address ->
                        onResult(VictimLocation(location.latitude, location.longitude, address))
                    }
                }
                .addOnFailureListener { e ->
                    if (settled) return@addOnFailureListener
                    settled = true
                    mainHandler.removeCallbacks(timeoutRunnable)
                    Log.e(TAG, "location_fetch_failed: ${e.message}")
                    onResult(null)
                }
        } catch (e: SecurityException) {
            // Permission revoked between the check above and this call (a real
            // but narrow race — e.g. pulled via Settings mid-flow). Fail
            // closed to "no location," never crash the escalation flow over it.
            settled = true
            mainHandler.removeCallbacks(timeoutRunnable)
            Log.e(TAG, "location_fetch_security_exception: ${e.message}")
            onResult(null)
        }
    }

    /**
     * Android's Geocoder needs no API key of its own (unlike the raw Google
     * Maps Geocoding API), but on almost all real devices its backend is a
     * network-backed service via Google Play services, not an offline
     * on-device address database — so "no network call" is NOT true of this
     * step the way it is of, say, ML Kit's bundled language-id model.
     * Flagged here rather than silently assumed; see the honesty note this
     * feature was reported against.
     *
     * Runs off the main thread (the synchronous `getFromLocation` overload
     * blocks and can throw IOException) using a plain background Thread
     * rather than the newer API 33+ async `GeocodeListener` overload — one
     * unified code path across this app's full minSdk 29–targetSdk 34 range
     * was judged simpler than maintaining both, and the deprecation warning
     * on the sync overload is suppressed deliberately for that reason.
     */
    private fun reverseGeocode(lat: Double, lng: Double, onAddress: (String?) -> Unit) {
        Thread {
            val address = try {
                if (!Geocoder.isPresent()) {
                    Log.w(TAG, "reverse_geocode_skipped reason=geocoder_not_present_on_device")
                    null
                } else {
                    @Suppress("DEPRECATION")
                    val results = Geocoder(appContext, Locale.getDefault()).getFromLocation(lat, lng, 1)
                    results?.firstOrNull()?.let { formatAddress(it) }
                }
            } catch (e: IOException) {
                // Most common real cause: the geocoder's (usually network-
                // backed) service was unreachable — see class doc. GPS
                // coordinates are still delivered to the caller regardless.
                Log.w(TAG, "reverse_geocode_failed: ${e.message}")
                null
            } catch (e: IllegalArgumentException) {
                Log.w(TAG, "reverse_geocode_invalid_coordinates: ${e.message}")
                null
            }
            Handler(Looper.getMainLooper()).post { onAddress(address) }
        }.start()
    }

    /** getAddressLine(0) is the geocoder's own best-effort single-line
     *  formatting of whatever it actually resolved (street/locality/etc, at
     *  whatever precision the backend genuinely returned) — preferred over
     *  hand-picking fields, which would silently invent structure the
     *  backend didn't actually provide. Falls back to joining whichever
     *  individual fields are non-null in the rare case the backend didn't
     *  populate a formatted line; returns null (not blank) if neither is
     *  available at all. */
    private fun formatAddress(addr: Address): String? {
        addr.getAddressLine(0)?.let { return it }
        val fallback = listOfNotNull(addr.subLocality, addr.locality, addr.adminArea, addr.countryName)
            .joinToString(", ")
        return fallback.ifBlank { null }
    }

    companion object {
        const val DEFAULT_TIMEOUT_MS = 8_000L
    }
}
