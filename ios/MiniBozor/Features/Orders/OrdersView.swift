import SwiftUI
import Observation

@Observable
final class OrdersModel {
    var loading = true
    var activeTab = true
    var orders: [OrderSummaryDTO] = []
    var errorMessage: String?

    private let repo = OrderRepository()

    @MainActor
    func load() async {
        loading = true
        errorMessage = nil
        switch await repo.orders(active: activeTab) {
        case .success(let page): orders = page.items
        case .failure(let message): errorMessage = message
        }
        loading = false
    }

    @MainActor
    func select(active: Bool) async {
        activeTab = active
        await load()
    }
}

/// Screen 26 — Buyurtmalarim.
struct OrdersView: View {
    @Environment(Router.self) var router
    @State var model = OrdersModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("buyurtmalarim"), onBack: { router.pop() })
                segments
                content
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }

    private var segments: some View {
        HStack(spacing: 8) {
            segment(L("jarayonda"), active: model.activeTab) {
                Task { await model.select(active: true) }
            }
            segment(L("tugagan"), active: !model.activeTab) {
                Task { await model.select(active: false) }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(MB.color.surface)
    }

    private func segment(_ title: String, active: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .mbFont(MB.type.label)
                .foregroundStyle(active ? .white : MB.color.textSecondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(active ? MB.color.ink : MB.color.fill)
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private var content: some View {
        if model.loading {
            MBLoading()
        } else if let error = model.errorMessage {
            MBErrorState(message: error) { Task { await model.load() } }
        } else if model.orders.isEmpty {
            MBEmptyState(
                glyph: "box",
                title: model.activeTab ? L("faol_buyurtma_yoq") : L("tugagan_buyurtma_yoq"),
                message: L("buyurtma_bergach_holati_shu_yerda_korinadi")
            )
        } else {
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(model.orders) { order in
                        orderCard(order)
                    }
                }
                .padding(12)
            }
        }
    }

    private func orderCard(_ order: OrderSummaryDTO) -> some View {
        MBCard {
            HStack {
                MBStatusPill(
                    order.statusLabel,
                    background: OrderStatusStyle.background(order.status),
                    contentColor: OrderStatusStyle.foreground(order.status)
                )
                Spacer()
                Text(order.code).mbFont(MB.type.caption).foregroundStyle(MB.color.icon)
            }

            Spacer().frame(height: 14)
            HStack(spacing: 8) {
                ForEach(order.previewImages.prefix(2), id: \.self) { image in
                    MBProductImage(url: image, cornerRadius: MB.metric.radiusL)
                        .frame(width: 56, height: 56)
                }
                let extra = order.itemsCount - min(2, order.previewImages.count)
                if extra > 0 {
                    Text("+\(extra)")
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.textSecondary)
                        .frame(width: 56, height: 56)
                        .background(MB.color.fill)
                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusL, style: .continuous))
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 1) {
                    Text(L("jami")).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                    Text(Format.sum(order.total)).mbFont(MB.type.priceSmall)
                        .foregroundStyle(MB.color.ink)
                }
            }

            Spacer().frame(height: 12)
            MBDivider()
            Spacer().frame(height: 12)
            HStack {
                Text(order.etaLabel).mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.textSecondary)
                Spacer()
                if order.canTrack {
                    MBSecondaryButton(L("kuzatish")) {
                        router.push(.tracking(orderId: order.id))
                    }
                    .frame(width: 120)
                }
            }
        }
        .contentShape(Rectangle())
        .onTapGesture { router.push(.orderDetail(orderId: order.id)) }
    }
}
