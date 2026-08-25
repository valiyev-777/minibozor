package uz.minibozor.core.util

import uz.minibozor.BuildConfig

/**
 * Turns the API's relative media path into a URL this build can load.
 *
 * The server returns `products/gazelle.png` and stays out of the business of
 * knowing how a client reaches it — an emulator, a USB-attached phone and
 * production all have different hosts.
 */
fun String?.mediaUrl(): String? {
    val path = this?.trim().orEmpty()
    if (path.isEmpty()) return null
    if (path.startsWith("http://") || path.startsWith("https://")) return path
    return BuildConfig.MEDIA_BASE_URL.trimEnd('/') + "/" + path.trimStart('/')
}
