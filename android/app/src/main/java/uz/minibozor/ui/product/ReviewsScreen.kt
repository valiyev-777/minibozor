package uz.minibozor.ui.product

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbBottomBar
import uz.minibozor.core.design.component.MbCard
import uz.minibozor.core.design.component.MbChip
import uz.minibozor.core.design.component.MbDivider
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.component.MbStars
import uz.minibozor.core.design.component.MbTopBar
import uz.minibozor.core.util.ratingText
import uz.minibozor.ui.product.component.ReviewRow

/** Screen 15 — Sharhlar, with the rating histogram and a star filter. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ReviewsScreen(
    productId: Int,
    onBack: () -> Unit,
    onWriteReview: () -> Unit,
    viewModel: ReviewsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    LaunchedEffect(productId) { viewModel.load(productId) }

    MbScreen(
        topBar = { MbTopBar("Sharhlar", onBack = onBack) },
        bottomBar = {
            MbBottomBar { MbPrimaryButton("Sharh yozish", onWriteReview, leadingGlyph = "star") }
        },
    ) { padding ->
        LazyColumn(
            Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            state.summary?.let { summary ->
                item {
                    MbCard {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                MbText(ratingText(summary.rating), MbTheme.type.display)
                                MbStars(summary.rating.toInt())
                                Spacer(Modifier.height(4.dp))
                                MbText(
                                    "${summary.total} sharh",
                                    MbTheme.type.meta,
                                    MbTheme.colors.icon,
                                )
                            }
                            Spacer(Modifier.width(20.dp))
                            Column(Modifier.weight(1f)) {
                                summary.distribution.forEach { bucket ->
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                                        modifier = Modifier.padding(vertical = 3.dp),
                                    ) {
                                        MbText(
                                            "${bucket.stars}",
                                            MbTheme.type.micro,
                                            MbTheme.colors.textSecondary,
                                        )
                                        Box(
                                            Modifier
                                                .weight(1f)
                                                .height(5.dp)
                                                .clip(MbTheme.shapes.chip)
                                                .background(MbTheme.colors.fill)
                                        ) {
                                            Box(
                                                Modifier
                                                    .fillMaxWidth(bucket.percent / 100f)
                                                    .height(5.dp)
                                                    .clip(MbTheme.shapes.chip)
                                                    .background(MbTheme.colors.star)
                                            )
                                        }
                                        MbText(
                                            "${bucket.count}",
                                            MbTheme.type.micro,
                                            MbTheme.colors.icon,
                                            modifier = Modifier.width(24.dp),
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }

            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MbChip("Hammasi", state.stars == null) { viewModel.filter(null) }
                    (5 downTo 1).forEach { stars ->
                        MbChip("$stars ★", state.stars == stars) { viewModel.filter(stars) }
                    }
                }
            }

            items(state.reviews, key = { it.id }) { review ->
                MbCard {
                    ReviewRow(review, onLike = { viewModel.like(review.id) })
                }
            }

            if (state.reviews.isEmpty() && !state.loading) {
                item {
                    MbCard {
                        MbText(
                            "Bu filtr bo'yicha sharh topilmadi.",
                            MbTheme.type.bodySmall,
                            MbTheme.colors.icon,
                        )
                    }
                }
            }
        }
    }
}
