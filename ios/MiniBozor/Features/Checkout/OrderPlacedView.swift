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
                Text(L("buyurtma_qabul_qilindi"))
                    .mbFont(MB.type.title1)
                    .foregroundStyle(MB.color.ink)
                    .multilineTextAlignment(.center)
                Spacer().frame(height: 8)
                Text(model.order.map { "\($0.code) raqami bilan qabul qildik" }
                     ?? L("tez_orada_yigishni_boshlaymiz"))
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)

                if let order = model.order {
                    Spacer().frame(height: 26)
                    MBCard(background: MB.color.canvas) {
                        MBKeyValueRow(key: L("buyurtma"), value: order.code)
                        if let created = UzDate.parseDateTime(order.createdAt) {
                            MBKeyValueRow(key: L("sana"), value: UzDate.dayTime(created))
                        }
                        MBKeyValueRow(key: L("yetkazish"), value: order.etaLabel)
                        MBKeyValueRow(key: L("tolov"), value: order.paymentLabel)
                        MBKeyValueRow(key: L("jami"), value: Format.sum(order.total))
                    }
                }
                Spacer()
            }
            .padding(.horizontal, 24)
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(L("buyurtmani_kuzatish"), leadingGlyph: "box") {
                    router.replace(with: .orderDetail(orderId: orderId))
                }
                MBSecondaryButton(L("bosh_sahifaga")) { router.popToRoot() }
            }
        }
        .task { await model.load(id: orderId) }
    }
}
