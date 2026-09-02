import SwiftUI

/// The tappable list row used by the catalogue, profile, settings and help.
struct MBListRow<Trailing: View>: View {
    let label: String
    var glyph: String?
    /// A supplied picture for the leading square; falls back to `glyph`.
    var imageUrl: String?
    var subtitle: String?
    var meta: String?
    var showChevron: Bool = true
    var tint: Color = MB.color.ink
    var onTap: (() -> Void)?
    @ViewBuilder var trailing: Trailing

    var body: some View {
        let row = HStack(spacing: 12) {
            if imageUrl != nil || glyph != nil {
                Group {
                    if let imageUrl, let parsed = AppConfig.media(imageUrl) {
                        AsyncImage(url: parsed) { phase in
                            if let picture = phase.image {
                                picture.resizable().scaledToFit()
                            } else {
                                Color.clear
                            }
                        }
                        .padding(4)
                    } else if let glyph {
                        MBIcon(glyph, size: 18, tint: tint)
                    }
                }
                .frame(width: 38, height: 38)
                .background(MB.color.fill)
                .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(label).mbFont(MB.type.bodyBold).foregroundStyle(tint).lineLimit(1)
                if let subtitle {
                    Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.icon).lineLimit(2)
                }
            }
            Spacer(minLength: 8)
            trailing
            if let meta, !meta.isEmpty {
                Text(meta).mbFont(MB.type.caption).foregroundStyle(MB.color.icon).lineLimit(1)
            }
            if showChevron {
                Text("›").mbFont(MB.type.title3).foregroundStyle(MB.color.hairlineStrong)
            }
        }
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())

        if let onTap {
            Button(action: onTap) { row }.buttonStyle(.plain)
        } else {
            row
        }
    }
}

extension MBListRow where Trailing == EmptyView {
    init(
        _ label: String,
        glyph: String? = nil,
        imageUrl: String? = nil,
        subtitle: String? = nil,
        meta: String? = nil,
        showChevron: Bool = true,
        tint: Color = MB.color.ink,
        onTap: (() -> Void)? = nil
    ) {
        self.init(
            label: label, glyph: glyph, imageUrl: imageUrl, subtitle: subtitle,
            meta: meta, showChevron: showChevron, tint: tint, onTap: onTap
        ) { EmptyView() }
    }
}

/// Switch row — notification preferences, location, night mode.
struct MBToggleRow: View {
    let label: String
    var subtitle: String?
    var glyph: String?
    @Binding var isOn: Bool

    var body: some View {
        MBListRow(
            label: label,
            glyph: glyph,
            subtitle: subtitle,
            showChevron: false
        ) {
            MBSwitch(isOn: $isOn)
        }
    }
}

struct MBSwitch: View {
    @Binding var isOn: Bool

    var body: some View {
        Button {
            isOn.toggle()
        } label: {
            ZStack(alignment: isOn ? .trailing : .leading) {
                Capsule().fill(isOn ? MB.color.accent : MB.color.divider)
                Circle().fill(.white).frame(width: 20, height: 20).padding(2)
            }
            .frame(width: 40, height: 24)
            .animation(.easeOut(duration: 0.16), value: isOn)
        }
        .buttonStyle(.plain)
    }
}

/// Radio row — delivery slot, payment method, cancel reason, language.
struct MBRadioRow<Leading: View>: View {
    let label: String
    var subtitle: String?
    var trailingLabel: String?
    var trailingColor: Color = MB.color.ink
    let selected: Bool
    let onSelect: () -> Void
    @ViewBuilder var leading: Leading

    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 12) {
                leading
                VStack(alignment: .leading, spacing: 2) {
                    Text(label).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                    if let subtitle {
                        Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                            .lineLimit(2)
                    }
                }
                Spacer(minLength: 8)
                if let trailingLabel {
                    Text(trailingLabel).mbFont(MB.type.label).foregroundStyle(trailingColor)
                }
                MBRadio(selected: selected)
            }
            .padding(.vertical, 13)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

extension MBRadioRow where Leading == EmptyView {
    init(
        _ label: String,
        subtitle: String? = nil,
        trailingLabel: String? = nil,
        trailingColor: Color = MB.color.ink,
        selected: Bool,
        onSelect: @escaping () -> Void
    ) {
        self.init(
            label: label, subtitle: subtitle, trailingLabel: trailingLabel,
            trailingColor: trailingColor, selected: selected, onSelect: onSelect
        ) { EmptyView() }
    }
}

struct MBRadio: View {
    let selected: Bool

    var body: some View {
        Circle()
            .strokeBorder(
                selected ? MB.color.accent : MB.color.hairline,
                lineWidth: selected ? 5 : 1.5
            )
            .frame(width: 20, height: 20)
    }
}

/// Checkbox row — filter flags and brand lists.
struct MBCheckRow: View {
    let label: String
    var subtitle: String?
    var count: String?
    let checked: Bool
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(spacing: 12) {
                MBCheckbox(checked: checked)
                VStack(alignment: .leading, spacing: 2) {
                    Text(label).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                    if let subtitle {
                        Text(subtitle).mbFont(MB.type.meta).foregroundStyle(MB.color.icon)
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 8)
                if let count {
                    Text(count).mbFont(MB.type.caption).foregroundStyle(MB.color.icon)
                }
            }
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

struct MBCheckbox: View {
    let checked: Bool

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .fill(checked ? MB.color.accent : .clear)
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .stroke(checked ? .clear : MB.color.hairline, lineWidth: 1.5)
            if checked {
                Text("✓").mbFont(MB.type.micro).foregroundStyle(.white)
            }
        }
        .frame(width: 22, height: 22)
    }
}

/// A "key — value" line, used by order summaries and product specs.
struct MBKeyValueRow: View {
    let key: String
    let value: String

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Text(key).mbFont(MB.type.bodySmall).foregroundStyle(MB.color.icon)
            Spacer(minLength: 0)
            Text(value)
                .mbFont(MB.type.bodySmall)
                .fontWeight(.bold)
                .foregroundStyle(MB.color.ink)
                .multilineTextAlignment(.trailing)
        }
        .padding(.vertical, 9)
    }
}

/// Totals line in the cart and checkout; `strong` renders the grand total.
struct MBTotalRow: View {
    let label: String
    let value: String
    var strong: Bool = false
    var valueColor: Color = MB.color.ink

    var body: some View {
        HStack {
            Text(label)
                .mbFont(strong ? MB.type.sectionHead : MB.type.bodySmall)
                .foregroundStyle(strong ? MB.color.ink : MB.color.textSecondary)
            Spacer(minLength: 8)
            Text(value)
                .mbFont(strong ? MB.type.price : MB.type.label)
                .foregroundStyle(valueColor)
        }
        .padding(.vertical, strong ? 8 : 6)
    }
}
