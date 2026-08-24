import SwiftUI

/// Screen 23 — the last look before the money moves.
struct ConfirmView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("To'lovni tasdiqlash", onBack: { router.pop() })

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
                            Text("Tugmani bosish orqali ommaviy oferta shartlariga rozilik bildirasiz.")
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
                        ? "Buyurtmani rasmiylashtirish"
                        : "To'lash · \(Format.grouped(model.preview?.totals.total ?? 0))",
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
                preview.slot?.label ?? "Punktdan olish",
                glyph: "clock",
                subtitle: preview.slot?.note,
                showChevron: false
            )
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                model.paymentMethod == "cash"
                    ? "Naqd pul" : "Karta ···· \(preview.card?.last4 ?? "")",
                glyph: "card",
                subtitle: model.paymentMethod == "cash"
                    ? "Kuryerga topshirishda" : preview.card?.brand,
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
                    label: "Chegirma",
                    value: "−\(Format.grouped(totals.discount))",
                    valueColor: MB.color.success
                )
            }
            MBTotalRow(
                label: "Yetkazish",
                value: totals.deliveryFee == 0 ? "Bepul" : Format.sum(totals.deliveryFee)
            )
            MBDivider().padding(.vertical, 8)
            MBTotalRow(label: "To'lanadi", value: Format.sum(totals.total), strong: true)
        }
    }
}
