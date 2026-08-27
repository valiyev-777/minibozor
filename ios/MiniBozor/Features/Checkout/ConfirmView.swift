import SwiftUI

/// Screen 23 — the last look before the money moves.
struct ConfirmView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("tolovni_tasdiqlash"), onBack: { router.pop() })

                if let preview = model.preview {
                    ScrollView {
                        VStack(spacing: 12) {
                            summaryCard(preview)
                            totalsCard(preview.totals)
                            if let error = model.errorMessage {
                                Text(error)
                                    .mbFont(MB.type.caption)
                                    .foregroundStyle(MB.color.danger)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .padding(.horizontal, 6)
                            }
                            Text(L("tugmani_bosish_orqali_ommaviy_oferta"))
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.textQuaternary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 20)
                        }
                        .padding(12)
                    }
                } else {
                    MBLoading()
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(
                    model.paymentMethod == "cash"
                        ? L("buyurtmani_rasmiylashtirish")
                        : L("tolash_n", Format.grouped(model.preview?.totals.total ?? 0)),
                    enabled: model.ready,
                    loading: model.placing
                ) {
                    Task { await model.place() }
                }
            }
        }
        .onChange(of: model.placedOrderId) { _, orderId in
            if let orderId { router.replace(with: .orderPlaced(orderId: orderId)) }
        }
    }

    private func summaryCard(_ preview: CheckoutPreviewDTO) -> some View {
        MBCard(padding: 6) {
            MBListRow(
                preview.address?.line ?? preview.pickupPoint?.name ?? "",
                glyph: "pin",
                subtitle: preview.address?.meta ?? preview.pickupPoint?.address,
                showChevron: false
            )
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                preview.slot?.label ?? L("punktdan_olish"),
                glyph: "clock",
                subtitle: preview.slot?.note,
                showChevron: false
            )
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                model.paymentMethod == "cash"
                    ? L("naqd_pul") : "Karta ···· \(preview.card?.last4 ?? "")",
                glyph: "card",
                subtitle: model.paymentMethod == "cash"
                    ? L("kuryerga_topshirishda") : preview.card?.brand,
                showChevron: false
            )
            .padding(.horizontal, 10)
        }
    }

    private func totalsCard(_ totals: CartTotalsDTO) -> some View {
        MBCard {
            MBTotalRow(label: "Tovarlar (\(totals.itemsCount))", value: Format.sum(totals.subtotal))
            if totals.discount > 0 {
                MBTotalRow(
                    label: L("chegirma"),
                    value: "−\(Format.grouped(totals.discount))",
                    valueColor: MB.color.success
                )
            }
            MBTotalRow(
                label: L("yetkazish"),
                value: totals.deliveryFee == 0 ? L("bepul") : Format.sum(totals.deliveryFee)
            )
            MBDivider().padding(.vertical, 8)
            MBTotalRow(label: L("tolanadi"), value: Format.sum(totals.total), strong: true)
        }
    }
}
