import SwiftUI

/// Filled accent button — the main call to action on almost every screen.
struct MBPrimaryButton: View {
    let title: String
    var enabled: Bool = true
    var loading: Bool = false
    var leadingGlyph: String?
    var container: Color = MB.color.accent
    var contentColor: Color = .white
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if loading {
                    ProgressView().tint(contentColor)
                } else {
                    if let leadingGlyph {
                        MBIcon(leadingGlyph, size: 18, tint: contentColor, lineWidth: 1.9)
                    }
                    Text(title).mbFont(MB.type.bodyBold).foregroundStyle(contentColor)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: MB.metric.buttonHeight)
            .background(enabled ? container : MB.color.disabled)
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous))
        }
        .buttonStyle(PressScaleStyle())
        .disabled(!enabled || loading)
    }

    init(
        _ title: String,
        enabled: Bool = true,
        loading: Bool = false,
        leadingGlyph: String? = nil,
        container: Color = MB.color.accent,
        contentColor: Color = .white,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.enabled = enabled
        self.loading = loading
        self.leadingGlyph = leadingGlyph
        self.container = container
        self.contentColor = contentColor
        self.action = action
    }
}

/// Outlined button — secondary paths.
struct MBSecondaryButton: View {
    let title: String
    var enabled: Bool = true
    var contentColor: Color = MB.color.ink
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .mbFont(MB.type.bodyBold)
                .foregroundStyle(contentColor)
                .frame(maxWidth: .infinity)
                .frame(height: MB.metric.buttonHeight)
                .background(MB.color.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous)
                        .stroke(MB.color.border, lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous))
        }
        .buttonStyle(PressScaleStyle())
        .opacity(enabled ? 1 : 0.5)
        .disabled(!enabled)
    }

    init(_ title: String, enabled: Bool = true, contentColor: Color = MB.color.ink, action: @escaping () -> Void) {
        self.title = title
        self.enabled = enabled
        self.contentColor = contentColor
        self.action = action
    }
}

/// Destructive action — cancelling an order, signing out.
struct MBDangerButton: View {
    let title: String
    var loading: Bool = false
    let action: () -> Void

    var body: some View {
        MBPrimaryButton(title, loading: loading, container: MB.color.danger, action: action)
    }

    init(_ title: String, loading: Bool = false, action: @escaping () -> Void) {
        self.title = title
        self.loading = loading
        self.action = action
    }
}

/// Pinned footer: white, safe-area aware.
struct MBBottomBar<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 10) {
            content
        }
        .padding(.horizontal, 20)
        .padding(.top, 14)
        .padding(.bottom, 14)
        .frame(maxWidth: .infinity)
        .background(MB.color.surface)
    }
}

private struct PressScaleStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}
