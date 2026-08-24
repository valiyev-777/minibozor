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
                Text("Kodni hech kimga aytmang. Mini Bozor xodimlari PIN so'ramaydi.")
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
                Text("PIN o'zgartirildi").mbFont(MB.type.title1).foregroundStyle(MB.color.ink)
                Spacer().frame(height: 8)
                Text("Endi ilovaga kirishda yangi kod so'raladi.")
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)
                Spacer()
            }
            .padding(.horizontal, 30)
        }
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton("Tayyor") { router.pop() }
            }
        }
    }

    private var title: String {
        switch model.step {
        case 0: return "Joriy PIN kod"
        case 1: return "Yangi PIN kod"
        default: return "Kodni tasdiqlang"
        }
    }

    private var subtitle: String {
        switch model.step {
        case 0: return "Xavfsizlik uchun avval joriy kodni kiriting"
        case 1: return "4 xonali kod o'ylab toping"
        default: return "Yangi kodni yana bir marta kiriting"
        }
    }
}
