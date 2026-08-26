package uz.minibozor.ui.onboarding

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
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.component.MbPrimaryButton
import uz.minibozor.core.design.mbClickable
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.component.MbProductImage
import uz.minibozor.core.design.component.MbScreen
import uz.minibozor.core.design.icon.MbIcon

private data class OnboardingPage(
    val title: String,
    val body: String,
    val image: String,
    val chip: String?,
)

/**
 * Screens 01–04. Copy and imagery come from the design; the illustration is a
 * product photo inset in a soft circle with a floating chip. The last page
 * swaps the skip/next pair for a single "Boshlash" plus a sign-in link.
 */
@Composable
private fun pages(mediaBase: String) = listOf(
    OnboardingPage(
        title = stringResource(R.string.onboarding_1_title),
        body = stringResource(R.string.onboarding_1_body),
        image = "$mediaBase/products/jordan1-low-white.png",
        chip = stringResource(R.string.onboarding_1_chip),
    ),
    OnboardingPage(
        title = stringResource(R.string.onboarding_2_title),
        body = stringResource(R.string.onboarding_2_body),
        image = "$mediaBase/products/gazelle.png",
        chip = stringResource(R.string.onboarding_2_chip),
    ),
    OnboardingPage(
        title = stringResource(R.string.onboarding_3_title),
        body = stringResource(R.string.onboarding_3_body),
        image = "$mediaBase/products/airpods.png",
        chip = stringResource(R.string.onboarding_3_chip),
    ),
    OnboardingPage(
        title = stringResource(R.string.onboarding_4_title),
        body = stringResource(R.string.onboarding_4_body),
        image = "$mediaBase/products/lamp.png",
        chip = stringResource(R.string.onboarding_4_chip),
    ),
)

@Composable
fun OnboardingScreen(
    mediaBase: String,
    onFinished: () -> Unit,
    onSignIn: () -> Unit = onFinished,
) {
    val items = pages(mediaBase)
    val pagerState = rememberPagerState(pageCount = { items.size })
    val scope = rememberCoroutineScope()

    MbScreen(background = MbTheme.colors.surfaceAlt) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 26.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                BrandMark()
                Spacer(Modifier.width(8.dp))
                MbText("Mini Bozor", MbTheme.type.label.copy(fontSize = MbTheme.type.bodySmall.fontSize))
                Spacer(Modifier.weight(1f))
                MbText(
                    "${pagerState.currentPage + 1} / ${items.size}",
                    MbTheme.type.caption,
                    MbTheme.colors.disabled,
                )
            }

            HorizontalPager(
                state = pagerState,
                modifier = Modifier.weight(1f),
            ) { page ->
                PageContent(items[page])
            }

            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(top = 30.dp),
                horizontalArrangement = Arrangement.Center,
            ) {
                repeat(items.size) { index ->
                    val active = index == pagerState.currentPage
                    Box(
                        Modifier
                            .padding(horizontal = 3.dp)
                            .size(width = if (active) 20.dp else 6.dp, height = 6.dp)
                            .clip(RoundedCornerShape(3.dp))
                            .background(if (active) MbTheme.colors.ink else MbTheme.colors.divider)
                    )
                }
            }

            Column(Modifier.padding(horizontal = 38.dp, vertical = 20.dp)) {
                MbText(
                    items[pagerState.currentPage].title,
                    MbTheme.type.display,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(11.dp))
                MbText(
                    items[pagerState.currentPage].body,
                    MbTheme.type.bodySmall,
                    MbTheme.colors.textTertiary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (pagerState.currentPage == items.lastIndex) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 24.dp)
                        .padding(top = 18.dp, bottom = 26.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    MbPrimaryButton(
                        text = stringResource(R.string.boshlash),
                        onClick = onFinished,
                        container = MbTheme.colors.inverse,
                    )
                    Spacer(Modifier.height(14.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        MbText(
                            stringResource(R.string.hisobingiz_bormi),
                            MbTheme.type.caption,
                            MbTheme.colors.textQuaternary,
                        )
                        MbText(
                            stringResource(R.string.kirish),
                            MbTheme.type.label,
                            MbTheme.colors.accent,
                            modifier = Modifier.mbTap(onClick = onSignIn),
                        )
                    }
                }
            } else {
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 26.dp)
                        .padding(bottom = 28.dp, top = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    MbText(
                        stringResource(R.string.otkazish),
                        MbTheme.type.label,
                        MbTheme.colors.textQuaternary,
                        modifier = Modifier.mbTap(onClick = onFinished),
                    )
                    Spacer(Modifier.weight(1f))
                    NextButton {
                        scope.launch {
                            pagerState.animateScrollToPage(pagerState.currentPage + 1)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun PageContent(page: OnboardingPage) {
    Box(
        Modifier
            .fillMaxWidth()
            .padding(top = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .fillMaxWidth(0.79f)
                .aspectRatio(1f),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                Modifier
                    .fillMaxSize()
                    .clip(CircleShape)
                    .background(MbTheme.colors.onboardRing)
            )
            MbProductImage(
                page.image,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(26.dp),
                shape = CircleShape,
                background = Color.Transparent,
            )
            if (page.chip != null) {
                Row(
                    Modifier
                        .align(Alignment.BottomStart)
                        .padding(bottom = 44.dp)
                        .clip(CircleShape)
                        .background(MbTheme.colors.surface)
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(7.dp),
                ) {
                    Box(
                        Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(MbTheme.colors.accent)
                    )
                    MbText(page.chip, MbTheme.type.caption.copy(
                        fontWeight = androidx.compose.ui.text.font.FontWeight.Bold))
                }
            }
        }
    }
}

@Composable
private fun NextButton(onClick: () -> Unit) {
    Row(
        Modifier
            .mbClickable(CircleShape, onClick = onClick)
            .background(MbTheme.colors.inverse)
            .padding(start = 24.dp, end = 20.dp, top = 15.dp, bottom = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        MbText(stringResource(R.string.keyingi), MbTheme.type.label, MbTheme.colors.onInverse)
        MbText("→", MbTheme.type.title3, MbTheme.colors.onInverse)
    }
}

/** Wordmark stand-in: the app's basket glyph in an accent tile. */
@Composable
fun BrandMark(size: androidx.compose.ui.unit.Dp = 26.dp) {
    Box(
        Modifier
            .size(size)
            .clip(RoundedCornerShape(size * 0.31f))
            .background(MbTheme.colors.accent),
        contentAlignment = Alignment.Center,
    ) {
        MbIcon("basket", size = size * 0.62f, tint = Color.White, strokeWidth = 2f)
    }
}
