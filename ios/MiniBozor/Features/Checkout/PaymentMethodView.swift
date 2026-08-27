import SwiftUI

/// Screen 22 — saved cards plus cash on delivery.
struct PaymentMethodView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("tolov_usuli"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        methodsCard
                        MBCard(padding: 6) {
                            MBListRow(
                                L("yangi_karta_qoshish"),
                                glyph: "card",
                                subtitle: L("humo_uzcard_visa"),
                                tint: MB.color.accent
                            ) {
                                router.push(.addCard)
                            }
                            .padding(.horizontal, 10)
                        }
                        note
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .onAppear { Task { await model.reloadCards() } }
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(
                    L("tanlash"),
                    enabled: model.paymentMethod == "cash" || model.cardId != nil
                ) {
                    router.pop()
                }
            }
        }
    }

    private var methodsCard: some View {
        MBCard(padding: 6) {
            ForEach(Array(model.cards.enumerated()), id: \.element.id) { offset, card in
                MBRadioRow(
                    label: "Karta ···· \(card.last4)",
                    subtitle: card.isExpired ? L("muddati_otgan") : card.brand,
                    selected: model.paymentMethod == "card" && model.cardId == card.id,
                    onSelect: {
                        guard !card.isExpired else { return }
                        Task { await model.selectCard(card.id) }
                    }
                ) {
                    RoundedRectangle(cornerRadius: MB.metric.radiusXS, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [
                                    MB.color.cardFrom,
                                    card.isExpired ? MB.color.disabled : MB.color.accent,
                                ],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 46, height: 30)
                }
                .padding(.horizontal, 10)
                if offset != model.cards.count - 1 { MBDivider(inset: 68) }
            }

            if !model.cards.isEmpty { MBDivider(inset: 68) }

            MBRadioRow(
                label: L("naqd_pul"),
                subtitle: L("kuryerga_topshirishda"),
                selected: model.paymentMethod == "cash",
                onSelect: { Task { await model.selectCash() } }
            ) {
                MBIcon("basket", size: 16, tint: MB.color.success)
                    .frame(width: 46, height: 30)
                    .background(MB.color.successBg)
                    .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXS, style: .continuous))
            }
            .padding(.horizontal, 10)
        }
    }

    private var note: some View {
        HStack(alignment: .top, spacing: 8) {
            MBIcon("gear", size: 16, tint: MB.color.icon)
            Text(L("karta_ma_lumotlari_tolov_provayderi"))
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textQuaternary)
        }
        .padding(.horizontal, 6)
    }
}
