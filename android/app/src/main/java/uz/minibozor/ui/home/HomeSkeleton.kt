package uz.minibozor.ui.home

import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbSkeleton

/**
 * What the home screen looks like before its first payload lands: the same
 * shapes in the same places, shimmering.
 *
 * The same shapes is the whole job, and it used to get it wrong. It drew a
 * five-across grid of quick links under the banner — two rows of ten round
 * tiles — and the home page has not had those since the category grid came out
 * of it and the space went to goods. So the wait promised a shelf of turkums,
 * the payload arrived, and the page the customer was already reading rearranged
 * itself under them. A skeleton that does not match is worse than no skeleton:
 * it is a layout shift with a shimmer on it.
 *
 * What the feed actually opens with is a white band holding the city and the
 * search, a banner with its dots, then a heading and a two-up row of cards, and
 * a second heading below that. This is that, at those sizes.
 *
 * Deliberately not scrollable. It stands in for one screenful and is replaced
 * the moment the data arrives, so giving it scroll state to throw away would
 * only add work.
 */
@Composable
fun HomeSkeleton(modifier: Modifier = Modifier) {
    val edge = MbTheme.dimens.homeEdge
    Column(modifier.fillMaxSize()) {
        // The header band, in the surface the real one is drawn on rather than
        // on bare canvas — the band is the first thing the eye finds at the top
        // of this page and it should not arrive with the data.
        Column(
            Modifier
                .fillMaxWidth()
                .background(MbTheme.colors.surface)
                .padding(horizontal = 20.dp),
        ) {
            Spacer(Modifier.height(14.dp))
            MbSkeleton(Modifier.width(120.dp).height(17.dp), MbTheme.shapes.badge)
            Spacer(Modifier.height(14.dp))
            MbSkeleton(
                Modifier.fillMaxWidth().height(MbTheme.dimens.searchHeight),
                MbTheme.shapes.field,
            )
            Spacer(Modifier.height(10.dp))
        }

        Spacer(Modifier.height(12.dp))
        MbSkeleton(
            Modifier
                .padding(horizontal = edge)
                .fillMaxWidth()
                .height(MbTheme.dimens.bannerHeight),
            MbTheme.shapes.card,
        )
        Spacer(Modifier.height(10.dp))
        // The carousel's own dots, which are part of the shape of the block.
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            MbSkeleton(Modifier.width(40.dp).height(3.5.dp), MbTheme.shapes.badge)
        }

        SkeletonSectionHead(edge)
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = edge),
            horizontalArrangement = Arrangement.spacedBy(MbTheme.dimens.cardGap),
        ) {
            repeat(2) { SkeletonCard(Modifier.weight(1f)) }
        }

        // The second heading, so the wait ends on the promise of another shelf
        // rather than on the bottom edge of one card.
        SkeletonSectionHead(edge)
    }
}

/** A section's heading and its "Barchasi", at the size and spacing the real one keeps. */
@Composable
private fun SkeletonSectionHead(edge: Dp) {
    Spacer(Modifier.height(22.dp))
    Row(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = edge),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        MbSkeleton(Modifier.width(150.dp).height(19.dp), MbTheme.shapes.badge)
        MbSkeleton(Modifier.width(58.dp).height(14.dp), MbTheme.shapes.badge)
    }
    Spacer(Modifier.height(12.dp))
}

/**
 * One product card, hollow.
 *
 * The card's own surface with its shapes inside it, not four grey blocks on the
 * page: the tile is a lifted white card and drawing the wait without it made
 * the shelf appear to gain its cards rather than fill them. The blocks match
 * what goes in them — a square photograph, a price, the thin was-price line,
 * and two lines of name.
 */
@Composable
private fun SkeletonCard(modifier: Modifier = Modifier) {
    Column(
        modifier
            .clip(MbTheme.shapes.tileLarge)
            .background(MbTheme.colors.surface)
            .padding(8.dp),
    ) {
        MbSkeleton(Modifier.fillMaxWidth().aspectRatio(1f), MbTheme.shapes.tileSmall)
        Spacer(Modifier.height(9.dp))
        MbSkeleton(Modifier.width(96.dp).height(17.dp), MbTheme.shapes.badge)
        Spacer(Modifier.height(4.dp))
        MbSkeleton(Modifier.width(60.dp).height(11.dp), MbTheme.shapes.badge)
        Spacer(Modifier.height(7.dp))
        MbSkeleton(Modifier.fillMaxWidth().height(12.dp), MbTheme.shapes.badge)
        Spacer(Modifier.height(5.dp))
        MbSkeleton(Modifier.width(80.dp).height(12.dp), MbTheme.shapes.badge)
    }
}
