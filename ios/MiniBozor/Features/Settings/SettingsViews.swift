import SwiftUI

/// Screen 36 — Bildirishnomalar.
struct NotificationsView: View {
    @Environment(Router.self) var router
    @State var model = NotificationsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(title: L("bildirishnomalar"), onBack: { router.pop() }) {
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
                        title: L("bildirishnoma_yoq"),
                        message: L("buyurtma_holati_va_chegirmalar_haqida_shu")
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
    @Environment(Appearance.self) var appearance
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("sozlamalar"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        menuCard
                        togglesCard
                        Text(L("mini_bozor_versiya_1_0"))
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
                ("bell", L("bildirishnoma_sozlamalari"), L("push_sms"), .notificationSettings),
                ("globe", L("ilova_tili"), model.languageLabel, .language),
                ("gear", L("xavfsizlik"), model.hasPin ? L("pin_yoqilgan") : L("pin_ornatilmagan"), .security),
                ("headset", L("yordam_markazi"), "1150", .help),
                ("ret", L("shartlar_va_maxfiylik"), "", .legal),
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
                label: L("joylashuv"),
                subtitle: L("yaqin_punktlarni_korsatish"),
                glyph: "pin",
                isOn: Binding(
                    get: { model.settings?.locationEnabled ?? true },
                    set: { value in Task { await model.setLocation(value) } }
                )
            )
            .padding(.horizontal, 10)
            MBDivider(inset: 60)
            MBToggleRow(
                label: L("tungi_rejim"),
                subtitle: L("tizim_bilan_moslashadi"),
                glyph: "gear",
                // Written to the device first, then mirrored to the account:
                // the device is what the customer is looking at, and the round
                // trip only keeps their other phones in step.
                isOn: Binding(
                    get: { appearance.forceDark },
                    set: { value in
                        appearance.forceDark = value
                        Task { await model.setNightMode(value) }
                    }
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
                MBTopBar(L("bildirishnomalar"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            toggle(L("buyurtma_holati"), L("yigildi_yolda_yetkazildi"), "box",
                                   value: model.prefs?.orderStatus ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(orderStatus: value))
                            }
                            MBDivider(inset: 60)
                            toggle(L("chegirma_va_aksiyalar"), L("haftada_2_martadan_kop_emas"), "gift",
                                   value: model.prefs?.promotions ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(promotions: value))
                            }
                            MBDivider(inset: 60)
                            toggle(L("sevimlilar_narxi"), L("narx_tushganda_xabar"), "heart",
                                   value: model.prefs?.priceDrop ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(priceDrop: value))
                            }
                        }

                        MBCard(padding: 6) {
                            SectionHeader(title: L("kanallar"))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 8)
                            toggle(L("push_bildirishnoma"), nil, "bell",
                                   value: model.prefs?.push ?? true) { value in
                                await model.setPref(NotificationPrefsRequest(push: value))
                            }
                            MBDivider(inset: 60)
                            toggle(L("sms"), nil, "phone", value: model.prefs?.sms ?? true) { value in
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
    @Environment(Localization.self) var localization
    @Environment(Router.self) var router
    @State var model = SettingsModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("ilova_tili"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            ForEach(Array(model.languages.enumerated()), id: \.offset) { offset, language in
                                let code = language["code"] ?? ""
                                MBRadioRow(
                                    label: language["label"] ?? "",
                                    subtitle: language["native"],
                                    selected: localization.code == code,
                                    onSelect: {
                                        // Applied here first — the screen is
                                        // what the customer is looking at —
                                        // then mirrored to the account.
                                        localization.apply(code)
                                        Task { await model.setLanguage(code) }
                                    }
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
                        Text(L("tanlangan_til_darhol_qollanadi_turkum"))
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
                MBTopBar(L("xavfsizlik"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard(padding: 6) {
                            MBListRow(
                                model.hasPin ? L("pin_kodni_ozgartirish") : L("pin_kod_ornatish"),
                                glyph: "gear",
                                subtitle: L("ilovaga_kirishda_soraladi")
                            ) {
                                router.push(.pin(hasPin: model.hasPin))
                            }
                            .padding(.horizontal, 10)
                            MBDivider(inset: 60)
                            MBToggleRow(
                                label: L("face_id_barmoq_izi"),
                                subtitle: L("pin_orniga_biometrika"),
                                glyph: "user",
                                isOn: Binding(
                                    get: { model.biometrics },
                                    set: { value in Task { await model.setBiometrics(value) } }
                                )
                            )
                            .padding(.horizontal, 10)
                        }

                        Text(L("pin_kod_ilovani_ochishda_soraladi_unutib"))
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
