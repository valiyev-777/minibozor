package uz.minibozor.core.design.component

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.graphics.drawable.toBitmap
import coil.imageLoader
import coil.request.ImageRequest
import coil.request.SuccessResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import uz.minibozor.core.util.mediaUrl

/**
 * How a product photograph should meet its frame.
 *
 * Whoever is selling sends whatever their camera gave them: a cut-out on
 * nothing, a studio shot on white, a phone picture on a grey table. We can ask
 * for transparent backdrops but we cannot enforce it, so the frame has to cope
 * with either — without the ground itself changing colour from tile to tile,
 * which turns a grid into a patchwork.
 *
 * So the ground stays the theme's, always, and it is the photograph that
 * adapts: a cut-out is framed with room around it, and a photograph that
 * brought its own backdrop fills the frame outright, leaving no ground to
 * clash with.
 */
enum class PhotoFraming {
    /** Nothing behind the subject. Sits inset on the theme's ground. */
    Cutout,

    /** Brought its own backdrop. Fills the frame, so no ground shows at all. */
    Backdrop,
}

@Composable
fun rememberPhotoFraming(url: String?): PhotoFraming {
    val context = LocalContext.current
    val resolved = url.mediaUrl()
    var framing by remember(resolved) {
        mutableStateOf(cache[resolved] ?: PhotoFraming.Cutout)
    }

    LaunchedEffect(resolved) {
        if (resolved == null) {
            framing = PhotoFraming.Cutout
            return@LaunchedEffect
        }
        cache[resolved]?.let { framing = it; return@LaunchedEffect }
        val verdict = classify(context, resolved)
        cache[resolved] = verdict
        framing = verdict
    }
    return framing
}

/** Verdicts live for the process: the answer cannot change per screen. */
private val cache = mutableMapOf<String, PhotoFraming>()

/**
 * Reads the photograph's border to see whether anything is there.
 *
 * Decoded small on purpose. Whether a border exists survives being scaled to
 * 48 px, and nothing here is worth a full-size bitmap.
 */
private suspend fun classify(context: Context, url: String): PhotoFraming =
    withContext(Dispatchers.IO) {
        val request = ImageRequest.Builder(context)
            .data(url)
            .size(SAMPLE)
            // Pixels cannot be read back out of a hardware bitmap.
            .allowHardware(false)
            .build()
        val result = context.imageLoader.execute(request) as? SuccessResult
            ?: return@withContext PhotoFraming.Cutout
        val bitmap = runCatching { result.drawable.toBitmap() }.getOrNull()
            ?: return@withContext PhotoFraming.Cutout

        val width = bitmap.width
        val height = bitmap.height
        if (width < 8 || height < 8) return@withContext PhotoFraming.Cutout

        var opaque = 0
        var counted = 0
        for (x in 0 until width) {
            for (y in intArrayOf(0, height - 1)) {
                if (android.graphics.Color.alpha(bitmap.getPixel(x, y)) > 200) opaque++
                counted++
            }
        }
        for (y in 1 until height - 1) {
            for (x in intArrayOf(0, width - 1)) {
                if (android.graphics.Color.alpha(bitmap.getPixel(x, y)) > 200) opaque++
                counted++
            }
        }

        // A backdrop reaches the edge all the way round; a cut-out only ever
        // touches it where the subject runs off. Measured across the
        // catalogue the two groups sit at 100% and at under 35%, with most
        // cut-outs under 11%, so anything short of most of the way round is
        // read as a cut-out.
        if (opaque > counted * 0.7) PhotoFraming.Backdrop else PhotoFraming.Cutout
    }

/** Long edge the sample is decoded to. */
private const val SAMPLE = 48
