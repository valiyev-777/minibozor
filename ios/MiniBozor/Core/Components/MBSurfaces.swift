import SwiftUI

/// The page shell every screen sits in.
struct MBScreen<Content: View>: View {
    var background: Color = MB.color.canvas
    @ViewBuilder var content: Content

    var body: some View {
        ZStack {
            background.ignoresSafeArea()
            content
        }
        .toolbarBackground(.hidden, for: .navigationBar)
    }
}

/// The white rounded panel the design groups content into.
struct MBCard<Content: View>: View {
    var padding: CGFloat = 16
    var background: Color = MB.color.surface
    /// Square it off for a section that runs edge to edge — rounded corners
    /// against the screen edge look like a card that did not quite fit.
    var cornerRadius: CGFloat = MB.metric.radiusXXL
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(padding)
        .background(background)
        .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
    }
}

/// Inner-screen header: circular back button, centred title, one trailing action.
struct MBTopBar<Trailing: View>: View {
    let title: String
    var subtitle: String?
    var onBack: (() -> Void)?
    var background: Color = MB.color.surface
    @ViewBuilder var trailing: Trailing

    var body: some View {
        HStack(spacing: 0) {
            if let onBack {
                MBCircleButton(glyph: "ret", action: onBack)
            } else {
                Color.clear.frame(width: 36, height: 36)
            }
            VStack(spacing: 1) {
                if !title.isEmpty {
                    Text(title).mbFont(MB.type.title3).foregroundStyle(MB.color.ink)
                        .lineLimit(1)
                }
                if let subtitle {
                    Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.textQuaternary)
                        .lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity)
            trailing.frame(width: 36, height: 36)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(background)
    }
}

extension MBTopBar where Trailing == EmptyView {
    init(_ title: String, subtitle: String? = nil, background: Color = MB.color.surface, onBack: (() -> Void)? = nil) {
        self.init(title: title, subtitle: subtitle, onBack: onBack, background: background) { EmptyView() }
    }
}

struct MBCircleButton: View {
    let glyph: String
    var size: CGFloat = 36
    var tint: Color = MB.color.ink
    var background: Color = MB.color.fill
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            MBIcon(glyph, size: size * 0.5, tint: tint, lineWidth: 1.9)
                .frame(width: size, height: size)
                .background(background)
                .clipShape(Circle())
        }
        .buttonStyle(.plain)
    }
}

struct SectionHeader: View {
    let title: String
    var subtitle: String?
    var actionLabel: String?
    var onAction: (() -> Void)?

    var body: some View {
        HStack(alignment: .lastTextBaseline, spacing: 8) {
            Text(title).mbFont(MB.type.sectionHead).foregroundStyle(MB.color.ink)
            if let subtitle {
                Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.icon).lineLimit(1)
            }
            Spacer(minLength: 0)
            if let actionLabel, let onAction {
                Button(action: onAction) {
                    Text(actionLabel).mbFont(MB.type.label).foregroundStyle(MB.color.accent)
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct MBDivider: View {
    var inset: CGFloat = 0

    var body: some View {
        Rectangle()
            .fill(MB.color.border)
            .frame(height: 1)
            .padding(.leading, inset)
    }
}
