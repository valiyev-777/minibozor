import SwiftUI
import Observation

@Observable
final class ProfileModel {
    var overview: ProfileOverviewDTO?
    var loading = true
    var errorMessage: String?
    var saving = false
    var saved = false

    private let repo = ProfileRepository()

    @MainActor
    func load() async {
        loading = true
        switch await repo.overview() {
        case .success(let value): overview = value
        case .failure(let message): errorMessage = message
        }
        loading = false
    }

    @MainActor
    func save(fullName: String, email: String, birthDate: String?, gender: String?) async {
        saving = true
        saved = false
        let outcome = await repo.updateMe(
            UserUpdateRequest(
                fullName: fullName.trimmingCharacters(in: .whitespaces),
                email: email.isEmpty ? nil : email,
                birthDate: birthDate,
                gender: gender
            )
        )
        saving = false
        switch outcome {
        case .success: saved = true
        case .failure(let message): errorMessage = message
        }
    }
}

private struct QuickAction: Identifiable {
    var id: String { label }
    let glyph: String
    let label: String
    let route: Route
}

/// Screen 30 — Profil.
struct ProfileView: View {
    @Environment(Router.self) var router
    @Environment(AppSession.self) var session

    @State var model = ProfileModel()
    @State var confirmSignOut = false

    private var quickActions: [QuickAction] { [
        QuickAction(glyph: "box", label: L("buyurtmalar"), route: .orders),
        QuickAction(glyph: "heart", label: L("sevimlilar"), route: .favorites),
        QuickAction(glyph: "star", label: L("sharhlarim"), route: .myReviews),
        QuickAction(glyph: "ret", label: L("qaytarish"), route: .orders),
    ] }

    var body: some View {
        MBScreen {
            ScrollView {
                VStack(spacing: 12) {
                    profileCard
                    quickRow
                    menuCard
                    signOutCard
                    Spacer().frame(height: MB.metric.tabBarHeight + 26)
                }
                .padding(12)
            }
        }
        .task { await model.load() }
        .alert(L("hisobdan_chiqasizmi"), isPresented: $confirmSignOut) {
            Button(L("chiqish"), role: .destructive) {
                Task { await session.signOut() }
            }
            Button(L("bekor_qilish"), role: .cancel) {}
        } message: {
            Text(L("savat_va_sevimlilar_hisobingizda_saqlanadi"))
        }
    }

    private var profileCard: some View {
        MBCard {
            HStack(spacing: 14) {
                MBIcon("user", size: 26, tint: MB.color.icon)
                    .frame(width: 58, height: 58)
                    .background(MB.color.fill)
                    .clipShape(Circle())
                VStack(alignment: .leading, spacing: 2) {
                    Text(displayName).mbFont(MB.type.title3).foregroundStyle(MB.color.ink)
                    Text(Format.phone(model.overview?.user.phone ?? ""))
                        .mbFont(MB.type.bodySmall)
                        .foregroundStyle(MB.color.textTertiary)
                }
                Spacer()
                Button(L("tahrirlash")) { router.push(.personal) }
                    .mbFont(MB.type.label)
                    .foregroundStyle(MB.color.accent)
            }
        }
    }

    private var displayName: String {
        let name = model.overview?.user.fullName ?? ""
        return name.isEmpty ? L("ismingizni_kiriting") : name
    }

    private var quickRow: some View {
        HStack(spacing: 10) {
            ForEach(quickActions) { action in
                Button {
                    router.push(action.route)
                } label: {
                    VStack(spacing: 8) {
                        MBIcon(action.glyph, size: 22)
                        Text(action.label).mbFont(MB.type.micro)
                            .foregroundStyle(MB.color.textSecondary)
                            .lineLimit(1)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(MB.color.surface)
                    .clipShape(RoundedRectangle(cornerRadius: MB.metric.radiusXXL, style: .continuous))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var menuCard: some View {
        MBCard(padding: 6) {
            let rows: [(String, String, String, Route)] = [
                ("card", L("tolov_kartalari"), LPlural("n_items", count: model.overview?.cardsCount ?? 0,
                        "\(model.overview?.cardsCount ?? 0)"), .cards),
                ("pin", L("manzillarim"), LPlural("n_items", count: model.overview?.addressesCount ?? 0,
                        "\(model.overview?.addressesCount ?? 0)"), .addresses),
                ("star", L("sharhlarim"), LPlural("n_items", count: model.overview?.reviewsCount ?? 0,
                        "\(model.overview?.reviewsCount ?? 0)"), .myReviews),
                ("bell", L("bildirishnomalar"), unreadLabel, .notifications),
                ("gear", L("sozlamalar"), "", .settings),
            ]
            ForEach(Array(rows.enumerated()), id: \.offset) { offset, row in
                MBListRow(
                    row.1,
                    glyph: row.0,
                    meta: row.2.isEmpty ? nil : row.2
                ) {
                    router.push(row.3)
                }
                .padding(.horizontal, 10)
                if offset != rows.count - 1 { MBDivider(inset: 60) }
            }
        }
    }

    private var unreadLabel: String {
        let count = model.overview?.unreadNotifications ?? 0
        return count > 0 ? L("n_yangi", "\(count)") : ""
    }

    private var signOutCard: some View {
        MBCard(padding: 6) {
            MBListRow(
                L("hisobdan_chiqish"),
                glyph: "ret",
                showChevron: false,
                tint: MB.color.danger
            ) {
                confirmSignOut = true
            }
            .padding(.horizontal, 10)
        }
    }
}
