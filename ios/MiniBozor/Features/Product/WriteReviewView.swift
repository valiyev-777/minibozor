import SwiftUI
import Observation

@Observable
final class WriteReviewModel {
    var rating = 5
    var text = ""
    var tags: [String] = []
    var selectedTags: Set<String> = []
    var submitting = false
    var errorMessage: String?
    var done = false

    private let catalog = CatalogRepository()

    @MainActor
    func loadTags() async {
        if case .success(let values) = await catalog.reviewTags() { tags = values }
    }

    @MainActor
    func toggle(_ tag: String) {
        if selectedTags.contains(tag) { selectedTags.remove(tag) } else { selectedTags.insert(tag) }
    }

    @MainActor
    func submit(productId: Int, orderItemId: Int?) async {
        guard !submitting else { return }
        submitting = true
        errorMessage = nil

        let outcome = await catalog.createReview(
            productId: productId,
            body: ReviewCreateRequest(
                rating: rating,
                text: text.trimmingCharacters(in: .whitespacesAndNewlines),
                tags: Array(selectedTags),
                photos: [],
                variantLabel: "",
                orderItemId: orderItemId
            )
        )
        submitting = false
        switch outcome {
        case .success: done = true
        case .failure(let message): errorMessage = message
        }
    }
}

/// Screen 16 — Sharh yozish.
struct WriteReviewView: View {
    let productId: Int
    let orderItemId: Int?

    @Environment(Router.self) var router
    @State var model = WriteReviewModel()

    private var ratingWords: [String] {
        ["", "Yomon", "O'rtacha", "Yaxshi", "Juda yaxshi", "Ajoyib"]
    }

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Sharh yozish", onBack: { router.pop() })
                ScrollView {
                    VStack(spacing: 12) {
                        MBCard {
                            Text("Mahsulotni qanday baholaysiz?")
                                .mbFont(MB.type.title3)
                                .foregroundStyle(MB.color.ink)
                                .frame(maxWidth: .infinity)
                                .multilineTextAlignment(.center)
                            Spacer().frame(height: 16)
                            HStack(spacing: 12) {
                                ForEach(1...5, id: \.self) { star in
                                    Button {
                                        model.rating = star
                                    } label: {
                                        Text("★")
                                            .font(.system(size: 32))
                                            .foregroundStyle(
                                                star <= model.rating ? MB.color.star : MB.color.divider
                                            )
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .frame(maxWidth: .infinity)
                            Spacer().frame(height: 10)
                            Text(ratingWords[model.rating])
                                .mbFont(MB.type.label)
                                .foregroundStyle(MB.color.textSecondary)
                                .frame(maxWidth: .infinity)
                                .multilineTextAlignment(.center)
                        }

                        if !model.tags.isEmpty {
                            MBCard {
                                SectionHeader(title: "Nimasi yoqdi?")
                                Spacer().frame(height: 12)
                                FlowLayout(spacing: 8) {
                                    ForEach(model.tags, id: \.self) { tag in
                                        MBChip(tag, selected: model.selectedTags.contains(tag)) {
                                            model.toggle(tag)
                                        }
                                    }
                                }
                            }
                        }

                        MBCard {
                            SectionHeader(title: "Fikringiz", subtitle: "ixtiyoriy")
                            Spacer().frame(height: 12)
                            MBTextField(
                                placeholder: "Sifati, o'lchami, yetkazish haqida yozing…",
                                text: Binding(get: { model.text }, set: { model.text = $0 }),
                                multiline: true,
                                minHeight: 120
                            )
                            if let error = model.errorMessage {
                                Spacer().frame(height: 10)
                                Text(error).mbFont(MB.type.caption).foregroundStyle(MB.color.danger)
                            }
                        }

                        Text("Sharh moderatsiyadan o'tgach e'lon qilinadi.")
                            .mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.textQuaternary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .safeAreaInset(edge: .bottom) {
            MBBottomBar {
                MBPrimaryButton("Yuborish", loading: model.submitting) {
                    Task { await model.submit(productId: productId, orderItemId: orderItemId) }
                }
            }
        }
        .task { await model.loadTags() }
        .onChange(of: model.done) { _, done in
            if done { router.pop() }
        }
    }
}
