import SwiftUI

/// Screen 19 — Buyurtma berish.
struct CheckoutView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Buyurtma berish", onBack: { router.pop() })

                if let preview = model.preview {
                    ScrollView {
                        VStack(spacing: 12) {
                            stepsCard(preview)
                            basketCard(preview)
                            totalsCard(preview.totals)
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
                HStack(spacing: 14) {
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Jami").mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                        Text(Format.grouped(model.preview?.totals.total ?? 0))
                            .mbFont(MB.type.price)
                            .foregroundStyle(MB.color.ink)
                    }
                    MBPrimaryButton("Davom etish", enabled: model.ready) {
                        router.push(.confirm)
                    }
                }
            }
        }
        .task {
            model.reset()
            await model.load()
        }
    }

    private func stepsCard(_ preview: CheckoutPreviewDTO) -> some View {
        MBCard(padding: 6) {
            MBListRow(
                preview.address?.title ?? preview.pickupPoint?.name ?? "Manzilni tanlang",
                glyph: "pin",
                subtitle: preview.address?.line ?? preview.pickupPoint?.address
            ) {
                router.push(.addressForm)
            }
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                preview.slot?.label ?? "Yetkazish vaqtini tanlang",
                glyph: "clock",
                subtitle: preview.slot?.note
            ) {
                router.push(.deliveryTime)
            }
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                paymentTitle(preview),
                glyph: "card",
                subtitle: model.paymentMethod == "cash"
                    ? "Kuryerga topshirishda" : preview.card?.brand
            ) {
                router.push(.paymentMethod)
            }
            .padding(.horizontal, 10)
        }
    }

    private func paymentTitle(_ preview: CheckoutPreviewDTO) -> String {
        if model.paymentMethod == "cash" { return "Naqd pul" }
        if let card = preview.card { return "Karta ···· \(card.last4)" }
        return "To'lov usulini tanlang"
    }

    private func basketCard(_ preview: CheckoutPreviewDTO) -> some View {
        MBCard {
            SectionHeader(title: "Savat", subtitle: "\(preview.items.count) tovar")
            Spacer().frame(height: 12)
            ForEach(Array(preview.items.enumerated()), id: \.element.id) { offset, item in
                MBLineItem(
                    title: item.title,
                    imageUrl: item.imageUrl,
                    meta: item.variantLabel,
                    price: item.unitPrice,
                    quantity: item.quantity
                )
                if offset != preview.items.count - 1 { Spacer().frame(height: 14) }
            }
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
                value: totals.deliveryFee == 0 ? "Bepul" : Format.sum(totals.deliveryFee),
                valueColor: totals.deliveryFee == 0 ? MB.color.success : MB.color.ink
            )
            MBDivider().padding(.vertical, 8)
            MBTotalRow(label: "Jami", value: Format.sum(totals.total), strong: true)
        }
    }
}
