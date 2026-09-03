import SwiftUI
import Observation

@Observable
final class ReturnsModel {
    var items: [ReturnDTO] = []
    var loading = true
    var errorMessage: String?

    private let repo = OrderRepository()

    @MainActor
    func load() async {
        loading = true
        errorMessage = nil
        switch await repo.returns() {
        case .success(let rows):
            items = rows
        case .failure(let message):
            errorMessage = message
        }
        loading = false
    }
}

/// Every return the customer has asked for, newest first.
///
/// The profile's "Qaytarish" tile used to open the orders list, which is where
/// "Buyurtmalar" directly above it already went — two tiles, one screen, and no
/// way to see whether a request that had been sent was ever answered. The
/// request itself is made from an order; this is the other half of it, which is
/// what happened next.
struct ReturnsView: View {
    @Environment(Router.self) var router
    @State var model = ReturnsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("qaytarishlarim"), onBack: { router.pop() })

                if model.loading && model.items.isEmpty {
                    MBLoading()
                } else if let error = model.errorMessage, model.items.isEmpty {
                    MBErrorState(message: error) { Task { await model.load() } }
                } else if model.items.isEmpty {
                    MBEmptyState(
                        glyph: "ret",
                        title: L("hali_qaytarish_arizasi_yubormagansiz"),
                        message: L("yetkazilgan_buyurtmani_14_kun_ichida_qaytarish_mumkin")
                    )
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(model.items) { request in
                                MBCard {
                                    HStack {
                                        Text(request.orderCode)
                                            .mbFont(MB.type.bodyBold)
                                            .foregroundStyle(MB.color.ink)
                                        Spacer()
                                        MBStatusPill(
                                            statusLabel(request.status),
                                            background: statusBackground(request.status),
                                            contentColor: statusColor(request.status)
                                        )
                                    }
                                    Spacer().frame(height: 8)
                                    Text(request.reason)
                                        .mbFont(MB.type.bodySmall)
                                        .foregroundStyle(MB.color.inkSoft)
                                    if !request.comment.isEmpty {
                                        Spacer().frame(height: 4)
                                        Text(request.comment)
                                            .mbFont(MB.type.caption)
                                            .foregroundStyle(MB.color.textSecondary)
                                    }
                                    if let created = UzDate.parseDateTime(request.createdAt) {
                                        Spacer().frame(height: 8)
                                        Text(UzDate.dayTime(created))
                                            .mbFont(MB.type.caption)
                                            .foregroundStyle(MB.color.textQuaternary)
                                    }
                                }
                            }
                        }
                        .padding(12)
                    }
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "approved": return L("return_approved")
        case "rejected": return L("return_rejected")
        case "refunded": return L("return_refunded")
        default: return L("return_submitted")
        }
    }

    private func statusBackground(_ status: String) -> Color {
        switch status {
        case "approved", "refunded": return MB.color.successBg
        case "rejected": return MB.color.dangerBg
        default: return MB.color.warningBg
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "approved", "refunded": return MB.color.success
        case "rejected": return MB.color.danger
        default: return MB.color.warning
        }
    }
}
