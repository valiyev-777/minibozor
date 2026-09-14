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
import androidx.compose.ui.text.style.TextAlign
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
import uz.minibozor.data.remote.dto.ColourDto
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

/**
 * How many have gone, in one line under the price.
 *
 * **How many are left is not on this page.** It used to lead the line — "4 dona
 * qoldi · 4 dona sotilgan" — and a shop telling a customer how much of it is in
 * the room is answering a question nobody asked with a figure that helps a
 * competitor more than a buyer. What is left is still enforced, at the only
 * moment it is a real answer: the stepper in the buy bar stops at the last one
 * and says the number there. What goes here is the half a customer does read —
 * how many other people bought it, which is the only fact on the page that is
 * about them rather than about us.
 *
 * The pill stays. A shelf with none left has to say so before somebody picks a
 * size and finds a dead button, and [inStock] is about the cell chosen above,
 * not about the product as a whole.
 *
 * Nothing at all when there is nothing to say — a product in stock that nobody
 * has bought yet gets a line of silence rather than an empty box glyph.
 */
@Composable
fun ShelfLine(
    soldCount: Int,
    inStock: Boolean,
    modifier: Modifier = Modifier,
) {
    val gone = !inStock
    if (!gone && soldCount <= 0) return
    Row(
        modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        MbIcon(
            "box",
            size = 14.dp,
            tint = if (gone) MbTheme.colors.danger else MbTheme.colors.icon,
        )
        if (soldCount > 0) {
            MbText(
                pluralStringResource(R.plurals.n_sotilgan, soldCount, soldCount.grouped()),
                MbTheme.type.caption,
                MbTheme.colors.textSecondary,
                maxLines = 1,
            )
        }
        if (gone) {
            Spacer(Modifier.weight(1f))
            MbStatusPill(
                stringResource(R.string.tugadi),
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
 *
 * **A colour is sold out *in the size being asked about*.** The tile used to go
 * grey only when every size of that colour had gone, so a customer who wanted a
 * 41 was shown five bright photographs of which one actually had a 41 — they
 * found out by tapping each in turn and watching the size row underneath.
 * [soldOut] is the set the caller works out from the chosen size, and changing
 * the size changes the set: the photographs light back up as the question
 * changes. Both halves stay pressable ([MbSizeChip] does the same), because
 * colour and size are one question asked from two ends.
 */
@Composable
fun ColorPicker(
    colors: List<ColourDto>,
    selected: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
    /** Colour names with nothing left in the size currently chosen. */
    soldOut: Set<String> = emptySet(),
    /** Used for the fallback when a lone colour has no photo of its own. */
    productImages: List<String> = emptyList(),
) {
    val chosen = colors.firstOrNull { it.colour == selected } ?: colors.firstOrNull()
    Column(modifier.fillMaxWidth()) {
        PickerLabel(stringResource(R.string.rang), chosen?.colour.orEmpty())
        Spacer(Modifier.height(12.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            colors.forEachIndexed { index, color ->
                val isSelected = color.colour == chosen?.colour
                val gone = color.colour in soldOut || !color.inStock
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
                        // Pressable whether or not this colour has the size in
                        // hand. Tapping a struck-out one is how a customer asks
                        // "what sizes does the blue come in?", and refusing the
                        // tap leaves them no way to ask it.
                        .mbClickable(MbTheme.shapes.tile) { onSelect(color.colour) }
                        // Room for the ring to read as a ring rather than as a
                        // dark edge on the photograph.
                        .padding(if (isSelected) 4.dp else 3.dp)
                        .alpha(if (gone) 0.4f else 1f),
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
                                .background(color.hex.toColor(MbTheme.colors.fill))
                        )
                    }
                    // In a word. A sold-out colour was a dimmed photograph and
                    // nothing else: it reads as a photograph that came out
                    // badly, and the customer taps it again. The sizes say so
                    // with a line through them; a photograph cannot be struck
                    // through, so it is said.
                    if (gone) {
                        MbText(
                            stringResource(R.string.tugagan),
                            MbTheme.type.caption,
                            MbTheme.colors.surface,
                            modifier = Modifier
                                .align(Alignment.BottomCenter)
                                .fillMaxWidth()
                                .clip(MbTheme.shapes.tileSmall)
                                .background(MbTheme.colors.ink.copy(alpha = 0.66f))
                                .padding(vertical = 2.dp),
                            textAlign = TextAlign.Center,
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
            // The size, not the cell's whole label. `label` is "Qora · 41",
            // composed for a place where the colour is worth repeating — a
            // basket line, a pick list. Here the colour is either the strip
            // above or the only one there is, so printing it in the heading and
            // again on every chip made a row of "Qora · 41  Qora · 42  Qora ·
            // 43" that says one useful digit per chip.
            name = stringResource(R.string.olcham),
            value = selected?.size.orEmpty(),
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
                    label = variant.size,
                    selected = variant.id == selected?.id,
                    // Struck through, not switched off. A size this colour has
                    // run out of is still the size the customer came for, and
                    // pressing it re-reads the colours above against it.
                    soldOut = !variant.inStock,
                    onClick = { onSelect(variant.id) },
                )
            }
        }
        // No count under the row. It used to answer about the size in hand,
        // which was right when the page had no other figure — but the line
        // under the rating now answers about the same cell and the buy bar
        // repeats it a hundred pixels below this, so the screen said "2 dona
        // qoldi" three times and a reader has to check whether they agree.
    }
}

// `OfferRow` and `SellerLine` stood here, to the end of the file.
//
// There is one company selling now, so a product has one price and nobody to
// name beside it. A row saying who the seller is, in a shop that *is* the
// seller, asks the customer a question they cannot act on — and the count that
// made it worth reading ("and three others are selling it") counted offers,
// which is the thing that went.
