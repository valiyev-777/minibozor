import SwiftUI
import Observation

@Observable
final class OrderDetailModel {
    var loading = true
    var order: OrderDTO?
    var errorMessage: String?

    var reasons: [ReasonDTO] = []
    var selectedReasonId: Int?
    var comment = ""
    var submitting = false
    var finished = false

    private let repo = OrderRepository()
    private var orderId = 0

    @MainActor
    func load(id: Int) async {
        orderId = id
        loading = true
        errorMessage = nil
        switch await repo.order(id: id) {
        case .success(let value): order = value
        case .failure(let message): errorMessage = message
        }
        loading = false
    }

    @MainActor
    func loadReasons(isReturn: Bool) async {
        let outcome = isReturn ? await repo.returnReasons() : await repo.cancelReasons()
        if case .success(let values) = outcome {
            reasons = values
            selectedReasonId = selectedReasonId ?? values.first?.id
        }
    }

    @MainActor
    func cancel() async {
        guard !submitting else { return }
        submitting = true
        errorMessage = nil
        switch await repo.cancel(
            id: orderId,
            body: CancelRequest(reasonId: selectedReasonId, comment: comment)
        ) {
        case .success(let value):
            order = value
            finished = true
        case .failure(let message):
            errorMessage = message
        }
        submitting = false
    }

    @MainActor
    func requestReturn() async {
        guard !submitting else { return }
        submitting = true
        errorMessage = nil
        switch await repo.requestReturn(
            id: orderId,
            body: ReturnRequestBody(reasonId: selectedReasonId, comment: comment)
        ) {
        case .success: finished = true
        case .failure(let message): errorMessage = message
        }
        submitting = false
    }
}

/// Screens 25 (tracking) and 27 (full detail) — same data, different depth.
struct OrderDetailView: View {
    let orderId: Int
    let trackingOnly: Bool

    @Environment(Router.self) var router
    @State var model = OrderDetailModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(
                    trackingOnly ? L("yetkazish_holati") : L("buyurtma_tafsilotlari"),
                    subtitle: model.order?.code,
                    onBack: { router.pop() }
                )

                if model.loading && model.order == nil {
                    MBLoading()
                } else if let error = model.errorMessage, model.order == nil {
                    MBErrorState(message: error) { Task { await model.load(id: orderId) } }
                } else if let order = model.order {
                    detail(order)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load(id: orderId) }
    }

    private func detail(_ order: OrderDTO) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                MBCard {
                    HStack {
                        MBStatusPill(
                            order.statusLabel,
                            background: OrderStatusStyle.background(order.status),
                            contentColor: OrderStatusStyle.foreground(order.status)
                        )
                        Spacer()
                        Text(order.etaLabel).mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.icon)
                    }
                    Spacer().frame(height: 16)
                    ForEach(Array(order.events.enumerated()), id: \.element.id) { offset, event in
                        TimelineRow(event: event, isLast: offset == order.events.count - 1)
                    }
                }

                MBCard {
                    SectionHeader(title: L("tovarlar"), subtitle: "\(order.itemsCount) ta")
                    Spacer().frame(height: 12)
                    ForEach(Array(order.items.enumerated()), id: \.element.id) { offset, item in
                        MBLineItem(
                            title: item.title,
                            imageUrl: item.imageUrl,
                            meta: item.variantLabel,
                            price: item.unitPrice,
                            quantity: item.quantity
                        ) {
                            if order.status == "delivered", !item.reviewed, let productId = item.productId {
                                MBSecondaryButton(L("sharh")) {
                                    router.push(.writeReview(productId: productId, orderItemId: item.id))
                                }
                                .frame(width: 88)
                            }
                        }
                        if offset != order.items.count - 1 { Spacer().frame(height: 14) }
                    }
                }

                if !trackingOnly {
                    MBCard {
                        SectionHeader(title: L("ma_lumot"))
                        if let created = UzDate.parseDateTime(order.createdAt) {
                            MBKeyValueRow(key: L("buyurtma_sanasi"), value: UzDate.dayTime(created))
                        }
                        MBKeyValueRow(key: L("tolov"), value: order.paymentLabel)
                        MBKeyValueRow(
                            key: L("manzil"),
                            value: [order.addressLine, order.addressMeta]
                                .filter { !$0.isEmpty }
                                .joined(separator: ", ")
                        )
                        MBKeyValueRow(
                            key: L("qabul_qiluvchi"),
                            value: "\(order.recipientName), \(order.recipientPhone)"
                        )
                    }

                    MBCard {
                        MBTotalRow(label: L("tovarlar"), value: Format.sum(order.subtotal))
                        if order.discount > 0 {
                            MBTotalRow(
                                label: L("chegirma"),
                                value: "−\(Format.grouped(order.discount))",
                                valueColor: MB.color.success
                            )
                        }
                        MBTotalRow(
                            label: L("yetkazish"),
                            value: order.deliveryFee == 0 ? L("bepul") : Format.sum(order.deliveryFee)
                        )
                        MBDivider().padding(.vertical, 8)
                        MBTotalRow(label: L("jami"), value: Format.sum(order.total), strong: true)
                    }

                    if order.canCancel {
                        MBSecondaryButton(L("buyurtmani_bekor_qilish"), contentColor: MB.color.danger) {
                            router.push(.orderCancel(orderId: order.id))
                        }
                    }
                    if order.status == "delivered" {
                        MBSecondaryButton(L("qaytarish_arizasi")) {
                            router.push(.orderReturn(orderId: order.id))
                        }
                    }
                }
            }
            .padding(12)
        }
    }
}

private struct TimelineRow: View {
    let event: OrderEventDTO
    let isLast: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle()
                    .fill(event.done ? MB.color.accent : MB.color.divider)
                    .frame(width: 12, height: 12)
                if !isLast {
                    Rectangle()
                        .fill(event.done ? MB.color.accent.opacity(0.35) : MB.color.border)
                        .frame(width: 1.5, height: 34)
                }
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(event.title)
                    .mbFont(MB.type.bodyBold)
                    .foregroundStyle(event.done ? MB.color.ink : MB.color.disabled)
                Text(stamp).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
            }
            Spacer(minLength: 0)
        }
        .padding(.bottom, isLast ? 0 : 8)
    }

    private var stamp: String {
        if let happenedAt = event.happenedAt, let date = UzDate.parseDateTime(happenedAt) {
            return UzDate.dayTime(date)
        }
        return event.note.isEmpty ? L("kutilmoqda") : event.note
    }
}
