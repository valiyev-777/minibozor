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
                MBTopBar("Shaxsiy ma'lumotlar", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard {
                            MBTextField(
                                placeholder: "Aziz Toshmatov",
                                text: $fullName,
                                label: "Ism va familiya"
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "",
                                text: .constant(Format.phone(model.overview?.user.phone ?? "")),
                                label: "Telefon",
                                disabled: true,
                                trailingText: "O'zgartirib bo'lmaydi"
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "siz@example.uz",
                                text: $email,
                                label: "Email",
                                keyboard: .emailAddress
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "1994-05-12",
                                text: $birthDate,
                                label: "Tug'ilgan sana",
                                keyboard: .numbersAndPunctuation
                            )
                        }

                        MBCard {
                            SectionHeader(title: "Jins")
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
                MBPrimaryButton("Saqlash", enabled: !fullName.isEmpty, loading: model.saving) {
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
                MBTopBar("To'lov kartalari", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        ForEach(model.cards) { card in
                            cardTile(card)
                        }
                        MBCard(padding: 6) {
                            MBListRow(
                                "Yangi karta qo'shish",
                                glyph: "card",
                                subtitle: "Humo, UzCard, Visa",
                                tint: MB.color.accent
                            ) {
                                router.push(.addCard)
                            }
                            .padding(.horizontal, 10)
                        }
                        if model.cards.isEmpty {
                            Text("Karta qo'shsangiz — buyurtmani bir bosishda to'laysiz.")
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
                        MBStatusPill("ASOSIY", background: .white.opacity(0.2), contentColor: .white)
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
                    Text("Muddati o'tgan").mbFont(MB.type.caption)
                        .foregroundStyle(MB.color.danger)
                } else if !card.isDefault {
                    Button("Asosiy qilish") { Task { await model.makeDefault(card.id) } }
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.accent)
                }
                Spacer()
                Button("O'chirish") { Task { await model.delete(card.id) } }
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
                MBTopBar("Karta qo'shish", onBack: { router.pop() })
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
                            Text("Karta raqami qurilmadan chiqmaydi — serverda faqat oxirgi "
                                 + "4 raqam va muddati saqlanadi.")
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
                    "Kartani saqlash",
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
                label: "Karta raqami",
                keyboard: .numberPad,
                leadingGlyph: "card",
                error: model.numberError
            )
            Spacer().frame(height: 14)
            HStack(spacing: 12) {
                MBTextField(
                    placeholder: "MM/YY",
                    text: Binding(
                        get: { CardFormat.expiry(model.expiry) },
                        set: { model.setExpiry($0) }
                    ),
                    label: "Amal qilish muddati",
                    keyboard: .numberPad
                )
                MBTextField(
                    placeholder: "",
                    text: .constant(model.brand.label),
                    label: "To'lov tizimi",
                    disabled: true
                )
            }
            Spacer().frame(height: 14)
            MBTextField(
                placeholder: "AZIZ TOSHMATOV",
                text: Binding(
                    get: { model.holder },
                    set: { model.setHolder($0) }
                ),
                label: "Karta egasi"
            )
        }
    }

    private var defaultCard: some View {
        MBCard(padding: 6) {
            MBToggleRow(
                label: "Asosiy karta",
                subtitle: "Buyurtma berishda avtomatik tanlanadi",
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
                Text(model.brand == .unknown ? "Yangi karta" : model.brand.label)
                    .mbFont(MB.type.label)
                    .foregroundStyle(.white)
                Spacer()
                if model.makeDefault {
                    MBStatusPill("ASOSIY", background: .white.opacity(0.2), contentColor: .white)
                }
            }
            Spacer()
            Text(maskedNumber).mbFont(MB.type.title3).foregroundStyle(.white)
            Spacer().frame(height: 10)
            HStack {
                Text(model.holder.isEmpty ? "KARTA EGASI" : model.holder)
                    .mbFont(MB.type.caption)
                    .foregroundStyle(.white.opacity(0.75))
                Spacer()
                Text(model.expiry.count == 4 ? CardFormat.expiry(model.expiry) : "MM/YY")
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
