import SwiftUI

/// Screen 45 — Yordam markazi.
struct HelpView: View {
    @Environment(Router.self) var router
    @State var model = ContentModel()
    @State var expanded: Int?

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Yordam markazi", onBack: { router.pop() })
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        MBCard(padding: 6) {
                            MBListRow(
                                "Qo'ng'iroq qilish",
                                glyph: "headset",
                                subtitle: model.support["hours"],
                                meta: model.support["phone"]
                            )
                            .padding(.horizontal, 10)
                            MBDivider(inset: 60)
                            MBListRow(
                                "Telegram orqali yozish",
                                glyph: "phone",
                                subtitle: "Odatda 5 daqiqada javob beramiz"
                            )
                            .padding(.horizontal, 10)
                        }

                        Text("Ko'p so'raladigan savollar")
                            .mbFont(MB.type.captionBold)
                            .foregroundStyle(MB.color.textSecondary)
                            .padding(.leading, 6)

                        MBCard(padding: 6) {
                            ForEach(Array(model.faq.enumerated()), id: \.element.id) { offset, item in
                                VStack(alignment: .leading, spacing: 0) {
                                    HStack {
                                        Text(item.question).mbFont(MB.type.bodyBold)
                                            .foregroundStyle(MB.color.ink)
                                            .multilineTextAlignment(.leading)
                                        Spacer()
                                        Text(expanded == item.id ? "−" : "+")
                                            .mbFont(MB.type.title3)
                                            .foregroundStyle(MB.color.hairlineStrong)
                                    }
                                    if expanded == item.id {
                                        Spacer().frame(height: 8)
                                        Text(item.answer).mbFont(MB.type.bodySmall)
                                            .foregroundStyle(MB.color.textSecondary)
                                    }
                                }
                                .padding(.horizontal, 10)
                                .padding(.vertical, 14)
                                .contentShape(Rectangle())
                                .onTapGesture {
                                    withAnimation { expanded = expanded == item.id ? nil : item.id }
                                }
                                if offset != model.faq.count - 1 { MBDivider() }
                            }
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}

/// Screen 46 — Shartlar va maxfiylik.
struct LegalView: View {
    @Environment(Router.self) var router
    @State var model = ContentModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar("Shartlar va maxfiylik", onBack: { router.pop() })
                ScrollView {
                    MBCard(padding: 6) {
                        ForEach(Array(model.docs.enumerated()), id: \.element.id) { offset, doc in
                            MBListRow(
                                doc.title,
                                glyph: doc.icon,
                                subtitle: doc.meta.isEmpty ? nil : doc.meta
                            ) {
                                router.push(.legalDoc(slug: doc.slug))
                            }
                            .padding(.horizontal, 10)
                            if offset != model.docs.count - 1 { MBDivider(inset: 60) }
                        }
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.load() }
    }
}

/// One legal document. Also used as a sheet from the sign-in screen, where
/// there is no router, so the back button is optional.
struct LegalDocView: View {
    let slug: String

    @Environment(Router.self) var router: Router?
    @Environment(\.dismiss) var dismiss
    @State var model = ContentModel()

    var body: some View {
        MBScreen {
            VStack(spacing: 0) {
                MBTopBar(model.doc?.title ?? "Hujjat", onBack: {
                    if let router { router.pop() } else { dismiss() }
                })
                ScrollView {
                    MBCard {
                        Text(model.doc?.meta ?? "").mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.icon)
                        Spacer().frame(height: 12)
                        Text(model.doc?.body ?? "")
                            .mbFont(MB.type.bodySmall)
                            .foregroundStyle(MB.color.inkSoft)
                    }
                    .padding(12)
                }
            }
        }
        .navigationBarBackButtonHidden()
        .task { await model.loadDoc(slug: slug) }
    }
}
