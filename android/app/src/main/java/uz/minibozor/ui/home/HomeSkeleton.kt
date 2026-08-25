package uz.minibozor.ui.home

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbSkeleton

/**
 * What the home screen looks like before its first payload lands: the same
 * shapes in the same places, shimmering.
 *
 * Deliberately not scrollable. It stands in for one screenful and is replaced
 * the moment the data arrives, so giving it scroll state to throw away would
 * only add work.
 */
@Composable
fun HomeSkeleton(modifier: Modifier = Modifier) {
    Column(modifier.fillMaxSize()) {
        // header: city line and the search field
        Column(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
        ) {
            MbSkeleton(Modifier.width(140.dp).height(18.dp), MbTheme.shapes.badge)
            Spacer(Modifier.height(12.dp))
            MbSkeleton(Modifier.fillMaxWidth().height(46.dp), MbTheme.shapes.chip)
        }

        Spacer(Modifier.height(6.dp))
        MbSkeleton(
            Modifier
                .padding(horizontal = 12.dp)
                .fillMaxWidth()
                .height(MbTheme.dimens.bannerHeight),
            MbTheme.shapes.card,
        )

        Spacer(Modifier.height(18.dp))
        // the 5x2 quick-link grid
        Column(
            Modifier.padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            repeat(2) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    repeat(5) {
                        Column(
                            Modifier.weight(1f),
                            horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
                        ) {
                            MbSkeleton(Modifier.size(52.dp), MbTheme.shapes.tileSmall)
                            Spacer(Modifier.height(6.dp))
                            MbSkeleton(
                                Modifier.fillMaxWidth().height(9.dp),
                                MbTheme.shapes.badge,
                            )
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(22.dp))
        // a section header and its first row of tiles
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            MbSkeleton(Modifier.width(150.dp).height(20.dp), MbTheme.shapes.badge)
            MbSkeleton(Modifier.width(60.dp).height(20.dp), MbTheme.shapes.badge)
        }
        Spacer(Modifier.height(12.dp))
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            repeat(2) {
                Column(Modifier.weight(1f)) {
                    MbSkeleton(
                        Modifier.fillMaxWidth().aspectRatio(1f),
                        MbTheme.shapes.tileSmall,
                    )
                    Spacer(Modifier.height(8.dp))
                    MbSkeleton(Modifier.width(110.dp).height(16.dp), MbTheme.shapes.badge)
                    Spacer(Modifier.height(6.dp))
                    MbSkeleton(Modifier.fillMaxWidth().height(11.dp), MbTheme.shapes.badge)
                }
            }
        }
    }
}
