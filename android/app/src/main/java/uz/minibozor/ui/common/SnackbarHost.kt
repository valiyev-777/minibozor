package uz.minibozor.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme

/** Lightweight toast in the design's ink pill, used for "Savatga qo'shildi". */
@Composable
fun MbToastHost(message: MutableState<String?>, modifier: Modifier = Modifier) {
    val text = message.value
    LaunchedEffect(text) {
        if (text != null) {
            delay(2_200)
            message.value = null
        }
    }
    if (text != null) {
        Box(
            modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 12.dp),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                Modifier
                    .clip(MbTheme.shapes.chip)
                    .background(MbTheme.colors.ink)
                    .padding(horizontal = 18.dp, vertical = 12.dp)
            ) {
                MbText(text, MbTheme.type.caption, Color.White)
            }
        }
    }
}

@Composable
fun rememberToast(): MutableState<String?> = remember { mutableStateOf(null) }
