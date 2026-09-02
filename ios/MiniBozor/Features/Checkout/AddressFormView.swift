import SwiftUI

private struct AddressPreset: Hashable {
    let title: String
    let icon: String
    let badge: String?
}

/// Screen 20 — Manzil qo'shish.
struct AddressFormView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model

    private var presets: [AddressPreset] { [
        AddressPreset(title: L("preset_uy"), icon: "pin", badge: L("asosiy")),
        AddressPreset(title: L("preset_ish"), icon: "box", badge: L("preset_badge_ofis")),
        AddressPreset(title: L("preset_boshqa"), icon: "star", badge: nil),
    ] }

    @State private var preset: AddressPreset
    @State var line = ""
    @State var floor = ""
    @State var apartment = ""
    @State var entranceCode = ""
    @State var comment = ""
    @State var isDefault = false
    @State var saving = false

    init() {
        _preset = State(initialValue: AddressPreset(title: L("preset_uy"), icon: "pin", badge: L("asosiy")))
    }

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(L("manzil_qoshish"), onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard {
                            SectionHeader(title: L("manzil_turi"))
                            Spacer().frame(height: 12)
                            FlowLayout(spacing: 8) {
                                ForEach(presets, id: \.self) { option in
                                    MBChip(option.title, selected: option == preset) {
                                        preset = option
                                    }
                                }
                            }
                        }

                        MBCard {
                            MBTextField(
                                placeholder: L("toshkent_amir_temur_shoh_kochasi_108"),
                                text: $line,
                                label: L("kocha_va_uy_raqami")
                            )
                            Spacer().frame(height: 14)
                            HStack(spacing: 12) {
                                MBTextField(placeholder: "12", text: $floor, label: L("qavat"))
                                MBTextField(placeholder: "45", text: $apartment, label: L("xona"))
                            }
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "1245K",
                                text: $entranceCode,
                                label: L("kirish_kodi")
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: L("domofon_ishlamaydi_qongiroq_qiling"),
                                text: $comment,
                                label: L("kuryerga_izoh"),
                                multiline: true,
                                minHeight: 80
                            )
                        }

                        MBCard(padding: 6) {
                            MBToggleRow(
                                label: L("asosiy_manzil"),
                                subtitle: L("buyurtma_berishda_avtomatik_tanlanadi"),
                                glyph: "pin",
                                isOn: $isDefault
                            )
                            .padding(.horizontal, 10)
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton(L("saqlash"), enabled: !line.isEmpty, loading: saving) {
                    Task { await save() }
                }
            }
        }
    }

    private func save() async {
        saving = true
        let created = await model.createAddress(
            AddressRequest(
                title: preset.title,
                icon: preset.icon,
                badge: preset.badge,
                line: line.trimmingCharacters(in: .whitespaces),
                floor: floor.isEmpty ? nil : floor,
                apartment: apartment.isEmpty ? nil : apartment,
                entranceCode: entranceCode.isEmpty ? nil : entranceCode,
                comment: comment.isEmpty ? nil : comment,
                isDefault: isDefault
            )
        )
        saving = false
        if created { router.pop() }
    }
}
