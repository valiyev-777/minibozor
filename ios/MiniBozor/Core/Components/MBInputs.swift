import SwiftUI

/// Labelled text field, matching the address and profile forms.
struct MBTextField: View {
    let placeholder: String
    @Binding var text: String
    var label: String?
    var keyboard: UIKeyboardType = .default
    var multiline: Bool = false
    var minHeight: CGFloat = 48
    var leadingGlyph: String?
    var error: String?
    var disabled: Bool = false
    var trailingText: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let label {
                Text(label).mbFont(MB.type.caption).foregroundStyle(MB.color.textQuaternary)
            }
            HStack(spacing: 10) {
                if let leadingGlyph {
                    MBIcon(leadingGlyph, size: 16, tint: MB.color.icon, lineWidth: 1.9)
                }
                Group {
                    if multiline {
                        TextField(placeholder, text: $text, axis: .vertical)
                            .lineLimit(3...8)
                    } else {
                        TextField(placeholder, text: $text)
                    }
                }
                .mbFont(MB.type.bodySmall)
                .foregroundStyle(MB.color.ink)
                .keyboardType(keyboard)
                .disabled(disabled)
                .tint(MB.color.accent)

                if let trailingText {
                    Text(trailingText).mbFont(MB.type.micro).foregroundStyle(MB.color.disabled)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(minHeight: minHeight, alignment: .center)
            .background(MB.color.fill)
            .overlay(
                RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous)
                    .stroke(error == nil ? .clear : MB.color.danger, lineWidth: 1.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))

            if let error {
                Text(error).mbFont(MB.type.caption).foregroundStyle(MB.color.danger)
            }
        }
    }
}

/// The read-only search pill on the home screen.
struct MBSearchPill: View {
    let placeholder: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                MBIcon("search", size: 14, tint: MB.color.icon, lineWidth: 2)
                Text(placeholder).mbFont(MB.type.bodySmall).foregroundStyle(MB.color.icon)
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .frame(height: MB.metric.searchHeight)
            .background(MB.color.canvas)
            .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

/// The live search field on screen 08.
struct MBSearchField: View {
    @Binding var text: String
    var placeholder: String = L("mahsulot_va_turkumlar_qidirish")
    var onSubmit: () -> Void = {}
    @FocusState var focused: Bool

    var body: some View {
        HStack(spacing: 8) {
            MBIcon("search", size: 14, tint: MB.color.icon, lineWidth: 2)
            TextField(placeholder, text: $text)
                .mbFont(MB.type.bodySmall)
                .foregroundStyle(MB.color.ink)
                .tint(MB.color.accent)
                .submitLabel(.search)
                .focused($focused)
                .onSubmit(onSubmit)
            if !text.isEmpty {
                Button {
                    text = ""
                } label: {
                    Text("×")
                        .mbFont(MB.type.micro)
                        .foregroundStyle(.white)
                        .frame(width: 18, height: 18)
                        .background(MB.color.hairlineStrong)
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 12)
        .frame(height: MB.metric.searchHeight + 4)
        .background(MB.color.fill)
        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
        .onAppear { focused = true }
    }
}

/// Boxed code entry for the SMS and PIN screens: real boxes over one hidden
/// field, so the system keyboard and SMS autofill both behave normally.
struct MBCodeField: View {
    @Binding var code: String
    var length: Int = 6
    var masked: Bool = false
    var isError: Bool = false
    @FocusState var focused: Bool

    var body: some View {
        ZStack {
            TextField("", text: $code)
                .keyboardType(.numberPad)
                .textContentType(.oneTimeCode)
                .focused($focused)
                .foregroundStyle(.clear)
                .tint(.clear)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .onChange(of: code) { _, newValue in
                    let digits = newValue.filter(\.isNumber)
                    code = String(digits.prefix(length))
                }

            HStack(spacing: 10) {
                ForEach(0..<length, id: \.self) { index in
                    box(at: index)
                }
            }
            .allowsHitTesting(false)
        }
        .frame(height: 60)
        .contentShape(Rectangle())
        .onTapGesture { focused = true }
        .onAppear { focused = true }
    }

    @ViewBuilder
    private func box(at index: Int) -> some View {
        let characters = Array(code)
        let filled = index < characters.count
        ZStack {
            RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous)
                .fill(filled ? MB.color.surface : MB.color.fill)
            RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous)
                .stroke(
                    isError ? MB.color.danger : (filled ? MB.color.ink : .clear),
                    lineWidth: (isError || filled) ? 1.6 : 0
                )
            if filled {
                if masked {
                    Circle().fill(MB.color.ink).frame(width: 10, height: 10)
                } else {
                    Text(String(characters[index]))
                        .mbFont(MB.type.title2)
                        .foregroundStyle(MB.color.ink)
                }
            }
        }
        .frame(width: length > 4 ? 46 : 54, height: 60)
    }
}

/// −/+ stepper used in the cart and on the product page.
struct MBQuantityStepper: View {
    let quantity: Int
    var minimum: Int = 1
    var maximum: Int = 99
    /// The tap target at each end. Cart rows want the compact default; a
    /// stepper standing next to a button wants that button's height, so the
    /// two read as one bar.
    var size: CGFloat = 34
    let onChange: (Int) -> Void

    var body: some View {
        HStack(spacing: 0) {
            stepButton("−", enabled: quantity > minimum) { onChange(quantity - 1) }
            Text("\(quantity)")
                .mbFont(size >= 44 ? MB.type.title3 : MB.type.label)
                .foregroundStyle(MB.color.ink)
                .frame(width: size)
            stepButton("+", enabled: quantity < maximum) { onChange(quantity + 1) }
        }
        .background(MB.color.fill)
        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusM, style: .continuous))
    }

    private func stepButton(_ symbol: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(symbol)
                .mbFont(size >= 44 ? MB.type.title2 : MB.type.title3)
                .foregroundStyle(enabled ? MB.color.ink : MB.color.disabled)
                .frame(width: size, height: size)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }
}
