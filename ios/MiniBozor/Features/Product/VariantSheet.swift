import Observation
import SwiftUI

/// Backs the picker a tile opens instead of adding straight to the cart.
///
/// The tile only knows the card fields, so the variants are fetched when the
/// sheet opens. The summary at the top is drawn from what the tile already
/// has, which is why the sheet can be on screen before this finishes.
@Observable
final class VariantSheetModel {
    var loading = true
    var product: ProductDTO?
    var sizeId: Int?
    var colorId: Int?
    var quantity = 1
    /// Set once the line is in the cart; the bottom bar becomes a stepper.
    var cartItemId: Int?
    var busy = false
    var errorMessage: String?

    private let catalog = CatalogRepository()

    var sizes: [VariantDTO] { product?.sizes ?? [] }
    var colors: [VariantDTO] { product?.colors ?? [] }
    var selectedSize: VariantDTO? { sizes.first { $0.id == sizeId } }
    var selectedColor: VariantDTO? { colors.first { $0.id == colorId } }
    /// How many of the thing actually chosen are left: the colour's share of
    /// the shelf, or the whole shelf when the colours are not counted apart.
    var shelfLeft: Int { selectedColor?.stockLeft ?? product?.stockLeft ?? 1 }

    /// A size has to be chosen when the product has any in stock.
    var ready: Bool { product != nil && (!sizes.contains { $0.inStock } || sizeId != nil) }

    @MainActor
    func load(id: Int) async {
        loading = true
        errorMessage = nil
        switch await catalog.product(id) {
        case .success(let value):
            product = value
            // Preselect a colour — there is always one right answer — but never
            // a size, which is the customer's call.
            colorId = value.colors.first { $0.inStock }?.id
        case .failure(let message):
            errorMessage = message
        }
        loading = false
    }

    @MainActor
    func addToCart(using cart: CartRepository) async {
        guard let product, !busy else { return }
        busy = true
        errorMessage = nil
        let outcome = await cart.add(
            productId: product.id,
            variantId: sizeId,
            colorVariantId: colorId,
            quantity: quantity
        )
        busy = false
        switch outcome {
        case .success(let value):
            // Match on the line just added, so the stepper drives the right row
            // rather than the product's first one.
            let line = value.items.last { $0.productId == product.id }
            cartItemId = line?.id
            quantity = line?.quantity ?? quantity
        case .failure(let message):
            errorMessage = message
        }
    }

    /// Stepper on the added state; zero removes the line and returns to choosing.
    @MainActor
    func setQuantity(_ value: Int, using cart: CartRepository) async {
        guard let itemId = cartItemId, !busy, (0...99).contains(value) else { return }
        busy = true
        quantity = max(value, 1)
        let outcome = value == 0
            ? await cart.remove(itemId: itemId)
            : await cart.setQuantity(itemId: itemId, quantity: value)
        busy = false
        if case .failure(let message) = outcome {
            errorMessage = message
        } else if value == 0 {
            cartItemId = nil
            quantity = 1
        }
    }
}

/// The picker a tile opens when a product comes in more than one size or
/// colour, instead of guessing one and adding it.
struct VariantSheet: View {
    let card: ProductCardDTO
    let onDismiss: () -> Void
    let onOpenCart: () -> Void

    @Environment(CartRepository.self) private var cart
    @State private var model = VariantSheetModel()

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(L("xususiyatlarni_tanlang"))
                    .mbFont(MB.type.title2)
                    .foregroundStyle(MB.color.ink)
                Spacer()
                Button(action: onDismiss) {
                    MBIcon("close", size: 14, tint: MB.color.inkSoft)
                        .frame(width: 32, height: 32)
                        .background(MB.color.fill)
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 20)
            .padding(.top, 6)

            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Spacer().frame(height: 12)
                    summary

                    if model.loading {
                        MBLoading().frame(height: 140)
                    } else {
                        if !model.colors.isEmpty {
                            Spacer().frame(height: 20)
                            label(L("rang"), model.selectedColor?.label ?? "")
                            Spacer().frame(height: 10)
                            colorRow
                        }
                        if !model.sizes.isEmpty {
                            Spacer().frame(height: 20)
                            label(L("olcham"), model.selectedSize?.label ?? "")
                            Spacer().frame(height: 10)
                            sizeRow
                        }
                    }

                    if let error = model.errorMessage {
                        Spacer().frame(height: 12)
                        Text(error).mbFont(MB.type.caption).foregroundStyle(MB.color.danger)
                    }
                    Spacer().frame(height: 16)
                }
                .padding(.horizontal, 20)
            }
            .frame(maxHeight: 460)

            bottomBar
        }
        .background(MB.color.surface)
        .task { await model.load(id: card.id) }
    }

    /// Drawn from the tile's data, so it is on screen before the request lands.
    private var summary: some View {
        HStack(alignment: .top, spacing: 12) {
            MBProductImage(url: card.imageUrl, cornerRadius: MB.metric.radiusL)
                .frame(width: 84, height: 84)
            VStack(alignment: .leading, spacing: 6) {
                if let badge = card.badge, !badge.isEmpty {
                    MBStatusPill(badge, background: MB.color.successBg,
                                 contentColor: MB.color.success)
                }
                Text(card.title)
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.ink)
                    .lineLimit(2)
                MBPriceRow(
                    price: card.price,
                    oldPrice: card.oldPrice,
                    discountPercent: card.discountPercent,
                    style: MB.type.title3,
                    reservesFootnote: false
                )
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .overlay {
            RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous)
                .stroke(MB.color.border, lineWidth: 1)
        }
    }

    private func label(_ name: String, _ value: String) -> some View {
        HStack(spacing: 6) {
            Text("\(name):").mbFont(MB.type.bodySmall).foregroundStyle(MB.color.textSecondary)
            Text(value).mbFont(MB.type.bodySmall).foregroundStyle(MB.color.ink).bold()
        }
    }

    /// The colours, as photographs of the thing in that colour where the shop
    /// supplied one — a hex square asks the customer to imagine what `#0E0F12`
    /// looks like on a shoe, and the sheet is being asked to decide.
    private var colorRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                ForEach(model.colors) { variant in
                    let selected = variant.id == model.colorId
                    Button { model.colorId = variant.id } label: {
                        Group {
                            if let photo = variant.imageUrl {
                                MBProductImage(url: photo, cornerRadius: MB.metric.radiusS)
                            } else {
                                RoundedRectangle(cornerRadius: MB.metric.radiusS,
                                                 style: .continuous)
                                    .fill(Color(hexString: variant.value,
                                                fallback: MB.color.fill))
                            }
                        }
                        .padding(selected ? 4 : 3)
                        .frame(width: 56, height: 56)
                        .overlay {
                            RoundedRectangle(cornerRadius: MB.metric.radiusL,
                                             style: .continuous)
                                .stroke(
                                    selected ? MB.color.ink : MB.color.border,
                                    lineWidth: selected ? 2 : 1
                                )
                        }
                        .opacity(variant.inStock ? 1 : 0.4)
                    }
                    .buttonStyle(MBCardPressStyle(pressedScale: 0.95))
                    .disabled(!variant.inStock)
                }
            }
            .padding(.vertical, 1)
        }
    }

    private var sizeRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(model.sizes) { variant in
                    MBSizeChip(
                        variant.label,
                        selected: variant.id == model.sizeId,
                        enabled: variant.inStock
                    ) {
                        model.sizeId = variant.id
                    }
                }
            }
        }
    }

    /// "Savatga" before the line exists, a stepper and a way through once it does.
    private var bottomBar: some View {
        VStack(spacing: 0) {
            if model.cartItemId == nil {
                MBPrimaryButton(
                    L("savatga"),
                    enabled: model.ready && !model.busy,
                    loading: model.busy
                ) {
                    Task { await model.addToCart(using: cart) }
                }
            } else {
                HStack(spacing: 12) {
                    MBQuantityStepper(
                        quantity: model.quantity,
                        minimum: 0,
                        // Where the shelf ends, as everywhere else the count
                        // can be raised — and it is the chosen colour's shelf,
                        // since that is what this sheet is adding.
                        maximum: Swift.max(model.shelfLeft, 1),
                        size: 48
                    ) { value in
                        Task { await model.setQuantity(value, using: cart) }
                    }
                    MBPrimaryButton(L("otish"), leadingGlyph: "cart", action: onOpenCart)
                }
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 14)
        .background(MB.color.surfaceAlt)
    }
}
