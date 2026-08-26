package uz.minibozor.core.design.component

import androidx.compose.ui.res.pluralStringResource
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import uz.minibozor.R
import uz.minibozor.core.design.MbPressAlpha
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbPressable
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.mediaUrl
import uz.minibozor.core.util.ratingText

/** The soft ink wash a pressed tile is highlighted with. */
@Composable
private fun pressTint(): Color = MbTheme.colors.ink.copy(alpha = MbPressAlpha)

/**
 * Photo with the design's warm neutral backdrop showing through while it loads.
 *
 * Fit, not Crop: catalogue photos are cut-outs of a whole product in mixed
 * aspect ratios, and cropping a 387x516 shoe into a square tile shows its
 * middle and cuts off the toe. Scene photography — the home banner — passes
 * Crop explicitly, which is what it wants.
 */
@Composable
fun MbProductImage(
    url: String?,
    modifier: Modifier = Modifier,
    shape: Shape = MbTheme.shapes.tile,
    /** The theme's photo ground unless overridden. See [PhotoFraming]. */
    background: Color = Color.Unspecified,
    contentScale: ContentScale = ContentScale.Fit,
    /**
     * Room left between a cut-out photograph and the frame's edge.
     *
     * Applied inside rather than by the caller padding this composable, so the
     * ground still reaches the frame's edge. Ignored for a photograph that
     * brought its own backdrop: that one fills the frame instead, which is
     * what keeps a white studio shot from sitting as a bright block inside a
     * dark tile.
     */
    photoInset: Dp = 0.dp,
) {
    val framing = rememberPhotoFraming(url)
    val fills = framing == PhotoFraming.Backdrop
    Box(
        modifier
            .clip(shape)
            .background(if (background == Color.Unspecified) MbTheme.colors.photoWarmAlt else background),
        contentAlignment = Alignment.Center,
    ) {
        val resolved = url.mediaUrl()
        if (resolved != null) {
            AsyncImage(
                model = resolved,
                contentDescription = null,
                // Cropped when it brought its own backdrop, so that backdrop
                // covers the frame rather than showing as a rectangle inside
                // it. Fitted otherwise, since a cut-out has nothing to spare.
                contentScale = if (fills) ContentScale.Crop else contentScale,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(if (fills) 0.dp else photoInset),
            )
        } else {
            // No photo yet. A muted glyph reads as "none supplied" where an
            // empty warm rectangle just reads as broken.
            MbIcon("box", size = 26.dp, tint = MbTheme.colors.hairlineStrong)
        }
    }
}

/** `1 090 000` + `−29%` + struck-through old price. */
@Composable
fun MbPriceRow(
    price: Int,
    oldPrice: Int? = null,
    discountPercent: Int? = null,
    modifier: Modifier = Modifier,
    priceStyle: TextStyle = MbTheme.type.price,
) {
    Column(modifier) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            MbText(price.grouped(), priceStyle, maxLines = 1)
            if (discountPercent != null) {
                // A pill rather than 9.5sp of red text beside a 15sp number:
                // the saving is the reason someone stops on the row, and it was
                // the smallest thing in it.
                MbText(
                    "−$discountPercent%",
                    MbTheme.type.captionBold,
                    MbTheme.colors.danger,
                    modifier = Modifier
                        .clip(MbTheme.shapes.badge)
                        .background(MbTheme.colors.dangerBg)
                        .padding(horizontal = 6.dp, vertical = 2.dp),
                    maxLines = 1,
                )
            }
        }
        if (oldPrice != null && oldPrice > price) {
            Spacer(Modifier.height(2.dp))
            MbText(
                oldPrice.grouped(),
                MbTheme.type.caption.copy(textDecoration = TextDecoration.LineThrough),
                MbTheme.colors.textQuaternary,
                maxLines = 1,
            )
        }
    }
}

@Composable
fun MbRating(
    rating: Double,
    reviewsCount: Int,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        MbText("★", MbTheme.type.meta, MbTheme.colors.star)
        MbText(ratingText(rating), MbTheme.type.meta, MbTheme.colors.icon)
        if (reviewsCount > 0) {
            MbText("·", MbTheme.type.meta, MbTheme.colors.hairlineStrong)
            MbText(pluralStringResource(R.plurals.n_reviews, reviewsCount, reviewsCount), MbTheme.type.meta, MbTheme.colors.icon)
        }
    }
}

@Composable
fun MbStars(rating: Int, modifier: Modifier = Modifier, size: Dp = 13.dp) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(1.dp)) {
        repeat(5) { index ->
            MbText(
                "★",
                MbTheme.type.caption.copy(fontSize = size.value.sp),
                if (index < rating) MbTheme.colors.star else MbTheme.colors.divider,
            )
        }
    }
}

/**
 * The two-per-row grid tile from the home screen and search results: photo,
 * favourite toggle, price, title, rating and an add-to-cart button.
 */
@Composable
fun MbProductTile(
    title: String,
    price: Int,
    oldPrice: Int?,
    discountPercent: Int?,
    imageUrl: String?,
    rating: Double,
    reviewsCount: Int,
    isFavorite: Boolean,
    onClick: () -> Unit,
    onToggleFavorite: () -> Unit,
    onAddToCart: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    Column(
        // mbPressable, not mbClickable: the tile's content reaches its edges,
        // and a clip would shave the title and button at the corner arcs.
        modifier.mbPressable(MbTheme.shapes.tile, pressTint(), onClick = onClick),
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Box {
            MbProductImage(
                imageUrl,
                modifier = Modifier
                    // Square, like the rail tiles: the catalogue photos are
                    // 1:1 with their own baked-in backdrop, so a letterboxed
                    // strip of tile shows through any other ratio.
                    .fillMaxWidth()
                    .aspectRatio(1f),
            )
            FavoriteBubble(
                isFavorite = isFavorite,
                onClick = onToggleFavorite,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(6.dp),
            )
        }
        MbPriceRow(price, oldPrice, discountPercent)
        // Two lines always, so every tile in a row is the same height and no
        // title ends up pressed against the card edge.
        MbText(title, MbTheme.type.caption, MbTheme.colors.inkSoft, maxLines = 2, minLines = 2)
        MbRating(rating, reviewsCount)
        if (onAddToCart != null) {
            Spacer(Modifier.height(3.dp))
            Box(
                Modifier
                    .fillMaxWidth()
                    .clip(MbTheme.shapes.field)
                    .background(MbTheme.colors.accent)
                    .clickable(onClick = onAddToCart)
                    .padding(vertical = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                MbText(stringResource(R.string.savatga), MbTheme.type.label, Color.White)
            }
        }
    }
}

/** The 112 dp tile used by the horizontal rails ("Poyabzal", "Elektronika"). */
@Composable
fun MbRailTile(
    title: String,
    price: Int,
    discountPercent: Int?,
    imageUrl: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier
            .width(MbTheme.dimens.railTileWidth)
            // mbPressable, not mbClickable: a clip's corner arcs would cut the
            // first and last glyphs of a two-line title at the tile's bottom.
            .mbPressable(MbTheme.shapes.tileSmall, pressTint(), onClick = onClick),
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        MbProductImage(
            imageUrl,
            modifier = Modifier
                .width(MbTheme.dimens.railTileWidth)
                .aspectRatio(1f),
            shape = MbTheme.shapes.tileSmall,
            background = MbTheme.colors.photoWarm,
        )
        Row(
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            MbText(price.grouped(), MbTheme.type.priceSmall)
            if (discountPercent != null) {
                MbText("−$discountPercent%", MbTheme.type.micro, MbTheme.colors.danger)
            }
        }
        MbText(title, MbTheme.type.meta, MbTheme.colors.inkSoft, maxLines = 2, minLines = 2)
    }
}

/** Wide "Bugungi tanlov" tile: shorter photo with a discount flag. */
@Composable
fun MbDealTile(
    title: String,
    price: Int,
    oldPrice: Int?,
    discountPercent: Int?,
    imageUrl: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        // mbPressable, not mbClickable — see MbRailTile.
        modifier.mbPressable(MbTheme.shapes.tileSmall, pressTint(), onClick = onClick),
        verticalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        Box {
            MbProductImage(
                imageUrl,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(1f),
                shape = MbTheme.shapes.tileSmall,
            )
        }
        MbPriceRow(price, oldPrice, discountPercent)
        // Two lines always, so every tile in a row is the same height and no
        // title ends up pressed against the card edge.
        MbText(title, MbTheme.type.caption, MbTheme.colors.inkSoft, maxLines = 2, minLines = 2)
    }
}

@Composable
fun FavoriteBubble(
    isFavorite: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    size: Dp = 24.dp,
) {
    Box(
        modifier
            .size(size)
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.92f))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        MbIcon(
            "heart",
            size = size * 0.52f,
            tint = if (isFavorite) MbTheme.colors.danger else MbTheme.colors.textSecondary,
            strokeWidth = 2f,
            filled = isFavorite,
        )
    }
}

/** Compact line item: photo, title, variant, price — cart, orders, reviews. */
@Composable
fun MbLineItem(
    title: String,
    imageUrl: String?,
    meta: String,
    price: Int,
    quantity: Int? = null,
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier
            .fillMaxWidth()
            .let { if (onClick != null) it.clickable(onClick = onClick) else it },
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        MbProductImage(
            imageUrl,
            modifier = Modifier.size(64.dp),
            shape = MbTheme.shapes.tileSmall,
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            MbText(title, MbTheme.type.caption, MbTheme.colors.inkSoft, maxLines = 2)
            if (meta.isNotBlank()) {
                MbText(meta, MbTheme.type.meta, MbTheme.colors.icon, maxLines = 1)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                MbText(price.grouped(), MbTheme.type.priceSmall)
                if (quantity != null) {
                    MbText(
                        "  × $quantity",
                        MbTheme.type.meta,
                        MbTheme.colors.icon,
                    )
                }
            }
        }
        trailing?.invoke()
    }
}
