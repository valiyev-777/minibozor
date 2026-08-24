import SwiftUI

/// Screen 21 — day chips across the top, time windows below.
struct DeliveryTimeView: View {
    @Environment(Router.self) var router
    @Environment(CheckoutModel.self) var model
    @State var dayIndex = 0

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Yetkazish vaqti", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        dayChips
                        slotCard
                        Text("Kuryer yetkazishdan 30 daqiqa oldin qo'ng'iroq qiladi.")
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
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton("Tasdiqlash", enabled: model.slotId != nil) { router.pop() }
            }
        }
    }

    private var dayChips: some View {
        HStack(spacing: 10) {
            ForEach(Array(model.slotDays.enumerated()), id: \.element.id) { offset, day in
                let selected = offset == dayIndex
                Button {
                    dayIndex = offset
                } label: {
                    VStack(spacing: 4) {
                        Text(day.weekdayLabel)
                            .mbFont(MB.type.micro)
                            .foregroundStyle(selected ? .white.opacity(0.6) : MB.color.disabled)
                        Text(day.dayLabel)
                            .mbFont(MB.type.title2)
                            .foregroundStyle(selected ? .white : MB.color.textSecondary)
                        Text(day.monthLabel)
                            .mbFont(MB.type.micro)
                            .foregroundStyle(selected ? .white.opacity(0.6) : MB.color.disabled)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(selected ? MB.color.ink : MB.color.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous)
                            .stroke(selected ? MB.color.ink : MB.color.border, lineWidth: selected ? 1.6 : 1)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXL, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var slotCard: some View {
        MBCard(padding: 6) {
            let slots = model.slotDays.indices.contains(dayIndex) ? model.slotDays[dayIndex].slots : []
            if slots.isEmpty {
                Text("Bu kunga bo'sh oraliq qolmadi.")
                    .mbFont(MB.type.bodySmall)
                    .foregroundStyle(MB.color.icon)
                    .padding(16)
            }
            ForEach(Array(slots.enumerated()), id: \.element.id) { offset, slot in
                MBRadioRow(
                    slot.label,
                    subtitle: slot.note.isEmpty ? nil : slot.note,
                    trailingLabel: slot.price == 0 ? "Bepul" : "+\(Format.sum(slot.price))",
                    trailingColor: slot.price == 0 ? MB.color.success : MB.color.ink,
                    selected: slot.id == model.slotId
                ) {
                    Task { await model.selectSlot(slot.id) }
                }
                .padding(.horizontal, 10)
                if offset != slots.count - 1 { MBDivider() }
            }
        }
    }
}
