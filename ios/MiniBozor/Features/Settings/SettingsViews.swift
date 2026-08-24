import SwiftUI

/// Screen 36 — Bildirishnomalar.
struct NotificationsView: View {
    @Environment(Router.self) var router
    @State var model = NotificationsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(title: "Bildirishnomalar", onBack: { router.pop() }) {
                    Button {
                        Task { await model.markAllRead() }
                    } label: {
                        MBIcon("bell", size: 20, tint: MB.color.accent)
                    }
                    .buttonStyle(.plain)
                }

                if model.groups.isEmpty {
                    MBEmptyState(
                        glyph: "bell",
                        title: "Bildirishnoma yo'q",
                        message: "Buyurtma holati va chegirmalar haqida shu yerda xabar beramiz."
                    )
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(model.groups) { group in
                                Text(group.label)
                                    .mbFont(MB.type.captionBold)
                                    .foregroundStyle(MB.color.textSecondary)
                                    .padding(.leading, 6)

                                MBCard(padding: 6) {
                                    ForEach(Array(group.items.enumerated()), id: \.element.id) { offset, item in
                                        row(item)
                                        if offset != group.items.count - 1 { MBDivider(inset: 60) }
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

    private func row(_ item: NotificationDTO) -> some View {
        HStack(alignment: .top, spacing: 12) {
            MBIcon(item.icon, size: 18)
                .frame(width: 38, height: 38)
                .background(MB.color.fill)
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(item.title).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                        .lineLimit(1)
                    Spacer()
                    if !item.read {
                        Circle().fill(MB.color.accent).frame(width: 7, height: 7)
                    }
                }
                Text(item.text).mbFont(MB.type.meta).foregroundStyle(MB.color.textSecondary)
                if let date = UzDate.parseDateTime(item.createdAt) {
                    Text(UzDate.relative(date)).mbFont(MB.type.micro)
                        .foregroundStyle(MB.color.disabled)
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 12)
        .contentShape(Rectangle())
        .onTapGesture {
            if let link = item.deepLink,
               let id = Int(link.split(separator: "/").last ?? "") {
                router.push(.orderDetail(orderId: id))
            }
        }
    }
}

/// Screen 37 — Sozlamalar.
struct SettingsView: View {
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Sozlamalar", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        menuCard
                        togglesCard
                        Text("Mini Bozor · versiya 1.0")
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.disabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 6)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }

    private var menuCard: some View {
        MBCard(padding: 6) {
            let rows: [(String, String, String, Route)] = [
                ("bell", "Bildirishnoma sozlamalari", "Push, SMS", .notificationSettings),
                ("globe", "Ilova tili", model.languageLabel, .language),
                ("gear", "Xavfsizlik", model.hasPin ? "PIN yoqilgan" : "PIN o'rnatilmagan", .security),
                ("headset", "Yordam markazi", "1150", .help),
                ("ret", "Shartlar va maxfiylik", "", .legal),
            ]
            ForEach(Array(rows.enumerated()), id: \.offset) { offset, row in
                MBListRow(row.1, glyph: row.0, meta: row.2.isEmpty ? nil : row.2) {
                    router.push(row.3)
                }
                .padding(.horizontal, 10)
                if offset != rows.count - 1 { MBDivider(inset: 60) }
            }
        }
    }

    private var togglesCard: some View {
        MBCard(padding: 6) {
            MBToggleRow(
                label: "Joylashuv",
                subtitle: "Yaqin punktlarni ko'rsatish",
                glyph: "pin",
                isOn: Binding(
                    get: { model.settings?.locationEnabled ?? true },
                    set: { value in Task { await model.setLocation(value) } }
                )
            )
            .padding(.horizontal, 10)
            MBDivider(inset: 60)
            MBToggleRow(
                label: "Tungi rejim",
                subtitle: "Tizim bilan moslashadi",
                glyph: "gear",
                isOn: Binding(
                    get: { model.settings?.nightMode ?? false },
                    set: { value in Task { await model.setNightMode(value) } }
                )
            )
            .padding(.horizontal, 10)
        }
    }
}

/// Screen 38 — Bildirishnoma sozlamalari.
struct NotificationSettingsView: View {
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Bildirishnomalar", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            toggle("Buyurtma holati", "Yig'ildi, yo'lda, yetkazildi", "box",
                                   value: model.prefs?.orderStatus ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(orderStatus: value))
                            }
                            MBDivider(inset: 60)
                            toggle("Chegirma va aksiyalar", "Haftada 2 martadan ko'p emas", "gift",
                                   value: model.prefs?.promotions ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(promotions: value))
                            }
                            MBDivider(inset: 60)
                            toggle("Sevimlilar narxi", "Narx tushganda xabar", "heart",
                                   value: model.prefs?.priceDrop ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(priceDrop: value))
                            }
                        }

                        MBCard(padding: 6) {
                            SectionHeader(title: "Kanallar")
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                            toggle("Push bildirishnoma", nil, "bell",
                                   value: model.prefs?.push ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(push: value))
                            }
                            MBDivider(inset: 60)
                            toggle("SMS", nil, "phone", value: model.prefs?.sms ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(sms: value))
                            }
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }

    private func toggle(
        _ label: String,
        _ subtitle: String?,
        _ glyph: String,
        value: Bool,
        set: @escaping (Bool) async -> Void
    ) -> some View {
        MBToggleRow(
            label: label,
            subtitle: subtitle,
            glyph: glyph,
            isOn: Binding(get: { value }, set: { newValue in Task { await set(newValue) } })
        )
        .padding(.horizontal, 10)
    }
}

/// Screen 39 — Til.
struct LanguageView: View {
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Ilova tili", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            ForEach(Array(model.languages.enumerated()), id: \.offset) { offset, language in
                                let code = language["code"] ?? ""
                                MBRadioRow(
                                    label: language["label"] ?? "",
                                    subtitle: language["native"],
                                    selected: model.settings?.language == code,
                                    onSelect: { Task { await model.setLanguage(code) } }
                                ) {
                                    Text(code.uppercased())
                                        .mbFont(MB.type.micro)
                                        .foregroundStyle(MB.color.textSecondary)
                                        .frame(width: 38, height: 38)
                                        .background(MB.color.fill)
                                        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
                                }
                                .padding(.horizontal, 10)
                                if offset != model.languages.count - 1 { MBDivider(inset: 60) }
                            }
                        }
                        Text("Til o'zgarishi ilova qayta ishga tushganda to'liq qo'llanadi.")
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.textQuaternary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 6)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}

/// Screen 40 — Xavfsizlik.
struct SecurityView: View {
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Xavfsizlik", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            MBListRow(
                                model.hasPin ? "PIN kodni o'zgartirish" : "PIN kod o'rnatish",
                                glyph: "gear",
                                subtitle: "Ilovaga kirishda so'raladi"
                            ) {
                                router.push(.pin(hasPin: model.hasPin))
                            }
                            .padding(.horizontal, 10)
                            MBDivider(inset: 60)
                            MBToggleRow(
                                label: "Face ID / barmoq izi",
                                subtitle: "PIN o'rniga biometrika",
                                glyph: "user",
                                isOn: Binding(
                                    get: { model.biometrics },
                                    set: { value in Task { await model.setBiometrics(value) } }
                                )
                            )
                            .padding(.horizontal, 10)
                        }

                        Text("PIN kod ilovani ochishda so'raladi. Unutib qo'ysangiz — "
                             + "hisobdan chiqib, SMS orqali qayta kiring.")
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.textQuaternary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 6)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}
