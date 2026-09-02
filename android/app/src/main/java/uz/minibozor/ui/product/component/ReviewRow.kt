package uz.minibozor.ui.product.component

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbStars
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.toLocalDateTimeOrNull
import uz.minibozor.core.util.uzRelative
import uz.minibozor.data.remote.dto.ReviewDto

/** One review: avatar initials, name, stars, variant, body, photos and likes. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ReviewRow(
    review: ReviewDto,
    onLike: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(MbTheme.colors.fill),
                contentAlignment = Alignment.Center,
            ) {
                MbText(review.authorInitials, MbTheme.type.micro, MbTheme.colors.textSecondary)
            }
            Spacer(Modifier.size(10.dp))
            Column(Modifier.weight(1f)) {
                MbText(
                    review.authorName,
                    MbTheme.type.body.copy(
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold),
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    // Bigger than the app's default cluster: at 13 dp under a
                    // name set in bold the stars read as punctuation, and they
                    // are the whole point of the row — the verdict, before a
                    // word of the review is read.
                    MbStars(review.rating, size = 16.dp)
                    val date = review.createdAt.toLocalDateTimeOrNull()?.uzRelative().orEmpty()
                    MbText(date, MbTheme.type.meta, MbTheme.colors.icon)
                    if (review.variantLabel.isNotBlank()) {
                        MbText("·", MbTheme.type.meta, MbTheme.colors.hairlineStrong)
                        MbText(review.variantLabel, MbTheme.type.meta, MbTheme.colors.icon)
                    }
                }
            }
        }

        if (review.text.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            MbText(review.text, MbTheme.type.bodySmall, MbTheme.colors.inkSoft)
        }

        if (review.tags.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                review.tags.forEach { tag ->
                    Box(
                        Modifier
                            .clip(MbTheme.shapes.chip)
                            .background(MbTheme.colors.fill)
                            .padding(horizontal = 10.dp, vertical = 5.dp)
                    ) {
                        MbText(tag, MbTheme.type.micro, MbTheme.colors.textSecondary)
                    }
                }
            }
        }

        if (review.photos.isNotEmpty()) {
            Spacer(Modifier.height(10.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(review.photos) { photo ->
                    MbProductImage(
                        photo,
                        modifier = Modifier.size(72.dp),
                        shape = MbTheme.shapes.tileSmall,
                    )
                }
            }
        }

        if (onLike != null) {
            Spacer(Modifier.height(10.dp))
            Row(
                Modifier
                    .clip(MbTheme.shapes.chip)
                    .clickable(onClick = onLike)
                    .padding(horizontal = 4.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                MbIcon(
                    "heart",
                    size = 14.dp,
                    tint = if (review.likedByMe) MbTheme.colors.danger else MbTheme.colors.icon,
                )
                MbText("${review.likes}", MbTheme.type.caption, MbTheme.colors.icon)
            }
        }
    }
}
