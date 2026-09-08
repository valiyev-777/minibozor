package uz.minibozor.ui.product.component

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbPhotoStack
import uz.minibozor.core.design.component.MbSizeChip
import uz.minibozor.core.design.component.MbStatusPill
import uz.minibozor.core.design.component.MbStars
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.strikePrice
import uz.minibozor.core.util.grouped
import uz.minibozor.core.util.ratingText
import uz.minibozor.core.util.sum
import uz.minibozor.core.util.toColor
import uz.minibozor.data.remote.dto.OfferDto
import uz.minibozor.data.remote.dto.VariantDto

/**
 * The rating, in the place the description used to have.
 *
 * What someone wants at the top of a product page is not the seller's own prose
 * — it is what other buyers said, and how many of them there were. So the panel
 * leads with the number, the stars carry the fraction, and the customers' own
 * photographs sit beside it as the way through to the reviews. The description
 * still exists; it is further down, where a decided buyer goes looking for it.
 */
/**
 * Two of these are nullable, and each nullable one means "say nothing" rather
 * than "say nought".
 *
 * `reviewsCount = null` drops the "N sharh" line: the count is only worth
 * printing when the reviews behind it can be opened, and a page that promises
 * 136 of them and has none to show is worse than a page that promises
 * nothing. `onClick = null` drops the tap, for the same reason — a tile that
 * depresses and goes nowhere reads as a broken app.
 *
 * The *rating* is not nullable and stays either way: it is a cached column on
 * the product, and a page that suddenly has no rating at all reads as a
 * regression rather than as a feature being off. See `core/util/Features.kt`.
 */
@Composable
fun RatingPanel(
    rating: Double,
    reviewsCount: Int?,
    photos: List<String>,
    photosTotal: Int,
    onClick: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .fillMaxWidth()
            .clip(MbTheme.shapes.tile)
            .border(1.dp, MbTheme.colors.border, MbTheme.shapes.tile)
            .then(
                if (onClick != null) {
                    Modifier.mbClickable(MbTheme.shapes.tile, onClick = onClick)
                } else {
                    Modifier
                },
            )
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                MbText(ratingText(rating), MbTheme.type.title1)
                MbStars(rating, size = 17.dp)
            }
            if (reviewsCount != null) {
                Spacer(Modifier.height(5.dp))
                // Reviews only. The order count used to sit here beside them,
                // and the line below now prints what has sold as one half of
                // its own answer — the same number twice in forty vertical
                // points was one too many.
                MbText(
                    pluralStringResource(R.plurals.n_reviews, reviewsCount, reviewsCount),
                    MbTheme.type.caption,
                    MbTheme.colors.textSecondary,
                    maxLines = 1,
                )
            }
        }
        if (photos.isNotEmpty()) {
            Spacer(Modifier.width(10.dp))
            MbPhotoStack(photos, photosTotal)
        } else if (onClick != null) {
            // The chevron is a promise that there is somewhere to go. With
            // reviews off there is not, and a panel that offers the arrow and
            // then does nothing when pressed is the one thing worse than a
            // panel with no arrow.
            MbIcon("chevron-right", size = 16.dp, tint = MbTheme.colors.icon)
        }
    }
}

/** Under this many left, the count stops being a fact and becomes a reason. */
private const val LowStock = 5

/**
 * How many are left and how many have gone, in one line under the rating.
 *
 * The same fact the tile in the grid prints, at the same weight and in the same
 * words — a caption with the box beside it, quiet by default and red once the
 * number has something to say. It was a bordered panel for a while, with a
 * meter across it and the two figures set at title size; that is a great deal
 * of page for "six left, three hundred sold", and the meter was drawing a
 * proportion of a denominator nobody had. What it says fits on a line, so it
 * takes a line.
 *
 * The pill only appears when there is a reason for it. A product that is simply
 * in stock says so by not saying anything.
 *
 * [stockLeft] and [inStock] are about the colour on show above, not about the
 * product as a whole — the photograph is of one colour, and the count under it
 * has to be the count of the thing being looked at.
 */
@Composable
fun ShelfLine(
    stockLeft: Int,
    soldCount: Int,
    inStock: Boolean,
    modifier: Modifier = Modifier,
) {
    val gone = !inStock || stockLeft <= 0
    val low = !gone && stockLeft <= LowStock
    val urgent = gone || low
    Row(
        modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MbIcon(
            "box",
            size = 14.dp,
            tint = if (urgent) MbTheme.colors.danger else MbTheme.colors.icon,
        )
        // Nothing to count when there are none: the pill on the right is the
        // whole of what a sold-out shelf has to say, and "0 dona qoldi" beside
        // it would be the same sentence twice.
        if (!gone) {
            MbText(
                stringResource(R.string.n_dona_qoldi, stockLeft),
                MbTheme.type.caption,
                if (low) MbTheme.colors.danger else MbTheme.colors.inkMuted,
                maxLines = 1,
            )
        }
        if (soldCount > 0) {
            if (!gone) MbText("·", MbTheme.type.caption, MbTheme.colors.hairlineStrong)
            MbText(
                pluralStringResource(R.plurals.n_sotilgan, soldCount, soldCount.grouped()),
                MbTheme.type.caption,
                MbTheme.colors.textSecondary,
                maxLines = 1,
            )
        }
        if (urgent) {
            Spacer(Modifier.weight(1f))
            MbStatusPill(
                stringResource(if (gone) R.string.tugadi else R.string.kam_qoldi),
                background = MbTheme.colors.dangerBg,
                contentColor = MbTheme.colors.danger,
            )
        }
    }
}

/** `Rang: Oqish rang` — the label the pickers share. */
@Composable
private fun PickerLabel(
    name: String,
    value: String,
    modifier: Modifier = Modifier,
    action: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Row(
        modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MbText("$name:", MbTheme.type.body, MbTheme.colors.textSecondary)
        MbText(
            value,
            MbTheme.type.body.copy(fontWeight = FontWeight.Bold),
            maxLines = 1,
            modifier = Modifier.weight(1f, fill = false),
        )
        if (action != null && onAction != null) {
            Spacer(Modifier.weight(1f))
            MbText(
                action,
                MbTheme.type.label,
                MbTheme.colors.accent,
                modifier = Modifier
                    .clip(MbTheme.shapes.chip)
                    .mbTap(onClick = onAction)
                    .padding(horizontal = 2.dp, vertical = 2.dp),
                maxLines = 1,
            )
        }
    }
}

/**
 * The colours, as photographs of the thing in that colour.
 *
 * A hex circle asks the customer to imagine what "#0E0F12" looks like on a shoe;
 * the photograph shows them. Where the shop supplied no photo for a colour the
 * tile falls back to the swatch, so a half-photographed catalogue still picks.
 */
@Composable
fun ColorPicker(
    colors: List<VariantDto>,
    selectedId: Int?,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
    /** Used for the fallback when a lone colour has no photo of its own. */
    productImages: List<String> = emptyList(),
) {
    val selected = colors.firstOrNull { it.id == selectedId } ?: colors.firstOrNull()
    Column(modifier.fillMaxWidth()) {
        PickerLabel(stringResource(R.string.rang), selected?.label.orEmpty())
        Spacer(Modifier.height(12.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            colors.forEachIndexed { index, color ->
                val isSelected = color.id == selected?.id
                // One colour and no photo of its own: the product's own first
                // photograph is a picture of it in that colour.
                val photo = color.imageUrl
                    ?: productImages.getOrNull(index).takeIf { colors.size == 1 }
                Box(
                    Modifier
                        .size(74.dp)
                        .clip(MbTheme.shapes.tile)
                        .border(
                            width = if (isSelected) 2.dp else 1.dp,
                            color = if (isSelected) {
                                MbTheme.colors.ink
                            } else {
                                MbTheme.colors.border
                            },
                            shape = MbTheme.shapes.tile,
                        )
                        .mbClickable(MbTheme.shapes.tile, enabled = color.inStock) {
                            onSelect(color.id)
                        }
                        // Room for the ring to read as a ring rather than as a
                        // dark edge on the photograph.
                        .padding(if (isSelected) 4.dp else 3.dp)
                        .alpha(if (color.inStock) 1f else 0.4f),
                ) {
                    if (photo != null) {
                        MbProductImage(
                            photo,
                            modifier = Modifier.fillMaxSize(),
                            shape = MbTheme.shapes.tileSmall,
                        )
                    } else {
                        Box(
                            Modifier
                                .fillMaxSize()
                                .clip(MbTheme.shapes.tileSmall)
                                .background(color.value.toColor(MbTheme.colors.fill))
                        )
                    }
                }
            }
        }
    }
}

/**
 * The sizes, with the selected one ringed rather than filled.
 *
 * One row that scrolls, not a block that wraps. A size run is a single scale —
 * 39 through 46 — and wrapping it put 46 alone on a second line, which reads as
 * a separate question rather than as the end of the same one. Eight two-digit
 * chips fit a 375 dp screen at this size; a catalogue of "41 mm" or "XXL"
 * labels runs past the edge and is pushed along instead of stacked, which is
 * also what the colours above it do.
 */
@Composable
fun SizePicker(
    sizes: List<VariantDto>,
    selectedId: Int?,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
    onOpenChart: (() -> Unit)? = null,
) {
    val selected = sizes.firstOrNull { it.id == selectedId }
    Column(modifier.fillMaxWidth()) {
        PickerLabel(
            name = stringResource(R.string.olcham),
            value = selected?.label.orEmpty(),
            action = onOpenChart?.let { stringResource(R.string.olchamlar_jadvali) },
            onAction = onOpenChart,
        )
        Spacer(Modifier.height(12.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            sizes.forEach { variant ->
                MbSizeChip(
                    label = variant.label,
                    selected = variant.id == selected?.id,
                    enabled = variant.inStock,
                    onClick = { onSelect(variant.id) },
                )
            }
        }
        // How many of the size in hand, under the row rather than on the chips.
        // A 38-point chip holds two digits and nothing else, and a count on
        // every one of eight of them is a wall of numbers to read before
        // choosing — this answers about the one actually chosen, which is the
        // one the question is being asked about. A size with none left is
        // struck through in the row above and says nothing here.
        val left = selected?.stockLeft
        if (left != null && left > 0) {
            Spacer(Modifier.height(9.dp))
            MbText(
                stringResource(R.string.n_dona_qoldi, left),
                MbTheme.type.caption,
                if (left <= LowStock) MbTheme.colors.danger else MbTheme.colors.textTertiary,
                maxLines = 1,
            )
        }
    }
}

/**
 * Every seller offering this product, cheapest first.
 *
 * The one price at the top of the page belongs to one seller, and on a
 * marketplace that is a fact the page has been keeping to itself: the same
 * thing sits on the same card at four prices and the customer saw one of them
 * with no way to know there were others, or who any of them were. This is the
 * list behind that number — a name, a price and what is left of it per row,
 * with the row the card is quoting marked so the two numbers are seen to be the
 * same number rather than a contradiction.
 *
 * A sold-out seller stays in the list, greyed and struck: a cheaper price that
 * has run out is the reason the price above is the one it is, and hiding it
 * turns an explanation into a mystery. A seller who has withdrawn is not here
 * at all — the server does not send them.
 *
 * Read-only. Choosing a seller is a thing the API has no way to say yet, so the
 * rows do not pretend to be buttons.
 */
@Composable
fun OfferRow(offer: OfferDto, modifier: Modifier = Modifier) {
    val gone = !offer.inStock || offer.stockLeft <= 0
    Row(
        modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Column(Modifier.weight(1f)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                MbText(
                    offer.seller.name,
                    MbTheme.type.body.copy(fontWeight = FontWeight.Bold),
                    if (gone) MbTheme.colors.textTertiary else MbTheme.colors.ink,
                    maxLines = 1,
                )
                // Which of these rows the page above is quoting. Only ever one,
                // and only while it still has something to sell.
                if (offer.isWinner && !gone) {
                    MbStatusPill(
                        stringResource(R.string.kartadagi_narx),
                        MbTheme.colors.successBg,
                        MbTheme.colors.success,
                    )
                }
            }
            Spacer(Modifier.height(3.dp))
            MbText(
                if (gone) {
                    stringResource(R.string.tugagan)
                } else {
                    stringResource(R.string.n_dona_qoldi, offer.stockLeft)
                },
                MbTheme.type.caption,
                when {
                    gone -> MbTheme.colors.textTertiary
                    offer.stockLeft <= LowStock -> MbTheme.colors.danger
                    else -> MbTheme.colors.textSecondary
                },
                maxLines = 1,
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(horizontalAlignment = Alignment.End) {
            MbText(
                offer.price.sum(),
                MbTheme.type.priceSmall,
                if (gone) MbTheme.colors.textTertiary else MbTheme.colors.ink,
                maxLines = 1,
            )
            val was = offer.oldPrice
            if (was != null && was > offer.price) {
                Spacer(Modifier.height(3.dp))
                MbText(
                    was.grouped(),
                    MbTheme.type.strikePrice.copy(textDecoration = TextDecoration.LineThrough),
                    MbTheme.colors.textQuaternary,
                    maxLines = 1,
                )
            }
        }
    }
}

/**
 * Who is selling the thing at the price above, on the panel itself.
 *
 * On a marketplace the seller is part of what is being bought, and until now
 * the page carried the name in a delivery row folded behind "Batafsil" three
 * sections down. The count beside it is the point of the section further down:
 * "and three others are selling it" is a reason to keep scrolling, and one
 * seller says nothing at all.
 */
@Composable
fun SellerLine(name: String, offersCount: Int, modifier: Modifier = Modifier) {
    Row(
        modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MbIcon("basket", size = 14.dp, tint = MbTheme.colors.icon)
        MbText(name, MbTheme.type.label, MbTheme.colors.inkMuted, maxLines = 1)
        if (offersCount > 1) {
            MbText("·", MbTheme.type.caption, MbTheme.colors.hairlineStrong)
            MbText(
                pluralStringResource(R.plurals.n_sotuvchi, offersCount, offersCount),
                MbTheme.type.caption,
                MbTheme.colors.textSecondary,
                maxLines = 1,
            )
        }
    }
}
