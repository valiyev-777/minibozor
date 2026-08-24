import SwiftUI
import Observation

@Observable
final class SearchModel {
    var query = ""
    var recent: [String] = []
    var popular: [String] = []
    var suggestions: [SuggestionDTO] = []

    private let catalog = CatalogRepository()
    private var suggestTask: Task<Void, Never>?

    @MainActor
    func loadLanding() async {
        if case .success(let landing) = await catalog.searchLanding() {
            recent = landing.recent
            popular = landing.popular
        }
    }

    /// Debounced so typing does not fire a request per keystroke.
    @MainActor
    func queryChanged(_ text: String) {
        query = text
        suggestTask?.cancel()
        guard text.count >= 2 else {
            suggestions = []
            return
        }
        suggestTask = Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            if case .success(let items) = await catalog.suggest(text) {
                suggestions = items
            }
        }
    }

    @MainActor
    func remember(_ text: String) async {
        await catalog.rememberSearch(text)
        await loadLanding()
    }

    @MainActor
    func clearHistory() async {
        await catalog.clearSearchHistory()
        recent = []
    }
}

/// Screen 08 — Qidiruv.
struct SearchView: View {
    @Environment(Router.self) var router
    @Environment(\.dismiss) var dismiss

    @State var model = SearchModel()

    var body: some View {
        MBScreen(background: MB.color.surface) {
            VStack(spacing: 0) {
                HStack(spacing: 12) {
                    MBSearchField(
                        text: Binding(
                            get: { model.query },
                            set: { model.queryChanged($0) }
                        ),
                        onSubmit: { submit(model.query) }
                    )
                    Button("Bekor") { router.pop() }
                        .mbFont(MB.type.label)
                        .foregroundStyle(MB.color.accent)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)

                if model.suggestions.isEmpty {
                    landing
                } else {
                    suggestionList
                }
                Spacer(minLength: 0)
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.loadLanding() }
    }

    private var suggestionList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(model.suggestions) { item in
                    Button {
                        router.push(.product(id: item.productId))
                    } label: {
                        HStack(spacing: 12) {
                            MBProductImage(url: item.imageUrl, cornerRadius: MB.metric.radiusM)
                                .frame(width: 44, height: 44)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.title).mbFont(MB.type.bodySmall)
                                    .foregroundStyle(MB.color.ink).lineLimit(1)
                                Text(Format.sum(item.price)).mbFont(MB.type.meta)
                                    .foregroundStyle(MB.color.icon)
                            }
                            Spacer()
                            MBIcon("search", size: 14, tint: MB.color.hairlineStrong)
                        }
                        .padding(.vertical, 10)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 20)
        }
    }

    private var landing: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if !model.recent.isEmpty {
                    Spacer().frame(height: 18)
                    SectionHeader(title: "Oxirgi qidiruvlar", actionLabel: "Tozalash") {
                        Task { await model.clearHistory() }
                    }
                    Spacer().frame(height: 12)
                    ForEach(model.recent, id: \.self) { text in
                        Button {
                            submit(text)
                        } label: {
                            HStack(spacing: 12) {
                                MBIcon("clock", size: 16, tint: MB.color.icon)
                                Text(text).mbFont(MB.type.bodySmall).foregroundStyle(MB.color.ink)
                                Spacer()
                                Text("↖").mbFont(MB.type.caption)
                                    .foregroundStyle(MB.color.hairlineStrong)
                            }
                            .padding(.vertical, 11)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }

                if !model.popular.isEmpty {
                    Spacer().frame(height: 22)
                    SectionHeader(title: "Ommabop so'rovlar")
                    Spacer().frame(height: 12)
                    FlowLayout(spacing: 8) {
                        ForEach(model.popular, id: \.self) { text in
                            MBChip(text, selected: false) { submit(text) }
                        }
                    }
                }
            }
            .padding(.horizontal, 20)
        }
    }

    private func submit(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        Task { await model.remember(trimmed) }
        router.push(.listing(category: nil, query: trimmed, title: trimmed))
    }
}
