import SwiftUI

/// Selectable pill: solid ink when selected, hairline outline when not.
struct MBChip: View {
    let label: String
    let selected: Bool
    var enabled: Bool = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .mbFont(MB.type.caption)
                .foregroundStyle(foreground)
                .lineLimit(1)
                .padding(.horizontal, 14)
                .padding(.vertical, 9)
                .background(background)
                .overlay(
                    Capsule().stroke(
                        selected || !enabled ? .clear : MB.color.border,
                        lineWidth: 1
                    )
                )
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }

    private var background: Color {
        if !enabled { return MB.color.fill }
        return selected ? MB.color.ink : MB.color.surface
    }

    private var foreground: Color {
        if !enabled { return MB.color.disabled }
        return selected ? .white : MB.color.inkSoft
    }

    init(_ label: String, selected: Bool, enabled: Bool = true, action: @escaping () -> Void) {
        self.label = label
        self.selected = selected
        self.enabled = enabled
        self.action = action
    }
}

/// Square-ish size chip (39–46, S–XXL) from the product page.
struct MBSizeChip: View {
    let label: String
    let selected: Bool
    var enabled: Bool = true
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .mbFont(MB.type.label)
                .foregroundStyle(enabled ? (selected ? .white : MB.color.textSecondary) : MB.color.disabled)
                .padding(.horizontal, 16)
                .padding(.vertical, 11)
                .background(selected ? MB.color.ink : MB.color.surface)
                .overlay(
                    RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous)
                        .stroke(selected ? MB.color.ink : MB.color.border, lineWidth: selected ? 1.6 : 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }

    init(_ label: String, selected: Bool, enabled: Bool = true, action: @escaping () -> Void) {
        self.label = label
        self.selected = selected
        self.enabled = enabled
        self.action = action
    }
}

/// Status pill: order state, review moderation state, address label.
struct MBStatusPill: View {
    let label: String
    let background: Color
    let contentColor: Color

    var body: some View {
        Text(label)
            .mbFont(MB.type.badge)
            .foregroundStyle(contentColor)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXS, style: .continuous))
    }

    init(_ label: String, background: Color, contentColor: Color) {
        self.label = label
        self.background = background
        self.contentColor = contentColor
    }
}

/// Order status → the palette the design uses for its pills.
enum OrderStatusStyle {
    static func background(_ status: String) -> Color {
        switch status {
        case "packing": return MB.color.warningBg
        case "delivered": return MB.color.successBg
        case "cancelled", "returned": return MB.color.dangerBg
        default: return MB.color.fillCool
        }
    }

    static func foreground(_ status: String) -> Color {
        switch status {
        case "packing": return MB.color.warning
        case "delivered": return MB.color.success
        case "cancelled", "returned": return MB.color.danger
        default: return MB.color.accent
        }
    }
}
