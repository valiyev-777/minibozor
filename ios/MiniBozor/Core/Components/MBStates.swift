import SwiftUI

struct MBLoading: View {
    var body: some View {
        ProgressView()
            .tint(MB.color.accent)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Empty and error states share one layout — the empty cart (screen 18) is the
/// canonical example.
struct MBEmptyState: View {
    let glyph: String
    let title: String
    let message: String
    var actionLabel: String?
    var onAction: (() -> Void)?

    var body: some View {
        VStack(spacing: 0) {
            MBIcon(glyph, size: 44, tint: MB.color.hairlineStrong, lineWidth: 1.4)
                .frame(width: 120, height: 120)
                .background(MB.color.onboardRing)
                .clipShape(Circle())
            Spacer().frame(height: 22)
            Text(title)
                .mbFont(MB.type.title2)
                .foregroundStyle(MB.color.ink)
                .multilineTextAlignment(.center)
            Spacer().frame(height: 8)
            Text(message)
                .mbFont(MB.type.bodySmall)
                .foregroundStyle(MB.color.textTertiary)
                .multilineTextAlignment(.center)
            if let actionLabel, let onAction {
                Spacer().frame(height: 24)
                MBPrimaryButton(actionLabel, action: onAction)
            }
        }
        .padding(.horizontal, 40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct MBErrorState: View {
    let message: String
    let onRetry: () -> Void

    var body: some View {
        MBEmptyState(
            glyph: "ret",
            title: "Nimadir noto'g'ri ketdi",
            message: message,
            actionLabel: "Qayta urinish",
            onAction: onRetry
        )
    }
}

/// Renders loading and error uniformly so screens only describe the happy path.
struct LoadStateView<Value, Content: View>: View {
    let state: LoadState<Value>
    let onRetry: () -> Void
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        switch state {
        case .loading:
            MBLoading()
        case .failed(let message):
            MBErrorState(message: message, onRetry: onRetry)
        case .ready(let value):
            content(value)
        }
    }
}

/// Lightweight toast in the design's ink pill, for "Savatga qo'shildi".
struct MBToast: ViewModifier {
    @Binding var message: String?

    func body(content: Content) -> some View {
        content.overlay(alignment: .bottom) {
            if let message {
                Text(message)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 18)
                    .padding(.vertical, 12)
                    .background(MB.color.ink)
                    .clipShape(Capsule())
                    .padding(.bottom, 100)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .task(id: message) {
                        try? await Task.sleep(for: .seconds(2.2))
                        withAnimation { self.message = nil }
                    }
            }
        }
        .animation(.easeOut(duration: 0.2), value: message)
    }
}

extension View {
    func mbToast(_ message: Binding<String?>) -> some View {
        modifier(MBToast(message: message))
    }
}
