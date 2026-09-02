package uz.minibozor.ui.product

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.background
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.lerp
import androidx.compose.ui.zIndex
import kotlinx.coroutines.launch
import uz.minibozor.core.design.MbMotion
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.design.mbTap
import kotlin.math.hypot
import kotlin.math.min

/** How far in a double tap takes the picture. */
private const val ZoomedIn = 2.6f

/** The most a pinch is allowed to reach. */
private const val MaxZoom = 5f

/** Drag the picture this far and letting go closes the view. */
private val DismissDistance = 120.dp

/** How far a dismissal drag has got, 0..1. */
private fun throwProgress(offset: Offset, dismissPx: Float): Float =
    if (dismissPx <= 0f) 0f else (hypot(offset.x, offset.y) / dismissPx).coerceIn(0f, 1f)

/**
 * The photograph, on its own, as large as the screen allows.
 *
 * The page's own frame is square and shares the screen with a price panel and a
 * bar of buttons, so a photograph there is always partly a thumbnail — fine for
 * recognising the thing, not enough for looking at it. This is the looking: the
 * picture as large as the screen allows, on the pale ground it is drawn on
 * everywhere else, with black around it and nothing else on the screen, and
 * double tap or pinch to go closer.
 *
 * It does not appear; it grows out of the picture that was tapped. [origin] is
 * where that picture sits on the page, in the root's own coordinates, and the
 * whole view is scaled and offset to coincide with it on the first frame, then
 * animated to its full size while the black ground fades up under it. Closing
 * runs the same path backwards, whether it is closed by the button, by the back
 * gesture, or by throwing the picture away — a swipe unwinds its own drag and
 * flies home at the same time, so the picture always ends up where the customer
 * left it rather than sliding off an edge.
 *
 * Leaving is deliberately hard to miss: a tap anywhere closes it, and so does
 * flicking the picture away in any direction it is free to move. The button in
 * the corner is the third way, not the only one — reaching a 44 dp target at
 * the top of the screen to put a photograph down is work nobody should have to
 * do.
 *
 * Paging stays with the pager while the picture is at its natural size; once it
 * is zoomed the same drags move the picture instead, and the pager is held. No
 * two gesture handlers listen at once, which is what stops one swipe from doing
 * half of each.
 */
@Composable
fun HeroViewer(
    images: List<String>,
    initialPage: Int,
    /**
     * The bounds of the picture this was opened from, in root coordinates.
     *
     * Null means there is nothing to fly from — the view fades up in place
     * instead, which is what a deep link or a restored state gets.
     */
    origin: Rect?,
    onClose: () -> Unit,
) {
    val pager = rememberPagerState(
        initialPage = initialPage.coerceIn(0, maxOf(images.lastIndex, 0)),
        pageCount = { maxOf(images.size, 1) },
    )

    var zoom by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val zoomedIn = zoom > 1.01f

    // A single photograph has nowhere to page to, so sideways is free for
    // throwing it away. With several, sideways belongs to the pager and only up
    // and down close the view.
    val single = images.size <= 1

    val scope = rememberCoroutineScope()
    val dismissPx = with(LocalDensity.current) { DismissDistance.toPx() }

    /** How far the picture has been dragged towards being put down. */
    val thrown = remember { Animatable(Offset.Zero, Offset.VectorConverter) }

    /** 0 = sitting in the page where it was tapped, 1 = filling the screen. */
    val flight = remember { Animatable(0f) }
    var closing by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        flight.animateTo(1f, tween(MbMotion.Emphasized, easing = MbMotion.Ease))
    }

    // A new page starts at its natural size. Carrying the zoom across meant
    // swiping to the next photograph and landing halfway into a corner of it.
    LaunchedEffect(pager.currentPage) {
        zoom = 1f
        offset = Offset.Zero
    }

    val scale by animateFloatAsState(
        zoom,
        spring(dampingRatio = 0.85f, stiffness = 600f),
        label = "viewerZoom",
    )

    val transformState = rememberTransformableState { zoomChange, panChange, _ ->
        zoom = (zoom * zoomChange).coerceIn(1f, MaxZoom)
        offset = if (zoom > 1.01f) offset + panChange else Offset.Zero
    }

    /** The reverse flight: home to where it came from, then gone. */
    fun close() {
        if (closing) return
        closing = true
        // Zoom and pan unwind with it, so the picture lands at the size the
        // page draws it rather than shrinking into its own corner.
        zoom = 1f
        offset = Offset.Zero
        scope.launch {
            launch {
                thrown.animateTo(Offset.Zero, tween(MbMotion.Standard, easing = MbMotion.Ease))
            }
            flight.animateTo(0f, tween(MbMotion.Standard, easing = MbMotion.Ease))
            onClose()
        }
    }

    fun release() {
        if (throwProgress(thrown.value, dismissPx) >= 1f) {
            close()
        } else {
            scope.launch {
                thrown.animateTo(Offset.Zero, spring(dampingRatio = 0.8f, stiffness = 700f))
            }
        }
    }

    BackHandler { close() }

    BoxWithConstraints(
        Modifier
            .fillMaxSize()
            // Over the page, the bar and the buy bar alike.
            .zIndex(10f)
            // Black rather than the theme's canvas: this is the one screen in
            // the app whose subject is the picture, and any ground with a
            // colour of its own tints what the customer is trying to judge. It
            // comes up with the flight, so the page is still visible around the
            // growing photograph, and thins out again as the picture is dragged
            // away so the gesture explains itself before it finishes. Drawn
            // here rather than set as a background colour, so following the
            // animation invalidates drawing and nothing else.
            .drawBehind {
                val ground = flight.value * (1f - throwProgress(thrown.value, dismissPx) * 0.7f)
                drawRect(Color.Black, alpha = ground)
            }
            // The dismissal drag. Off while the picture is zoomed — those drags
            // move the picture — and one axis or two depending on whether the
            // pager needs sideways for itself.
            .then(
                if (zoomedIn) {
                    Modifier
                } else if (single) {
                    Modifier.pointerInput(single, zoomedIn) {
                        detectDragGestures(
                            onDragEnd = { release() },
                            onDragCancel = { release() },
                        ) { _, delta ->
                            scope.launch { thrown.snapTo(thrown.value + delta) }
                        }
                    }
                } else {
                    Modifier.pointerInput(single, zoomedIn) {
                        detectVerticalDragGestures(
                            onDragEnd = { release() },
                            onDragCancel = { release() },
                        ) { _, delta ->
                            scope.launch {
                                thrown.snapTo(thrown.value + Offset(0f, delta))
                            }
                        }
                    }
                }
            )
    ) {
        // The two rectangles the flight runs between, worked out here where the
        // screen's own size is known.
        //
        // Fitted to the screen, a catalogue photograph is a square as wide as
        // the narrower side of the display — every photograph in the catalogue
        // is 1:1, which is also why the page's own frame is square. The page's
        // copy is the same square in a different place and at a different size,
        // so the flight is one scale and one offset, and at the top of a page,
        // where the frame is already full width, it comes out as pure movement
        // with no scaling at all.
        val density = LocalDensity.current
        val fullWidth = with(density) { maxWidth.toPx() }
        val fullHeight = with(density) { maxHeight.toPx() }
        val fitted = min(fullWidth, fullHeight)
        val fromScale = if (origin != null && fitted > 0f) {
            (origin.width / fitted).coerceIn(0.05f, 4f)
        } else {
            1f
        }
        val fromX = if (origin != null) origin.center.x - fullWidth / 2f else 0f
        val fromY = if (origin != null) origin.center.y - fullHeight / 2f else 0f

        Box(
            Modifier
                .fillMaxSize()
                .graphicsLayer {
                    val open = flight.value
                    val put = throwProgress(thrown.value, dismissPx)
                    // Shrinks a little as it is thrown, so the picture reads as
                    // being put down rather than sliding off a table.
                    val size = lerp(fromScale, 1f, open) * (1f - put * 0.12f)
                    scaleX = size
                    scaleY = size
                    translationX = lerp(fromX, 0f, open) + thrown.value.x
                    translationY = lerp(fromY, 0f, open) + thrown.value.y
                    // Only while it has somewhere to fly from: without an
                    // origin the picture simply fades up at full size.
                    alpha = if (origin == null) open else 1f
                }
        ) {
            HorizontalPager(
                pager,
                Modifier.fillMaxSize(),
                // Held while the picture is zoomed: those drags belong to the
                // picture.
                userScrollEnabled = !zoomedIn,
            ) { page ->
                Box(
                    Modifier
                        .fillMaxSize()
                        .pointerInput(page) {
                            detectTapGestures(
                                // One tap puts it down. It also swallows the
                                // tap, so nothing on the page underneath reacts
                                // to the same touch.
                                onTap = { close() },
                                onDoubleTap = {
                                    if (zoom > 1.01f) {
                                        zoom = 1f
                                        offset = Offset.Zero
                                    } else {
                                        zoom = ZoomedIn
                                    }
                                },
                            )
                        }
                        // Only once there is something to pan: at natural size
                        // the pager and the dismissal need every drag, and a
                        // transformable listening alongside them eats half.
                        .transformable(transformState, enabled = zoomedIn),
                    contentAlignment = Alignment.Center,
                ) {
                    // The photograph keeps the ground it is drawn on everywhere
                    // else in the app, on a plate of its own.
                    //
                    // Half the catalogue is cut out against transparency — the
                    // trainers, the watches, the headphones are RGBA with an
                    // empty background — so a picture drawn straight onto this
                    // screen's black ground loses the pale studio backdrop it
                    // has on the page, and the shoe reads as having had its
                    // background deleted. The same component as the page uses,
                    // at the same 1:1 the whole catalogue is shot at, so what
                    // opens is what was tapped, and the black is left as the
                    // room around the picture rather than as its backdrop.
                    //
                    // The zoom rides on the plate, not on the picture inside
                    // it, so going closer takes the backdrop with it instead of
                    // growing the product out of its own frame.
                    MbProductImage(
                        images.getOrNull(page),
                        modifier = Modifier
                            // A square as large as the shorter side of the
                            // screen: the same rectangle the flight above is
                            // computed against.
                            .aspectRatio(1f)
                            .graphicsLayer {
                                // Only the current page follows the zoom; the
                                // neighbours stay at their natural size behind
                                // the fold.
                                val live = page == pager.currentPage
                                scaleX = if (live) scale else 1f
                                scaleY = if (live) scale else 1f
                                translationX = if (live) offset.x else 0f
                                translationY = if (live) offset.y else 0f
                            },
                        // Square corners: it is the whole screen's subject, not
                        // a tile in a grid.
                        shape = RectangleShape,
                        // The whole photograph, uncropped.
                        contentScale = ContentScale.Fit,
                    )
                }
            }
        }

        Row(
            Modifier
                .fillMaxWidth()
                .windowInsetsPadding(WindowInsets.statusBars)
                .padding(horizontal = 14.dp, vertical = 10.dp)
                // Arrives with the flight and steps out of the way as the
                // picture is thrown, so the last thing on screen is the
                // picture.
                .graphicsLayer {
                    alpha = flight.value * (1f - throwProgress(thrown.value, dismissPx))
                },
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (images.size > 1) {
                // Which of how many, in words rather than dots: on a black
                // screen with no page under it, "2 / 5" is the only thing that
                // says the swipe has anywhere to go.
                MbText(
                    "${pager.currentPage + 1} / ${images.size}",
                    MbTheme.type.label,
                    Color.White.copy(alpha = 0.85f),
                    modifier = Modifier
                        .clip(MbTheme.shapes.chip)
                        .background(Color.White.copy(alpha = 0.14f))
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                )
            }
            Box(Modifier.weight(1f))
            Box(
                Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.14f))
                    .mbTap { close() },
                contentAlignment = Alignment.Center,
            ) {
                MbIcon("close", size = 20.dp, tint = Color.White, strokeWidth = 2f)
            }
        }
    }
}
