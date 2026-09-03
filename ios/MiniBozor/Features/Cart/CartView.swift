import SwiftUI

/// Screens 17 (savat) and 18 (bo'sh savat).
struct CartView: View {
    let onStartShopping: () -> Void

    @Environment(Router.self) var router
    @Environment(CartRepository.self) var cart

    @State var promoCode = ""
    @State var promoError: String?
    @State var loading = true

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                header
                content
            }
        }
        .task {
            _ = await cart.refresh()
            loading = false
        }
    }

    private var header: some View {
        HStack {
            Text(L("savat")).mbFont(MB.type.title1).foregroundStyle(MB.color.ink)
            Spacer()
            if let items = cart.cart?.items, !items.isEmpty {
                Text(LPlural("n_products", count: items.count, "\(items.count)"))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.icon)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(MB.color.surface)
    }

    @ViewBuilder
    private var content: some View {
        if loading && cart.cart == nil {
            MBLoading()
        } else if let payload = cart.cart, !payload.items.isEmpty {
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(payload.items) { item in
                        itemCard(item)
                    }
                    promoCard
                    totalsCard(payload.totals)
                    Spacer().frame(height: MB.metric.tabBarHeight + 26)
                }
                .padding(12)
            }
        } else {
            MBEmptyState(
                glyph: "cart",
                title: L("savat_bosh"),
                message: L("yoqqan_tovarlarni_savatga_qoshing_keyin_bir"),
                actionLabel: L("xaridni_boshlash"),
                onAction: onStartShopping
            )
        }
    }

    private func itemCard(_ item: CartItemDTO) -> some View {
        MBCard(padding: 14) {
            HStack(alignment: .top, spacing: 12) {
                Button {
                    Task { _ = await cart.setSelected(itemId: item.id, selected: !item.selected) }
                } label: {
                    MBCheckbox(checked: item.selected).padding(.top, 4)
                }
                .buttonStyle(.plain)

                MBLineItem(
                    title: item.title,
                    imageUrl: item.imageUrl,
                    meta: item.variantLabel,
                    price: item.unitPrice,
                    onTap: { router.push(.product(id: item.productId)) }
                )
            }

            Spacer().frame(height: 12)
            HStack(spacing: 14) {
                // Where the shelf ends, not an arbitrary 99: plus stops there
                // rather than sending a number the server has to cut down.
                MBQuantityStepper(
                    quantity: item.quantity,
                    maximum: Swift.max(item.stockLeft, 1)
                ) { quantity in
                    Task { _ = await cart.setQuantity(itemId: item.id, quantity: quantity) }
                }
                Spacer()
                Text(Format.sum(item.lineTotal))
                    .mbFont(MB.type.priceSmall)
                    .foregroundStyle(MB.color.ink)
                Button {
                    Task { _ = await cart.remove(itemId: item.id) }
                } label: {
                    MBIcon("ret", size: 18, tint: MB.color.icon)
                }
                .buttonStyle(.plain)
            }

            if !item.inStock {
                Spacer().frame(height: 8)
                Text(L("hozircha_mavjud_emas"))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.danger)
            }
        }
    }

    private var promoCard: some View {
        MBCard {
            HStack(spacing: 10) {
                MBTextField(
                    placeholder: "Promokod",
                    text: $promoCode,
                    leadingGlyph: "ticket",
                    error: promoError
                )
                Button {
                    Task {
                        let outcome = await cart.applyPromo(promoCode.trimmingCharacters(in: .whitespaces))
                        promoError = outcome.errorMessage
                    }
                } label: {
                    Text(L("qollash"))
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.onInverse)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 14)
                        .background(MB.color.inverse)
                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func totalsCard(_ totals: CartTotalsDTO) -> some View {
        MBCard {
            MBTotalRow(
                label: L("tovarlar_soni", totals.itemsCount),
                value: Format.sum(totals.subtotal)
            )
            if totals.discount > 0 {
                MBTotalRow(
                    label: L("chegirma") + (totals.promoCode.map { " · \($0)" } ?? ""),
                    value: "−\(Format.grouped(totals.discount))",
                    valueColor: MB.color.success
                )
            }
            MBTotalRow(
                label: L("yetkazish"),
                value: totals.deliveryFee == 0 ? L("bepul") : Format.sum(totals.deliveryFee),
                valueColor: totals.deliveryFee == 0 ? MB.color.success : MB.color.ink
            )
            if totals.deliveryFee > 0 {
                let left = max(0, totals.freeDeliveryThreshold - totals.subtotal)
                Text(L("bepul_yetkazishgacha", Format.sum(left)))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.textQuaternary)
            }
            MBDivider().padding(.vertical, 8)
            MBTotalRow(label: L("jami"), value: Format.sum(totals.total), strong: true)
            Spacer().frame(height: 12)
            MBPrimaryButton(L("buyurtma_berish"), enabled: totals.itemsCount > 0) {
                router.push(.checkout)
            }
        }
    }
}
