package uz.minibozor.core.util

import androidx.compose.ui.graphics.Color

/** `#14162A` as sent by the API into a Compose colour, with a safe fallback. */
fun String.toColor(fallback: Color = Color(0xFF14162A)): Color = runCatching {
    Color(android.graphics.Color.parseColor(this))
}.getOrElse { fallback }
