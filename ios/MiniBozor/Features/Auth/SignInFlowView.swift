import SwiftUI

/// Holds the sign-in stack so login and the code screen share one `AuthModel`.
struct SignInFlowView: View {
    @Environment(AppSession.self) var session
    @State var model = AuthModel()
    @State var path: [String] = []

    var body: some View {
        NavigationStack(path: $path) {
            LoginView(model: model, onCodeSent: { path.append("otp") })
                .navigationDestination(for: String.self) { _ in
                    OtpView(model: model, onBack: { path.removeLast() })
                }
        }
        .onChange(of: model.signedIn) { _, signedIn in
            if signedIn { session.didSignIn() }
        }
    }
}

/// Screen 05 — Kirish. The field only ever holds the nine national digits,
/// which is also what the model validates.
struct LoginView: View {
    @Bindable var model: AuthModel
    let onCodeSent: () -> Void

    @State var showTerms = false

    var body: some View {
        MBScreen(background: MB.color.surface) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    Spacer().frame(height: 28)
                    BrandMark(size: 46)
                    Spacer().frame(height: 20)
                    Text(L("app_name")).mbFont(MB.type.display).foregroundStyle(MB.color.ink)
                    Spacer().frame(height: 8)
                    Text(L("telefon_raqamingizni_kiriting_sms_kod"))
                        .mbFont(MB.type.bodySmall)
                        .foregroundStyle(MB.color.textTertiary)

                    Spacer().frame(height: 28)
                    phoneField

                    Spacer().frame(height: 18)
                    MBPrimaryButton(
                        L("davom_etish"),
                        enabled: model.phoneValid,
                        loading: model.sending
                    ) {
                        Task { await model.sendCode() }
                    }

                    Spacer().frame(height: 14)
                    Text(L("menda_referal_kod_bor"))
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.accent)
                        .frame(maxWidth: .infinity)

                    Spacer().frame(height: 28)
                    separator
                    Spacer().frame(height: 18)
                    socialRow

                    Spacer().frame(height: 40)
                    terms
                }
                .padding(.horizontal, 26)
                .padding(.bottom, 24)
            }
            .scrollDismissesKeyboard(.interactively)
        }
        .onChange(of: model.codeSent) { _, sent in
            if sent { onCodeSent() }
        }
        .sheet(isPresented: $showTerms) {
            NavigationStack { LegalDocView(slug: "ommaviy-oferta") }
        }
    }

    private var phoneField: some View {
        HStack(spacing: 12) {
            Text("+998").mbFont(MB.type.title3).foregroundStyle(MB.color.ink)
            TextField("-- --- -- --", text: Binding(
                get: { formatted(model.phoneDigits) },
                set: { model.setPhone($0) }
            ))
            .mbFont(MB.type.title3)
            .foregroundStyle(MB.color.ink)
            .keyboardType(.numberPad)
            .textContentType(.telephoneNumber)
            .tint(MB.color.accent)
        }
        .padding(.horizontal, 16)
        .frame(height: 56)
        .background(MB.color.fill)
        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
        .overlay(alignment: .bottomLeading) {
            if let error = model.errorMessage {
                Text(error)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(MB.color.danger)
                    .offset(y: 26)
            }
        }
    }

    /// `901234567` → `90 123 45 67`.
    private func formatted(_ digits: String) -> String {
        var out = ""
        for (offset, ch) in digits.enumerated() {
            if offset == 2 || offset == 5 || offset == 7 { out.append(" ") }
            out.append(ch)
        }
        return out
    }

    private var separator: some View {
        HStack(spacing: 12) {
            Rectangle().fill(MB.color.border).frame(height: 1)
            Text("yoki tezkor kirish")
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textQuaternary)
                .fixedSize()
            Rectangle().fill(MB.color.border).frame(height: 1)
        }
    }

    private var socialRow: some View {
        HStack(spacing: 10) {
            ForEach([L("apple"), L("google"), L("oneid")], id: \.self) { provider in
                Text(provider)
                    .mbFont(MB.type.label)
                    .foregroundStyle(MB.color.inkSoft)
                    .frame(maxWidth: .infinity)
                    .frame(height: 46)
                    .background(MB.color.fill)
                    .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
            }
        }
    }

    private var terms: some View {
        HStack(spacing: 0) {
            Text(L("kirish_orqali")).mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textQuaternary)
            Button(L("ommaviy_oferta")) { showTerms = true }
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.accent)
            Text(L("shartlariga_rozilik_bildirasiz")).mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textQuaternary)
        }
        .frame(maxWidth: .infinity)
        .multilineTextAlignment(.center)
    }
}

/// Screen 06 — SMS kod. Auto-submits on the sixth digit, which is what the
/// design's "Kod avtomatik o'qiladi" note promises.
struct OtpView: View {
    @Bindable var model: AuthModel
    let onBack: () -> Void

    var body: some View {
        MBScreen(background: MB.color.surface) {
            VStack(spacing: 0) {
                MBTopBar("", onBack: onBack)

                Spacer().frame(height: 12)
                Text(L("tasdiqlash_kodi"))
                    .mbFont(MB.type.display)
                    .foregroundStyle(MB.color.ink)
                Spacer().frame(height: 10)
                Text(L("otp_yuborildi", Format.phone(model.phoneDigits), AuthModel.codeLength))
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.textTertiary)
                    .multilineTextAlignment(.center)

                Spacer().frame(height: 30)
                MBCodeField(
                    code: Binding(get: { model.code }, set: { model.setCode($0) }),
                    length: AuthModel.codeLength,
                    isError: model.errorMessage != nil
                )

                if let error = model.errorMessage {
                    Spacer().frame(height: 12)
                    Text(error).mbFont(MB.type.caption).foregroundStyle(MB.color.danger)
                }
                if let devCode = model.devCode {
                    Spacer().frame(height: 12)
                    Text(L("dev_rejim_kod", devCode))
                        .mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.textQuaternary)
                }

                Spacer().frame(height: 20)
                resend

                Spacer().frame(height: 24)
                MBPrimaryButton(
                    L("tasdiqlash"),
                    enabled: model.codeValid,
                    loading: model.verifying
                ) {
                    Task { await model.verify() }
                }

                Spacer()
                footnotes
            }
            .padding(.horizontal, 26)
            .padding(.bottom, 28)
        }
        .navigationBarBackButtonHidden()
    }

    private var resend: some View {
        Group {
            if model.canResend {
                Button(L("kodni_qayta_yuborish")) {
                    Task { await model.sendCode() }
                }
                .mbFont(MB.type.label)
                .foregroundStyle(MB.color.accent)
            } else {
                HStack(spacing: 0) {
                    Text(L("kodni_qayta_yuborish_2"))
                        .mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.textQuaternary)
                    Text(clock(model.secondsLeft))
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.ink)
                }
            }
        }
    }

    private var footnotes: some View {
        VStack(spacing: 6) {
            Text(L("kod_avtomatik_oqiladi_sms_kelishi_bilan"))
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.textQuaternary)
            Text(L("kod_kelmadimi_1150_raqamiga_qongiroq_qiling"))
                .mbFont(MB.type.caption)
                .foregroundStyle(MB.color.disabled)
        }
        .multilineTextAlignment(.center)
    }

    private func clock(_ seconds: Int) -> String {
        String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }
}
