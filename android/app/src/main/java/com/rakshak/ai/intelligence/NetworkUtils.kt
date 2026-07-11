package com.rakshak.ai.intelligence

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities

/**
 * Cheap, synchronous, no-I/O check of whether the device currently has any
 * active network with internet capability — used by CheckCallActivity to
 * skip the Prahari HTTP attempt entirely (no spinner, no timeout wait) when
 * there's nothing to reach in the first place, e.g. airplane mode. Distinct
 * from "Prahari is actually reachable": a device can have a fine Wi-Fi/data
 * connection while the Prahari host specifically is down or slow — that
 * case still has to attempt the real request and rely on OkHttp's timeouts
 * (see PrahariHttpApiClient) to fall back within a bounded, short wait.
 */
fun hasActiveNetworkConnection(context: Context): Boolean {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        ?: return false
    val network = cm.activeNetwork ?: return false
    val capabilities = cm.getNetworkCapabilities(network) ?: return false
    return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
}
