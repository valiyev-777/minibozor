import SwiftUI

/// Screens 28 (cancel) and 29 (return). Both are "pick a reason, add a note,
/// confirm" — one view, two configurations.
struct ReasonView: View {
    let orderId: Int
    let isReturn: Bool

    @Environment(Router.self) var router
    @State var model = OrderDetailModel()

    private var selectedReason: ReasonDTO? {
        model.reasons.first { $0.id == model.selectedReasonId }
    }

    private var needsComment: Bool { selectedReason?.requiresComment == true }

    private var canSubmit: Bool {
        model.selectedReasonId != nil && (!needsComment || !model.comment.isEmpty)
    }

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(
                    isReturn ? "Qaytarish arizasi" : "Buyurtmani bekor qilish",
                    onBack: { router.pop() }
                )
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(isReturn
                             ? "Tovarni nima uchun qaytarmoqchisiz?"
                             : "Buyurtmani nima uchun bekor qilyapsiz?")
                            .mbFont(MB.type.title3)
                            .foregroundStyle(MB.color.ink)
                            .padding(.horizontal, 6)

                        MBCard(padding: 6) {
                            ForEach(Array(model.reasons.enumerated()), id: \.element.id) { offset, reason in
                                MBRadioRow(
                                    reason.label,
                                    selected: reason.id == model.selectedReasonId
                                ) {
                                    model.selectedReasonId = reason.id
                                }
                                .padding(.horizontal, 10)
                                if offset != model.reasons.count - 1 { MBDivider() }
                            }
                        }

                        MBCard {
                            SectionHeader(
                                title: "Izoh",
                                subtitle: needsComment ? "majburiy" : "ixtiyoriy"
                            )
                            Spacer().frame(height: 12)
                            MBTextField(
                                placeholder: "Qisqacha yozib qoldiring…",
                                text: Binding(get: { model.comment }, set: { model.comment = $0 }),
                                multiline: true,
                                minHeight: 100
                            )
                        }

                        if let error = model.errorMessage {
                            Text(error).mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.danger)
                                .padding(.horizontal, 6)
                        }

                        Text(isReturn
                             ? "Ariza ko'rib chiqilgach SMS yuboramiz. Tovarni qadog'i bilan saqlang."
                             : "To'langan summa 1–3 ish kunida kartangizga qaytariladi.")
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.textQuaternary)
                            .padding(.horizontal, 6)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                if isReturn {
                    MBPrimaryButton("Ariza yuborish", enabled: canSubmit, loading: model.submitting) {
                        Task { await model.requestReturn() }
                    }
                } else {
                    MBDangerButton("Bekor qilishni tasdiqlash", loading: model.submitting) {
                        Task { await model.cancel() }
                    }
                }
            }
        }
        .task {
            await model.load(id: orderId)
            await model.loadReasons(isReturn: isReturn)
        }
        .onChange(of: model.finished) { _, finished in
            if finished { router.pop() }
        }
    }
}
