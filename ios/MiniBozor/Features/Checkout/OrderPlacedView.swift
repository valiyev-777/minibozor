import SwiftUI

/// Screen 24 — Buyurtma qabul qilindi.
struct OrderPlacedView: View {
    let orderId: Int

    @Environment(Router.self) var router
    @State var model = OrderDetailModel()

    var body: some View {
        MBScreen(background: MB.color.surface) {
            VStack(spacing: 0) {
                Spacer().frame(height: 40)
                MBIcon("box", size: 40, tint: MB.color.success, lineWidth: 1.6)
                    .frame(width: 96, height: 96)
                    .background(MB.color.successBg)
                    .clipShape(Circle())
                Spacer().frame(height: 22)
                Text("Buyurtma qabul qilindi")
                    .mbFont(MB.type.title1)
                    .foregroundStyle(MB.color.ink)
                    .multilineTextAlignment(.center)
                Spacer().frame(height: 8)
                Text(model.order.map { "\($0.code) raqami bilan qabul qildik" }
                     ?? "Tez orada yig'ishni boshlaymiz")
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)

                if let order = model.order {
                    Spacer().frame(height: 26)
                    MBCard(background: MB.color.canvas) {
                        MBKeyValueRow(key: "Buyurtma", value: order.code)
                        if let created = UzDate.parseDateTime(order.createdAt) {
                            MBKeyValueRow(key: "Sana", value: UzDate.dayTime(created))
                        }
                        MBKeyValueRow(key: "Yetkazish", value: order.etaLabel)
                        MBKeyValueRow(key: "To'lov", value: order.paymentLabel)
                        MBKeyValueRow(key: "Jami", value: Format.sum(order.total))
                    }
                }
                Spacer()
            }
            .padding(.horizontal, 24)
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton("Buyurtmani kuzatish", leadingGlyph: "box") {
                    router.replace(with: .tracking(orderId: orderId))
                }
                MBSecondaryButton("Bosh sahifaga") { router.popToRoot() }
            }
        }
        .task { await model.load(id: orderId) }
    }
}
