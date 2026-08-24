import SwiftUI

struct MBTabItem: Identifiable, Hashable {
    let id: String
    let glyph: String
    let label: String
    var badge: Int = 0
}

/// The floating bottom bar from the design: a rounded translucent slab inset
/// from the screen edges, with a tinted pill behind the active item.
struct MBTabBar: View {
    let tabs: [MBTabItem]
    @Binding var selection: String

    var body: some View {
        HStack(spacing: 0) {
            ForEach(tabs) { tab in
                item(tab)
            }
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 8)
        .background(.regularMaterial)
        .background(Color.white.opacity(0.55))
        .overlay(
            RoundedRectangle(cornerRadius: MB.metric.radiusSheet, style: .continuous)
                .stroke(.white.opacity(0.8), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusSheet, style: .continuous))
        .shadow(color: Color(hex: 0x101428, alpha: 0.13), radius: 17, x: 0, y: 8)
        .padding(.horizontal, MB.metric.tabBarInset)
        .padding(.bottom, 8)
    }

    private func item(_ tab: MBTabItem) -> some View {
        let active = tab.id == selection
        let tint = active ? MB.color.accent : MB.color.icon

        return Button {
            selection = tab.id
        } label: {
            VStack(spacing: 4) {
                MBIcon(tab.glyph, size: 20, tint: tint, lineWidth: 1.7)
                Text(tab.label).mbFont(MB.type.micro).foregroundStyle(tint).lineLimit(1)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
            .background(active ? MB.color.ink.opacity(0.05) : .clear)
            .clipShape(RoundedRectangle(cornerRadius: 17, style: .continuous))
            .overlay(alignment: .topTrailing) {
                if tab.badge > 0 {
                    Text(tab.badge > 99 ? "99+" : "\(tab.badge)")
                        .mbFont(MB.type.micro)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 4)
                        .frame(minWidth: 15, minHeight: 15)
                        .background(MB.color.danger)
                        .clipShape(Capsule())
                        .offset(x: -14, y: 2)
                }
            }
        }
        .buttonStyle(.plain)
    }
}
