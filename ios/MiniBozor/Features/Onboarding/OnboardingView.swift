import SwiftUI

private struct OnboardingPage: Identifiable {
    let id = UUID()
    let title: String
    let body: String
    let image: String
    let chip: String?
}

/// Screens 01–04. Copy and imagery come from the design.
struct OnboardingView: View {
    let onFinished: () -> Void

    @State var index = 0

    private var pages: [OnboardingPage] { [
        OnboardingPage(
            title: L("onboarding_1_title"),
            body: L("onboarding_1_body"),
            image: "products/jordan1-low-white.png",
            chip: L("onboarding_1_chip")
        ),
        OnboardingPage(
            title: L("onboarding_2_title"),
            body: L("onboarding_2_body"),
            image: "products/gazelle.png",
            chip: L("onboarding_2_chip")
        ),
        OnboardingPage(
            title: L("onboarding_3_title"),
            body: L("onboarding_3_body"),
            image: "products/airpods.png",
            chip: L("onboarding_3_chip")
        ),
        OnboardingPage(
            title: L("onboarding_4_title"),
            body: L("onboarding_4_body"),
            image: "products/lamp.png",
            chip: L("onboarding_4_chip")
        ),
    ] }

    var body: some View {
        MBScreen(background: MB.color.surfaceAlt) {
            VStack(spacing: 0) {
                header
                TabView(selection: $index) {
                    ForEach(Array(pages.enumerated()), id: \.offset) { offset, page in
                        illustration(page).tag(offset)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))

                dots
                copy
                Spacer(minLength: 0)
                footer
            }
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            BrandMark(size: 26)
            Text(L("app_name")).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
            Spacer()
            Text("\(index + 1) / \(pages.count)")
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.disabled)
        }
        .padding(.horizontal, 26)
        .padding(.top, 8)
    }

    private func illustration(_ page: OnboardingPage) -> some View {
        GeometryReader { proxy in
            let side = min(proxy.size.width * 0.79, proxy.size.height)
            ZStack {
                Circle().fill(MB.color.onboardRing)
                MBProductImage(url: page.image, cornerRadius: side / 2, background: .clear)
                    .padding(26)
                if let chip = page.chip {
                    HStack(spacing: 7) {
                        Circle().fill(MB.color.accent).frame(width: 6, height: 6)
                        Text(chip).mbFont(MB.type.caption).fontWeight(.bold)
                            .foregroundStyle(MB.color.ink)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(MB.color.surface)
                    .clipShape(Capsule())
                    .shadow(color: Color(hex: 0x0E1228, alpha: 0.12), radius: 13, y: 5)
                    .offset(x: -side * 0.28, y: side * 0.28)
                }
            }
            .frame(width: side, height: side)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var dots: some View {
        HStack(spacing: 6) {
            ForEach(0..<pages.count, id: \.self) { position in
                Capsule()
                    .fill(position == index ? MB.color.ink : MB.color.divider)
                    .frame(width: position == index ? 20 : 6, height: 6)
            }
        }
        .padding(.top, 30)
        .animation(.easeOut(duration: 0.2), value: index)
    }

    private var copy: some View {
        VStack(spacing: 11) {
            Text(pages[index].title)
                .mbFont(MB.type.display)
                .foregroundStyle(MB.color.ink)
                .multilineTextAlignment(.center)
            Text(pages[index].body)
                .mbFont(MB.type.bodySmall)
                .foregroundStyle(MB.color.textTertiary)
                .multilineTextAlignment(.center)
        }
        .padding(.horizontal, 38)
        .padding(.top, 20)
    }

    private var footer: some View {
        HStack {
            Button(L("otkazish"), action: onFinished)
                .mbFont(MB.type.label)
                .foregroundStyle(MB.color.textQuaternary)
            Spacer()
            Button {
                if index == pages.count - 1 {
                    onFinished()
                } else {
                    withAnimation { index += 1 }
                }
            } label: {
                Text("→")
                    .mbFont(MB.type.title2)
                    .foregroundStyle(MB.color.onInverse)
                    .frame(width: 56, height: 56)
                    .background(MB.color.inverse)
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 30)
        .padding(.top, 16)
        .padding(.bottom, 32)
    }
}

/// Wordmark: the basket glyph in an accent tile, drawn rather than shipped as
/// an image so it stays sharp at every size.
struct BrandMark: View {
    var size: CGFloat = 26

    var body: some View {
        MBIcon("basket", size: size * 0.62, tint: .white, lineWidth: 2)
            .frame(width: size, height: size)
            .background(MB.color.accent)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.31, style: .continuous))
    }
}
