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
        AddressPreset(title: "Uy", icon: "pin", badge: "ASOSIY"),
        AddressPreset(title: "Ish", icon: "box", badge: "OFIS"),
        AddressPreset(title: "Boshqa", icon: "star", badge: nil),
    ] }

    @State var preset: AddressPreset
    @State var line = ""
    @State var floor = ""
    @State var apartment = ""
    @State var entranceCode = ""
    @State var comment = ""
    @State var isDefault = false
    @State var saving = false

    init() {
        _preset = State(initialValue: AddressPreset(title: "Uy", icon: "pin", badge: "ASOSIY"))
    }

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Manzil qo'shish", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard {
                            SectionHeader(title: "Manzil turi")
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
                                placeholder: "Toshkent, Amir Temur shoh ko'chasi 108",
                                text: $line,
                                label: "Ko'cha va uy raqami"
                            )
                            Spacer().frame(height: 14)
                            HStack(spacing: 12) {
                                MBTextField(placeholder: "12", text: $floor, label: "Qavat")
                                MBTextField(placeholder: "45", text: $apartment, label: "Xona")
                            }
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "1245K",
                                text: $entranceCode,
                                label: "Kirish kodi"
                            )
                            Spacer().frame(height: 14)
                            MBTextField(
                                placeholder: "Domofon ishlamaydi, qo'ng'iroq qiling",
                                text: $comment,
                                label: "Kuryerga izoh",
                                multiline: true,
                                minHeight: 80
                            )
                        }

                        MBCard(padding: 6) {
                            MBToggleRow(
                                label: "Asosiy manzil",
                                subtitle: "Buyurtma berishda avtomatik tanlanadi",
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
                MBPrimaryButton("Saqlash", enabled: !line.isEmpty, loading: saving) {
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
