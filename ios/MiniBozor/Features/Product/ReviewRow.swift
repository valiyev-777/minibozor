import SwiftUI

/// One review: initials avatar, name, stars, variant, body, photos and likes.
struct ReviewRow: View {
    let review: ReviewDTO
    let onLike: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                Text(review.authorInitials)
                    .mbFont(MB.type.micro)
                    .foregroundStyle(MB.color.textSecondary)
                    .frame(width: 36, height: 36)
                    .background(MB.color.fill)
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(review.authorName).mbFont(MB.type.bodyBold).foregroundStyle(MB.color.ink)
                    HStack(spacing: 6) {
                        MBStars(rating: review.rating)
                        if let date = UzDate.parseDateTime(review.createdAt) {
                            Text(UzDate.relative(date)).mbFont(MB.type.meta)
                                .foregroundStyle(MB.color.icon)
                        }
                        if !review.variantLabel.isEmpty {
                            Text("·").mbFont(MB.type.meta).foregroundStyle(MB.color.hairlineStrong)
                            Text(review.variantLabel).mbFont(MB.type.meta)
                                .foregroundStyle(MB.color.icon)
                        }
                    }
                }
                Spacer(minLength: 0)
            }

            if !review.text.isEmpty {
                Spacer().frame(height: 8)
                Text(review.text).mbFont(MB.type.bodySmall).foregroundStyle(MB.color.inkSoft)
            }

            if !review.tags.isEmpty {
                Spacer().frame(height: 8)
                FlowLayout(spacing: 6, lineSpacing: 6) {
                    ForEach(review.tags, id: \.self) { tag in
                        Text(tag)
                            .mbFont(MB.type.micro)
                            .foregroundStyle(MB.color.textSecondary)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(MB.color.fill)
                            .clipShape(Capsule())
                    }
                }
            }

            if !review.photos.isEmpty {
                Spacer().frame(height: 10)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(review.photos, id: \.self) { photo in
                            MBProductImage(url: photo, cornerRadius: MB.metric.radiusL)
                                .frame(width: 72, height: 72)
                        }
                    }
                }
            }

            if let onLike {
                Spacer().frame(height: 10)
                Button(action: onLike) {
                    HStack(spacing: 6) {
                        MBIcon(
                            "heart",
                            size: 14,
                            tint: review.likedByMe ? MB.color.danger : MB.color.icon
                        )
                        Text("\(review.likes)").mbFont(MB.type.caption)
                            .foregroundStyle(MB.color.icon)
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
