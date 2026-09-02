import SwiftUI

/// One piece of a written description.
///
/// A seller writing about a pair of shoes writes headings, lists and
/// photographs, not one paragraph — so the description arrives as marked-up text
/// and is drawn as these rather than poured into a single `Text`. The same
/// blocks, and the same small subset of mark-up, as the Android client's
/// `MbRichText`.
enum MBBlock: Identifiable {
    case paragraph(String)
    case heading(String)
    case bullets([String])
    case picture(url: String, caption: String)

    var id: String {
        switch self {
        case .paragraph(let text): return "p:\(text.prefix(24))"
        case .heading(let text): return "h:\(text)"
        case .bullets(let items): return "b:\(items.first ?? "")\(items.count)"
        case .picture(let url, _): return "i:\(url)"
        }
    }
}

/// `![alt](products/gazelle.png)`
private let markdownImage = try? NSRegularExpression(
    pattern: "^!\\[([^\\]]*)\\]\\(([^)]+)\\)$"
)

private let imageExtensions = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"]

private extension String {
    var looksLikeImage: Bool {
        let path = split(separator: "?").first.map(String.init)?.lowercased() ?? ""
        return imageExtensions.contains(where: path.hasSuffix) && !contains(" ")
    }
}

/// Splits a written description into blocks.
///
/// The mark-up is the small subset a shop actually needs, and anything it does
/// not recognise stays plain text — a description written as one paragraph comes
/// out as one paragraph, which is what most of them are.
///
/// - `## Materiali` — a heading
/// - `- Tabiiy zamsh` (or `*`, `•`) — a bullet, consecutive ones grouped
/// - `![Yon ko'rinish](products/gazelle.png)`, or a bare line ending in an image
///   extension — a photograph
/// - a blank line ends a paragraph
func parseRichText(_ source: String) -> [MBBlock] {
    var blocks: [MBBlock] = []
    var paragraph = ""
    var bullets: [String] = []

    func flushParagraph() {
        let text = paragraph.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty { blocks.append(.paragraph(text)) }
        paragraph = ""
    }

    func flushBullets() {
        if !bullets.isEmpty { blocks.append(.bullets(bullets)) }
        bullets = []
    }

    func flush() {
        flushParagraph()
        flushBullets()
    }

    for raw in source.components(separatedBy: .newlines) {
        let line = raw.trimmingCharacters(in: .whitespaces)

        if line.isEmpty {
            flush()
            continue
        }

        if let match = markdownImage?.firstMatch(
            in: line,
            range: NSRange(line.startIndex..., in: line)
        ), match.numberOfRanges == 3,
           let captionRange = Range(match.range(at: 1), in: line),
           let urlRange = Range(match.range(at: 2), in: line) {
            flush()
            blocks.append(.picture(
                url: String(line[urlRange]).trimmingCharacters(in: .whitespaces),
                caption: String(line[captionRange]).trimmingCharacters(in: .whitespaces)
            ))
            continue
        }

        if line.looksLikeImage {
            flush()
            blocks.append(.picture(url: line, caption: ""))
            continue
        }

        if line.hasPrefix("#") {
            flush()
            blocks.append(.heading(
                line.drop(while: { $0 == "#" }).trimmingCharacters(in: .whitespaces)
            ))
            continue
        }

        if line.hasPrefix("- ") || line.hasPrefix("* ") || line.hasPrefix("• ") {
            flushParagraph()
            bullets.append(String(line.dropFirst(2)).trimmingCharacters(in: .whitespaces))
            continue
        }

        flushBullets()
        // Kept as one paragraph: a hard-wrapped source line is not a new line on
        // a phone, it is the same sentence continuing.
        if !paragraph.isEmpty { paragraph += " " }
        paragraph += line
    }

    flush()
    return blocks
}

/// A written description: headings, lists and the shop's own photographs, folded
/// down to its opening lines until someone asks for the rest.
///
/// Collapsed it shows the first block and nothing else, so a page-long
/// description costs the same room as a short one; the toggle only appears when
/// there really is more to see.
struct MBRichText: View {
    let text: String
    var collapsedLines = 5
    var style: MBTypography.Style = MB.type.bodySmall

    @State private var expanded = false

    private var blocks: [MBBlock] { parseRichText(text) }

    var body: some View {
        let all = blocks
        // Collapsed, only the opening block is drawn. Clamping the whole lot to
        // a line count would put a cropped photograph under a cropped sentence.
        let shown = expanded ? all : Array(all.prefix(1))

        VStack(alignment: .leading, spacing: 0) {
            ForEach(Array(shown.enumerated()), id: \.offset) { index, block in
                if index > 0 {
                    Spacer().frame(height: heading(block) ? 16 : 10)
                }
                view(for: block)
            }

            if all.count > 1 {
                Spacer().frame(height: 10)
                Button {
                    withAnimation(MBMotion.ease) { expanded.toggle() }
                } label: {
                    HStack(spacing: 4) {
                        Text(expanded ? L("yopish") : L("batafsil"))
                            .mbFont(MB.type.label)
                            .foregroundStyle(MB.color.accent)
                        MBIcon("chevron-down", size: 14, tint: MB.color.accent)
                            .rotationEffect(.degrees(expanded ? 180 : 0))
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func heading(_ block: MBBlock) -> Bool {
        if case .heading = block { return true }
        return false
    }

    @ViewBuilder
    private func view(for block: MBBlock) -> some View {
        switch block {
        case .heading(let text):
            Text(text).mbFont(MB.type.sectionHead).foregroundStyle(MB.color.ink)

        case .paragraph(let text):
            Text(text)
                .mbFont(style)
                .foregroundStyle(MB.color.inkSoft)
                .lineLimit(expanded ? nil : collapsedLines)
                .frame(maxWidth: .infinity, alignment: .leading)

        case .bullets(let items):
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(items.enumerated()), id: \.offset) { _, item in
                    HStack(alignment: .top, spacing: 9) {
                        // A dot rather than a hyphen: a hyphen at 12.5 pt sits
                        // on the baseline and reads as a dash in the sentence.
                        Circle()
                            .fill(MB.color.hairlineStrong)
                            .frame(width: 4, height: 4)
                            .padding(.top, 7)
                        Text(item)
                            .mbFont(style)
                            .foregroundStyle(MB.color.inkSoft)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }

        case .picture(let url, let caption):
            VStack(alignment: .leading, spacing: 6) {
                MBProductImage(url: url, cornerRadius: MB.metric.radiusL)
                    .aspectRatio(1, contentMode: .fit)
                if !caption.isEmpty {
                    Text(caption).mbFont(MB.type.meta).foregroundStyle(MB.color.textQuaternary)
                }
            }
        }
    }
}
