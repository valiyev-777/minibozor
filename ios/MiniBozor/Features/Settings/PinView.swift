import SwiftUI

/// Screens 41–44 in one flow: current code, new code, confirmation, success.
struct PinView: View {
    let hasPin: Bool

    @Environment(Router.self) var router
    @State var model = PinModel()

    var body: some View {
        Group {
            if model.done {
                doneScreen
            } else {
                entryScreen
            }
        }
        .navigationBarBackButtonHidden()
        .task { model.start(hasPin: hasPin) }
    }

    private var entryScreen: some View {
        MBScreen(background: MB.color.surface) {
            VStack(spacing: 0) {
                MBTopBar("", onBack: { router.pop() })
                Spacer().frame(height: 20)
                Text(title).mbFont(MB.type.title1).foregroundStyle(MB.color.ink)
                Spacer().frame(height: 8)
                Text(subtitle)
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)
                Spacer().frame(height: 34)
                MBCodeField(
                    code: Binding(
                        get: { model.currentValue },
                        set: { value in Task { await model.input(value) } }
                    ),
                    length: PinModel.length,
                    masked: true,
                    isError: model.errorMessage != nil
                )
                if let error = model.errorMessage {
                    Spacer().frame(height: 14)
                    Text(error).mbFont(MB.type.caption).foregroundStyle(MB.color.danger)
                }
                Spacer()
                Text(L("kodni_hech_kimga_aytmang_mini_bozor"))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.disabled)
                    .multilineTextAlignment(.center)
                    .padding(.bottom, 30)
            }
            .padding(.horizontal, 26)
        }
    }

    private var doneScreen: some View {
        MBScreen(background: MB.color.surface) {
            VStack(spacing: 0) {
                Spacer().frame(height: 70)
                MBIcon("gear", size: 40, tint: MB.color.success, lineWidth: 1.6)
                    .frame(width: 96, height: 96)
                    .background(MB.color.successBg)
                    .clipShape(Circle())
                Spacer().frame(height: 22)
                Text(L("pin_ozgartirildi")).mbFont(MB.type.title1).foregroundStyle(MB.color.ink)
                Spacer().frame(height: 8)
                Text(L("endi_ilovaga_kirishda_yangi_kod_soraladi"))
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)
                Spacer()
            }
            .padding(.horizontal, 30)
        }
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(L("tayyor")) { router.pop() }
            }
        }
    }

    private var title: String {
        switch model.step {
        case 0: return L("joriy_pin_kod")
        case 1: return L("yangi_pin_kod")
        default: return L("kodni_tasdiqlang")
        }
    }

    private var subtitle: String {
        switch model.step {
        case 0: return L("xavfsizlik_uchun_avval_joriy_kodni_kiriting")
        case 1: return L("pin_4_xonali_kod_oylab_toping")
        default: return L("yangi_kodni_yana_bir_marta_kiriting")
        }
    }
}
