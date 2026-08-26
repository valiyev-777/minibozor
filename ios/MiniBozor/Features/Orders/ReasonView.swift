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
                    isReturn ? L("qaytarish_arizasi") : L("buyurtmani_bekor_qilish"),
                    onBack: { router.pop() }
                )
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(isReturn
                             ? L("tovarni_nima_uchun_qaytarmoqchisiz")
                             : L("buyurtmani_nima_uchun_bekor_qilyapsiz"))
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
                                title: L("izoh"),
                                subtitle: needsComment ? "majburiy" : "ixtiyoriy"
                            )
                            Spacer().frame(height: 12)
                            MBTextField(
                                placeholder: L("qisqacha_yozib_qoldiring"),
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
                             ? L("ariza_korib_chiqilgach_sms_yuboramiz")
                             : L("tolangan_summa_1_3_ish_kunida_kartangizga"))
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
                    MBPrimaryButton(L("ariza_yuborish"), enabled: canSubmit, loading: model.submitting) {
                        Task { await model.requestReturn() }
                    }
                } else {
                    MBDangerButton(L("bekor_qilishni_tasdiqlash"), loading: model.submitting) {
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
