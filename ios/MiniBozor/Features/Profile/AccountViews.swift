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
        .task { await model.load() }
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

/// Adding a card.
///
/// The card number is deliberately **not** collected here. The processor's own
/// SDK or 3-D Secure webview takes the PAN and returns a token, which is the
/// only thing `POST /payment-cards` accepts — so the app stays out of PCI scope.
struct AddCardView: View {
    @Environment(Router.self) var router

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Karta qo'shish", onBack: { router.pop() })
                VStack(spacing: 0) {
                    Spacer().frame(height: 24)
                    MBIcon("card", size: 36, tint: MB.color.accent, lineWidth: 1.6)
                        .frame(width: 88, height: 88)
                        .background(MB.color.accentTint)
                        .clipShape(Circle())
                    Spacer().frame(height: 20)
                    Text("Karta ma'lumotlari himoyalangan")
                        .mbFont(MB.type.title3)
                        .foregroundStyle(MB.color.ink)
                        .multilineTextAlignment(.center)
                    Spacer().frame(height: 8)
                    Text("Karta raqamini to'lov tizimining xavfsiz oynasida kiritasiz. "
                         + "Mini Bozor faqat kartaning oxirgi 4 raqamini saqlaydi.")
                        .mbFont(MB.type.bodySmall)
                        .foregroundStyle(MB.color.textTertiary)
                        .multilineTextAlignment(.center)
                    Spacer().frame(height: 24)
                    MBCard(padding: 6) {
                        MBListRow(
                            "Humo va UzCard",
                            glyph: "card",
                            subtitle: "Milliy to'lov tizimlari",
                            showChevron: false
                        )
                        .padding(.horizontal, 10)
                        MBListRow(
                            "Visa va Mastercard",
                            glyph: "globe",
                            subtitle: "Xalqaro kartalar",
                            showChevron: false
                        )
                        .padding(.horizontal, 10)
                    }
                    Spacer()
                }
                .padding(12)
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton("Xavfsiz oynani ochish", leadingGlyph: "card") {
                    // Present the processor's SDK here, then POST the token.
                    router.pop()
                }
            }
        }
    }
}
