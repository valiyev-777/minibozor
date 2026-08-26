import SwiftUI

/// A loading placeholder that sweeps a highlight across itself.
///
/// Used instead of a spinner while a screen's first payload is in flight: a
/// skeleton shaped like the content that is coming reads as "nearly there",
/// where a spinner alone on an empty screen reads as "nothing here".
struct MBSkeleton: View {
    var cornerRadius: CGFloat = MB.metric.radiusM

    @Environment(\.colorScheme) private var scheme
    @State private var sweep: CGFloat = -1

    var body: some View {
        GeometryReader { geometry in
            let band = geometry.size.width * 0.55
            RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .fill(MB.color.fill)
                .overlay {
                    LinearGradient(
                        colors: [.clear, highlight, .clear],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: band)
                    .offset(x: sweep * (geometry.size.width + band))
                }
                .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        }
        .onAppear {
            withAnimation(.linear(duration: 1.25).repeatForever(autoreverses: false)) {
                sweep = 1
            }
        }
    }
}

private extension MBSkeleton {
    var highlight: Color {
        MB.color.hairlineStrong.opacity(scheme == .dark ? 0.5 : 0.35)
    }
}

/// What the product page looks like before its payload lands.
struct ProductSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            MBSkeleton(cornerRadius: 0)
                .frame(height: ProductHero.height)
            VStack(alignment: .leading, spacing: 0) {
                MBSkeleton(cornerRadius: MB.metric.radiusS)
                    .frame(width: 140, height: 28)
                Spacer().frame(height: 12)
                MBSkeleton(cornerRadius: MB.metric.radiusS).frame(height: 18)
                Spacer().frame(height: 8)
                MBSkeleton(cornerRadius: MB.metric.radiusS)
                    .frame(width: 200, height: 14)
                Spacer().frame(height: 22)
                ForEach(0..<3, id: \.self) { _ in
                    MBSkeleton(cornerRadius: MB.metric.radiusS).frame(height: 13)
                    Spacer().frame(height: 9)
                }
            }
            .padding(16)
            Spacer()
        }
    }
}
