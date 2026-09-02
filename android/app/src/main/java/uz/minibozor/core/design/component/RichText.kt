package uz.minibozor.core.design.component

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import uz.minibozor.R
import uz.minibozor.core.design.MbText
import uz.minibozor.core.design.MbTheme
import uz.minibozor.core.design.mbTap
import uz.minibozor.core.design.icon.MbIcon
import uz.minibozor.core.util.mediaUrl

/**
 * One piece of a written description.
 *
 * A seller writing about a pair of shoes writes headings, lists and photographs,
 * not one paragraph — so the description arrives as marked-up text and is drawn
 * as these rather than poured into a single [MbText].
 */
sealed interface MbBlock {
    data class Paragraph(val text: String) : MbBlock
    data class Heading(val text: String) : MbBlock
    data class Bullets(val items: List<String>) : MbBlock
    data class Picture(val url: String, val caption: String) : MbBlock
}

private val ImageExtensions = listOf(".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")

/** `![alt](products/gazelle.png)` */
private val MarkdownImage = Regex("""^!\[([^]]*)]\(([^)]+)\)$""")

private fun String.looksLikeImage(): Boolean {
    val path = substringBefore('?').lowercase()
    return ImageExtensions.any { path.endsWith(it) } && !contains(' ')
}

/**
 * Splits a written description into blocks.
 *
 * The mark-up is the small subset a shop actually needs, and anything it does
 * not recognise stays plain text — a description written as one paragraph comes
 * out as one paragraph, which is what most of them are.
 *
 * - `## Materiali` — a heading
 * - `- Tabiiy zamsh` (or `*`, `•`) — a bullet, consecutive ones grouped
 * - `![Yon ko'rinish](products/gazelle.png)`, or a bare line ending in an image
 *   extension — a photograph
 * - a blank line ends a paragraph
 */
fun parseRichText(source: String): List<MbBlock> {
    val blocks = mutableListOf<MbBlock>()
    val paragraph = StringBuilder()
    val bullets = mutableListOf<String>()

    fun flushParagraph() {
        if (paragraph.isNotBlank()) blocks += MbBlock.Paragraph(paragraph.toString().trim())
        paragraph.clear()
    }

    fun flushBullets() {
        if (bullets.isNotEmpty()) blocks += MbBlock.Bullets(bullets.toList())
        bullets.clear()
    }

    fun flush() {
        flushParagraph()
        flushBullets()
    }

    for (raw in source.lines()) {
        val line = raw.trim()
        val image = MarkdownImage.matchEntire(line)
        when {
            line.isEmpty() -> flush()

            image != null -> {
                flush()
                blocks += MbBlock.Picture(
                    url = image.groupValues[2].trim(),
                    caption = image.groupValues[1].trim(),
                )
            }

            line.looksLikeImage() -> {
                flush()
                blocks += MbBlock.Picture(line, "")
            }

            line.startsWith("#") -> {
                flush()
                blocks += MbBlock.Heading(line.trimStart('#').trim())
            }

            line.startsWith("- ") || line.startsWith("* ") || line.startsWith("• ") -> {
                flushParagraph()
                bullets += line.drop(2).trim()
            }

            else -> {
                flushBullets()
                // Kept as one paragraph: a hard-wrapped source line is not a
                // new line on a phone, it is the same sentence continuing.
                if (paragraph.isNotEmpty()) paragraph.append(' ')
                paragraph.append(line)
            }
        }
    }
    flush()
    return blocks
}

/**
 * A written description: headings, lists and the shop's own photographs, folded
 * down to its opening lines until someone asks for the rest.
 *
 * Collapsed it shows the first paragraph clamped to [collapsedLines] and nothing
 * else, so a page-long description costs the same room as a short one; the
 * toggle only appears when there really is more to see.
 */
@Composable
fun MbRichText(
    text: String,
    modifier: Modifier = Modifier,
    collapsedLines: Int = 5,
    style: TextStyle = MbTheme.type.bodySmall,
) {
    val blocks = remember(text) { parseRichText(text) }
    if (blocks.isEmpty()) return

    var expanded by remember(text) { mutableStateOf(false) }
    var clamped by remember(text) { mutableStateOf(false) }
    val turn by animateFloatAsState(
        targetValue = if (expanded) 180f else 0f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 380f),
        label = "richMore",
    )

    // Collapsed, only the opening paragraph is drawn. Clamping the whole lot to
    // a line count would put a cropped photograph under a cropped sentence.
    val shown = if (expanded) blocks else blocks.take(1)
    val hasMore = blocks.size > 1 || clamped

    Column(
        modifier
            .fillMaxWidth()
            .animateContentSize(spring(dampingRatio = 0.9f, stiffness = 300f))
    ) {
        shown.forEachIndexed { index, block ->
            if (index > 0) Spacer(Modifier.height(if (block is MbBlock.Heading) 16.dp else 10.dp))
            when (block) {
                is MbBlock.Heading -> MbText(block.text, MbTheme.type.sectionHead)

                is MbBlock.Paragraph -> MbText(
                    block.text,
                    style,
                    MbTheme.colors.inkSoft,
                    maxLines = if (expanded) Int.MAX_VALUE else collapsedLines,
                    onTextLayout = { result: TextLayoutResult ->
                        if (!expanded && result.hasVisualOverflow) clamped = true
                    },
                )

                is MbBlock.Bullets -> Column(
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    block.items.forEach { item ->
                        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                            // A dot rather than a hyphen: a hyphen at 12.5 sp
                            // sits on the baseline and reads as a dash in the
                            // sentence.
                            Box(
                                Modifier
                                    .padding(top = 7.dp)
                                    .size(4.dp)
                                    .clip(CircleShape)
                                    .background(MbTheme.colors.hairlineStrong)
                            )
                            MbText(item, style, MbTheme.colors.inkSoft)
                        }
                    }
                }

                is MbBlock.Picture -> Column {
                    val resolved = block.url.mediaUrl()
                    if (resolved != null) {
                        AsyncImage(
                            model = resolved,
                            contentDescription = block.caption.ifBlank { null },
                            // Full width, its own height: a description photo
                            // is whatever shape the shop uploaded, and forcing
                            // it square would crop the half of it that carries
                            // the point.
                            contentScale = ContentScale.FillWidth,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 120.dp)
                                .clip(MbTheme.shapes.tile)
                                .background(MbTheme.colors.photoWarmAlt),
                        )
                    }
                    if (block.caption.isNotBlank()) {
                        Spacer(Modifier.height(6.dp))
                        MbText(block.caption, MbTheme.type.meta, MbTheme.colors.textQuaternary)
                    }
                }
            }
        }

        if (hasMore) {
            Spacer(Modifier.height(12.dp))
            Row(
                Modifier
                    .clip(MbTheme.shapes.chip)
                    .mbTap { expanded = !expanded }
                    .padding(horizontal = 2.dp, vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                MbText(
                    stringResource(if (expanded) R.string.yopish else R.string.batafsil),
                    MbTheme.type.label,
                    MbTheme.colors.accent,
                )
                MbIcon(
                    "chevron-down",
                    size = 14.dp,
                    tint = MbTheme.colors.accent,
                    modifier = Modifier.graphicsLayer { rotationZ = turn },
                )
            }
        }
    }
}
