import SwiftUI
import Observation

/// Screen 31 — Shaxsiy ma'lumotlar.
struct PersonalView: View {
    @Environment(Router.self) var router
    @State var model = ProfileModel()

    @State var fullName = ""
    @State var email = ""
    @State var birthDate = ""
    @State var gender = ""
    @State var loaded = false

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("shaxsiy_ma_lumotlar"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard {
                            MBTextField(
                                placeholder: L("aziz_toshmatov_2"),
                                text: $fullName,
                                label: L("ism_va_familiya")
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "",
                                text: .constant(Format.phone(model.overview?.user.phone ?? "")),
                                label: L("telefon"),
                                disabled: true,
                                trailingText: L("ozgartirib_bolmaydi")
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "siz@example.uz",
                                text: $email,
                                label: L("email"),
                                keyboard: .emailAddress
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "1994-05-12",
                                text: $birthDate,
                                label: L("tugilgan_sana"),
                                keyboard: .numbersAndPunctuation
                            )
                        }

                        MBCard {
                            SectionHeader(title: L("jins"))
                            Spacer().frame(height: 12)
                            FlowLayout(spacing: 8) {
                                ForEach(["erkak", "ayol"], id: \.self) { option in
                                    MBChip(option.capitalized, selected: gender == option) {
                                        gender = gender == option ? "" : option
                                    }
                                }
                            }
                        }

                        if let error = model.errorMessage {
                            Text(error).mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.danger)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 6)
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(L("saqlash"), enabled: !fullName.isEmpty, loading: model.saving) {
                    Task {
                        await model.save(
                            fullName: fullName,
                            email: email,
                            birthDate: birthDate.isEmpty ? nil : birthDate,
                            gender: gender.isEmpty ? nil : gender
                        )
                    }
                }
            }
        }
        .task {
            await model.load()
            if !loaded, let user = model.overview?.user {
                fullName = user.fullName
                email = user.email ?? ""
                birthDate = user.birthDate ?? ""
                gender = user.gender ?? ""
                loaded = true
            }
        }
        .onChange(of: model.saved) { _, saved in
            if saved { router.pop() }
        }
    }
}

@Observable
final class CardsModel {
    var cards: [CardDTO] = []
    private let repo = OrderRepository()

    @MainActor
    func load() async {
        cards = (await repo.cards()).value ?? []
    }

    @MainActor
    func makeDefault(_ id: Int) async {
        _ = await repo.makeCardDefault(id: id)
        await load()
    }

    @MainActor
    func delete(_ id: Int) async {
        _ = await repo.deleteCard(id: id)
        await load()
    }
}

/// Screen 32 — To'lov kartalari.
struct CardsView: View {
    @Environment(Router.self) var router
    @State var model = CardsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("tolov_kartalari"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(model.cards) { card in
                            cardTile(card)
                        }
                        MBCard(padding: 6) {
                            MBListRow(
                                L("yangi_karta_qoshish"),
                                glyph: "card",
                                subtitle: L("humo_uzcard_visa"),
                                tint: MB.color.accent
                            ) {
                                router.push(.addCard)
                            }
                            .padding(.horizontal, 10)
                        }
                        if model.cards.isEmpty {
                            Text(L("karta_qoshsangiz_buyurtmani_bir_bosishda"))
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.textQuaternary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 6)
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        // Re-reads on every return, so a card added on the next screen shows up.
        .onAppear { Task { await model.load() } }
    }

    private func cardTile(_ card: CardDTO) -> some View {
        MBCard {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text(card.brand).mbFont(MB.type.label).foregroundStyle(.white)
                    Spacer()
                    if card.isDefault {
                        MBStatusPill(L("asosiy"), background: .white.opacity(0.2), contentColor: .white)
                    }
                }
                Spacer()
                Text("···· ···· ···· \(card.last4)")
                    .mbFont(MB.type.title3)
                    .foregroundStyle(.white)
                Spacer().frame(height: 6)
                HStack {
                    Text(card.holder).mbFont(MB.type.caption)
                        .foregroundStyle(.white.opacity(0.75))
                    Spacer()
                    Text(card.expiry).mbFont(MB.type.caption)
                        .foregroundStyle(.white.opacity(0.75))
                }
            }
            .padding(18)
            .frame(height: 150)
            .frame(maxWidth: .infinity)
            .background(
                LinearGradient(
                    colors: [MB.color.cardFrom, card.isExpired ? MB.color.disabled : MB.color.accent],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous))

            Spacer().frame(height: 10)
            HStack {
                if card.isExpired {
                    Text(L("muddati_otgan")).mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.danger)
                } else if !card.isDefault {
                    Button(L("asosiy_qilish")) { Task { await model.makeDefault(card.id) } }
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.accent)
                }
                Spacer()
                Button(L("ochirish")) { Task { await model.delete(card.id) } }
                    .mbFont(MB.type.label)
                    .foregroundStyle(MB.color.danger)
            }
        }
    }
}

/// Screen 32 — "Yangi karta qo'shish".
///
/// A live preview of the card above the form, the same gradient tile the saved
/// cards use. The number stays on the device: only the brand, the last four
/// digits and the expiry are sent — see `AddCardModel`.
struct AddCardView: View {
    @Environment(Router.self) var router
    @State var model = AddCardModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("karta_qoshish"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        CardPreview(model: model)
                        formCard
                        defaultCard

                        if let error = model.errorMessage {
                            Text(error)
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.danger)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 6)
                        }

                        HStack(alignment: .top, spacing: 8) {
                            MBIcon("gear", size: 16, tint: MB.color.icon)
                            Text(L("karta_raqami_qurilmadan_chiqmaydi_serverda"))
                                .mbFont(MB.type.caption)
                                .foregroundStyle(MB.color.textQuaternary)
                        }
                        .padding(.horizontal, 6)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(
                    L("kartani_saqlash"),
                    enabled: model.canSave,
                    loading: model.saving
                ) {
                    Task { await model.save() }
                }
            }
        }
        .onChange(of: model.done) { _, done in
            if done { router.pop() }
        }
    }

    private var formCard: some View {
        MBCard {
            MBTextField(
                placeholder: "8600 0000 0000 0000",
                text: Binding(
                    get: { CardFormat.number(model.number) },
                    set: { model.setNumber($0) }
                ),
                label: L("karta_raqami"),
                keyboard: .numberPad,
                leadingGlyph: "card",
                error: model.numberError
            )
            Spacer().frame(height: 14)
            HStack(spacing: 12) {
                MBTextField(
                    placeholder: L("mm_yy"),
                    text: Binding(
                        get: { CardFormat.expiry(model.expiry) },
                        set: { model.setExpiry($0) }
                    ),
                    label: L("amal_qilish_muddati"),
                    keyboard: .numberPad
                )
                MBTextField(
                    placeholder: "",
                    text: .constant(model.brand.label),
                    label: L("tolov_tizimi"),
                    disabled: true
                )
            }
            Spacer().frame(height: 14)
            MBTextField(
                placeholder: L("aziz_toshmatov"),
                text: Binding(
                    get: { model.holder },
                    set: { model.setHolder($0) }
                ),
                label: L("karta_egasi")
            )
        }
    }

    private var defaultCard: some View {
        MBCard(padding: 6) {
            MBToggleRow(
                label: L("asosiy_karta"),
                subtitle: L("buyurtma_berishda_avtomatik_tanlanadi"),
                glyph: "card",
                isOn: Binding(
                    get: { model.makeDefault },
                    set: { model.makeDefault = $0 }
                )
            )
            .padding(.horizontal, 10)
        }
    }
}

/// The gradient tile from screen 32, filled in as the user types.
private struct CardPreview: View {
    let model: AddCardModel

    private var maskedNumber: String {
        let digits = Array(model.number.padding(toLength: 16, withPad: "\u{2022}", startingAt: 0))
        var out = ""
        for (index, character) in digits.enumerated() {
            if index > 0 && index % 4 == 0 { out += "  " }
            // Only the last four digits are ever shown back.
            out.append(index < 12 && character != "\u{2022}" ? "\u{2022}" : character)
        }
        return out
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(model.brand == .unknown ? L("yangi_karta") : model.brand.label)
                    .mbFont(MB.type.label)
                    .foregroundStyle(.white)
                Spacer()
                if model.makeDefault {
                    MBStatusPill(L("asosiy"), background: .white.opacity(0.2), contentColor: .white)
                }
            }
            Spacer()
            Text(maskedNumber).mbFont(MB.type.title3).foregroundStyle(.white)
            Spacer().frame(height: 10)
            HStack {
                Text(model.holder.isEmpty ? L("karta_egasi_2") : model.holder)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(.white.opacity(0.75))
                Spacer()
                Text(model.expiry.count == 4 ? CardFormat.expiry(model.expiry) : L("mm_yy"))
                    .mbFont(MB.type.caption)
                    .foregroundStyle(.white.opacity(0.75))
            }
        }
        .padding(20)
        .frame(height: 180)
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(
                colors: [MB.color.cardFrom, MB.color.accent],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXXL, style: .continuous))
    }
}
