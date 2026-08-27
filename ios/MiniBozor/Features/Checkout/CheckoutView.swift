import SwiftUI

/// Screen 19 — Buyurtma berish.
struct CheckoutView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("buyurtma_berish"), onBack: { router.pop() })

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
                        Text(L("jami")).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                        Text(Format.grouped(model.preview?.totals.total ?? 0))
                            .mbFont(MB.type.price)
                            .foregroundStyle(MB.color.ink)
                    }
                    MBPrimaryButton(L("davom_etish"), enabled: model.ready) {
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
                preview.address?.title ?? preview.pickupPoint?.name ?? L("manzilni_tanlang"),
                glyph: "pin",
                subtitle: preview.address?.line ?? preview.pickupPoint?.address
            ) {
                router.push(.addressForm)
            }
            .padding(.horizontal, 10)
            MBDivider(inset: 62)
            MBListRow(
                preview.slot?.label ?? L("yetkazish_vaqtini_tanlang"),
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
                    ? L("kuryerga_topshirishda") : preview.card?.brand
            ) {
                router.push(.paymentMethod)
            }
            .padding(.horizontal, 10)
        }
    }

    private func paymentTitle(_ preview: CheckoutPreviewDTO) -> String {
        if model.paymentMethod == "cash" { return L("naqd_pul") }
        if let card = preview.card { return "Karta ···· \(card.last4)" }
        return L("tolov_usulini_tanlang")
    }

    private func basketCard(_ preview: CheckoutPreviewDTO) -> some View {
        MBCard {
            SectionHeader(title: L("savat"), subtitle: "\(preview.items.count) tovar")
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
                    label: L("chegirma"),
                    value: "−\(Format.grouped(totals.discount))",
                    valueColor: MB.color.success
                )
            }
            MBTotalRow(
                label: L("yetkazish"),
                value: totals.deliveryFee == 0 ? L("bepul") : Format.sum(totals.deliveryFee),
                valueColor: totals.deliveryFee == 0 ? MB.color.success : MB.color.ink
            )
            MBDivider().padding(.vertical, 8)
            MBTotalRow(label: L("jami"), value: Format.sum(totals.total), strong: true)
        }
    }
}
