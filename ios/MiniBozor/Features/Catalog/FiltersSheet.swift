import SwiftUI

/// Screen 13. Edits a draft, so dismissing or clearing leaves the listing
/// untouched — only "Ko'rsatish" commits.
struct FiltersSheet: View {
    let filters: FiltersDTO?
    let initial: ProductQuery
    let resultCount: Int
    let onApply: (ProductQuery) -> Void

    @Environment(\.dismiss) var dismiss
    @State var draft: ProductQuery
    @State var minPrice: String
    @State var maxPrice: String

    init(
        filters: FiltersDTO?,
        initial: ProductQuery,
        resultCount: Int,
        onApply: @escaping (ProductQuery) -> Void
    ) {
        self.filters = filters
        self.initial = initial
        self.resultCount = resultCount
        self.onApply = onApply
        _draft = State(initialValue: initial)
        _minPrice = State(initialValue: initial.minPrice.map(String.init) ?? "")
        _maxPrice = State(initialValue: initial.maxPrice.map(String.init) ?? "")
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            MBDivider()
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    priceSection
                    brandSection
                    sizeSection
                    ratingSection
                    flagSection
                    Spacer().frame(height: 20)
                }
                .padding(.horizontal, 20)
            }
            MBDivider()
            MBBottomBar {
                MBPrimaryButton(
                    resultCount > 0
                        ? L("korsatish_n", Format.grouped(resultCount))
                        : L("qollash")
                ) {
                    draft.minPrice = Int(minPrice)
                    draft.maxPrice = Int(maxPrice)
                    onApply(draft)
                }
            }
        }
        .background(MB.color.surface)
    }

    private var header: some View {
        HStack {
            Text(L("filtrlar")).mbFont(MB.type.title2).foregroundStyle(MB.color.ink)
            Spacer()
            Button(L("tozalash")) {
                draft = draft.cleared()
                minPrice = ""
                maxPrice = ""
            }
            .mbFont(MB.type.label)
            .foregroundStyle(MB.color.accent)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
    }

    private var priceSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Spacer().frame(height: 16)
            SectionHeader(title: L("narx"), subtitle: L("som"))
            HStack(spacing: 12) {
                MBTextField(
                    placeholder: filters.map { Format.grouped($0.priceMin) } ?? "0",
                    text: $minPrice,
                    keyboard: .numberPad
                )
                MBTextField(
                    placeholder: filters.map { Format.grouped($0.priceMax) } ?? "∞",
                    text: $maxPrice,
                    keyboard: .numberPad
                )
            }
        }
    }

    @ViewBuilder
    private var brandSection: some View {
        if let brands = filters?.brands, !brands.isEmpty {
            Spacer().frame(height: 22)
            SectionHeader(title: L("brend"))
            ForEach(brands) { brand in
                MBCheckRow(
                    label: brand.name,
                    count: brand.productCount > 0 ? "\(brand.productCount)" : nil,
                    checked: draft.brands.contains(brand.slug),
                    onToggle: { draft.toggleBrand(brand.slug) }
                )
            }
        }
    }

    @ViewBuilder
    private var sizeSection: some View {
        if let sizes = filters?.sizes, !sizes.isEmpty {
            Spacer().frame(height: 22)
            SectionHeader(title: L("olcham"))
            Spacer().frame(height: 10)
            FlowLayout(spacing: 8) {
                ForEach(sizes, id: \.self) { size in
                    MBSizeChip(size, selected: draft.sizes.contains(size)) {
                        draft.toggleSize(size)
                    }
                }
            }
        }
    }

    private var ratingSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Spacer().frame(height: 22)
            SectionHeader(title: L("reyting"))
            FlowLayout(spacing: 8) {
                ForEach([4.5, 4.0], id: \.self) { value in
                    MBChip(L("rating_n_dan_yuqori", Format.rating(value)),
                           selected: draft.minRating == value) {
                        draft.minRating = draft.minRating == value ? nil : value
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var flagSection: some View {
        Spacer().frame(height: 22)
        SectionHeader(title: L("qoshimcha"))
        ForEach(filters?.flags ?? []) { flag in
            MBCheckRow(
                label: flag.label,
                subtitle: flag.subtitle.isEmpty ? nil : flag.subtitle,
                count: flag.count > 0 ? "\(flag.count)" : nil,
                checked: draft.flags[flag.key] == true,
                onToggle: { draft.toggleFlag(flag.key) }
            )
        }
        // Last in the section, and the only row here that is about the listing
        // rather than about the products: everything else narrows what is
        // shown, and this one widens it.
        MBCheckRow(
            label: L("tugaganlarni_korsatish"),
            subtitle: L("tugaganlar_odatda_royxatda_korinmaydi"),
            count: nil,
            checked: draft.showSoldOut,
            onToggle: { draft.showSoldOut.toggle() }
        )
    }
}
