import SwiftUI

/// A section that folds away, for the parts of a product page most people
/// scroll straight past.
///
/// The chevron turns rather than swapping glyph, and the body expands rather
/// than appearing, so the row above never jumps.
struct MBExpandableSection<Content: View>: View {
    let title: String
    var subtitle: String?
    var initiallyExpanded = false
    @ViewBuilder var content: () -> Content

    @State private var expanded: Bool

    init(
        _ title: String,
        subtitle: String? = nil,
        initiallyExpanded: Bool = false,
        @ViewBuilder content: @escaping () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.initiallyExpanded = initiallyExpanded
        self.content = content
        _expanded = State(initialValue: initiallyExpanded)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                // The height leads and the body follows, rather than both
                // starting together: fading up from nothing while the box is
                // still a sliver is what makes an accordion look cheap.
                withAnimation(.spring(response: 0.34, dampingFraction: 0.9)) {
                    expanded.toggle()
                }
            } label: {
                HStack(alignment: .center) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title).mbFont(MB.type.title3).foregroundStyle(MB.color.ink)
                        if let subtitle {
                            Text(subtitle)
                                .mbFont(MB.type.meta)
                                .foregroundStyle(MB.color.textQuaternary)
                        }
                    }
                    Spacer(minLength: 12)
                    MBIcon("chevron-down", size: 18, tint: MB.color.icon)
                        .rotationEffect(.degrees(expanded ? 180 : 0))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if expanded {
                VStack(alignment: .leading, spacing: 0) { content() }
                    .padding(.top, 10)
                    .transition(
                        .asymmetric(
                            insertion: .opacity.animation(.easeOut(duration: 0.2).delay(0.09)),
                            removal: .opacity.animation(.easeIn(duration: 0.11))
                        )
                    )
            }
        }
    }
}

/// Text clamped to `collapsedLines` with a toggle under it.
///
/// The toggle appears only when the text really is longer than that — measured
/// rather than guessed from the string's length, since how many lines a
/// paragraph takes depends on the screen it is on.
struct MBCollapsibleText: View {
    let text: String
    var collapsedLines = 4
    var style: MBTypography.Style = MB.type.bodySmall

    @State private var expanded = false
    @State private var clampedHeight: CGFloat = 0
    @State private var fullHeight: CGFloat = 0
    /// Sticky: once expanded the two heights match, and reading them live
    /// would take the toggle away just as it was needed to close again.
    @State private var overflows = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(text)
                .mbFont(style)
                .foregroundStyle(MB.color.inkSoft)
                .lineLimit(expanded ? nil : collapsedLines)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background {
                    GeometryReader { geometry in
                        Color.clear.preference(key: ClampedHeight.self,
                                               value: geometry.size.height)
                    }
                }
                // The same paragraph with no limit, drawn to nothing, is what
                // says whether the visible one was actually cut.
                .background {
                    Text(text)
                        .mbFont(style)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background {
                            GeometryReader { geometry in
                                Color.clear.preference(key: FullHeight.self,
                                                       value: geometry.size.height)
                            }
                        }
                        .hidden()
                }
                .animation(.spring(response: 0.34, dampingFraction: 0.9), value: expanded)

            if overflows {
                Button {
                    withAnimation(.spring(response: 0.34, dampingFraction: 0.9)) {
                        expanded.toggle()
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(L(expanded ? "yopish" : "batafsil"))
                            .mbFont(MB.type.label)
                        MBIcon("chevron-down", size: 14, tint: MB.color.accent)
                            .rotationEffect(.degrees(expanded ? 180 : 0))
                    }
                    .foregroundStyle(MB.color.accent)
                }
                .buttonStyle(.plain)
            }
        }
        .onPreferenceChange(ClampedHeight.self) { clampedHeight = $0; updateOverflow() }
        .onPreferenceChange(FullHeight.self) { fullHeight = $0; updateOverflow() }
    }

    private func updateOverflow() {
        guard !expanded else { return }
        overflows = fullHeight - clampedHeight > 1
    }
}

private struct ClampedHeight: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}

private struct FullHeight: PreferenceKey {
    static var defaultValue: CGFloat = 0
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}
