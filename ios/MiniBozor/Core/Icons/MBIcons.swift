import SwiftUI

/// The design's icon set, as SVG path data on a 24x24 grid.
///
/// Every glyph is drawn as a 1.6-weight round-capped stroke, exactly as the
/// design does, so a 20 pt icon and a 44 pt icon stay identical to the source.
///
/// Generated from `design/icons.json` — edit that file and regenerate rather
/// than hand-editing path data here.
enum MBIcons {
    static let glyphs: [String: [String]] = [
        "food": [
            "M4.6 12.8h14.8a7.4 7.4 0 0 1-14.8 0z",
            "M6.4 9.6c0-1.9 2.5-3.4 5.6-3.4s5.6 1.5 5.6 3.4",
            "M5 20.4h14",
        ],
        "globe": [
            "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
            "M3.6 12h16.8",
            "M12 3.5c2.3 2.3 3.5 5.1 3.5 8.5S14.3 18.2 12 20.5C9.7 18.2 8.5 15.4 8.5 12S9.7 5.8 12 3.5z",
        ],
        "plant": [
            "M12 21v-7.2",
            "M12 13.8c-3.4 0-5.2-2-5.2-5.2 3.4 0 5.2 2 5.2 5.2z",
            "M12 13.8c3.4 0 5.2-2 5.2-5.2-3.4 0-5.2 2-5.2 5.2z",
        ],
        "bottle": [
            "M9 8.4h6v10.8a1.8 1.8 0 0 1-1.8 1.8h-2.4A1.8 1.8 0 0 1 9 19.2z",
            "M10.6 8.4V5.6h2.8v2.8",
            "M9.4 12.6h5.2",
        ],
        "shirt": [
            "M8.2 4 4.6 6.4 6 9.8l2.2-1v11.4h7.6V8.8l2.2 1 1.4-3.4L15.8 4",
            "M8.2 4c0 2 1.7 2.9 3.8 2.9S15.8 6 15.8 4",
        ],
        "car": [
            "M3.6 15.4h16.8v-2.9l-1.7-4.2A2 2 0 0 0 16.8 7H7.2a2 2 0 0 0-1.9 1.3l-1.7 4.2z",
            "M7 18.4v-3M17 18.4v-3",
        ],
        "phone": [
            "M7.6 3.6h8.8a1.5 1.5 0 0 1 1.5 1.5v13.8a1.5 1.5 0 0 1-1.5 1.5H7.6a1.5 1.5 0 0 1-1.5-1.5V5.1a1.5 1.5 0 0 1 1.5-1.5z",
            "M10.6 17.4h2.8",
        ],
        "washer": [
            "M5.6 3.6h12.8a1 1 0 0 1 1 1v14.8a1 1 0 0 1-1 1H5.6a1 1 0 0 1-1-1V4.6a1 1 0 0 1 1-1z",
            "M12 9.4a4.1 4.1 0 1 0 0 8.2 4.1 4.1 0 0 0 0-8.2z",
            "M8 6.6h1.6",
        ],
        "gift": [
            "M4.4 9.6h15.2v9.8a1 1 0 0 1-1 1H5.4a1 1 0 0 1-1-1z",
            "M3.6 6.2h16.8v3.4H3.6z",
            "M12 6.2v14.2",
        ],
        "backpack": [
            "M6.2 9.8A4 4 0 0 1 10.2 5.8h3.6a4 4 0 0 1 4 4v8.8a1.5 1.5 0 0 1-1.5 1.5H7.7a1.5 1.5 0 0 1-1.5-1.5z",
            "M9.6 9.4V6.6a2.4 2.4 0 0 1 4.8 0v2.8",
            "M9.4 14.6h5.2",
        ],
        "lipstick": [
            "M9.6 10.2h4.8v10.4H9.6z",
            "M10.6 10.2V6.4a1.6 1.6 0 0 1 3.2 0v3.8",
        ],
        "basket": [
            "M4.2 9.6h15.6l-1.6 9.1a1.6 1.6 0 0 1-1.6 1.3H7.4a1.6 1.6 0 0 1-1.6-1.3z",
            "M8.6 9.6 10 4.6M15.4 9.6 14 4.6",
        ],
        "ball": [
            "M12 3.5a8.5 8.5 0 1 0 0 17 8.5 8.5 0 0 0 0-17z",
            "M12 3.5v17",
            "M3.5 12h17",
        ],
        "card": [
            "M3.6 6.4h16.8v11.2H3.6z",
            "M3.6 10.4h16.8",
        ],
        "pin": [
            "M12 20.8s6.8-5.4 6.8-10.8a6.8 6.8 0 1 0-13.6 0c0 5.4 6.8 10.8 6.8 10.8z",
            "M12 12.4a2.4 2.4 0 1 0 0-4.8 2.4 2.4 0 0 0 0 4.8z",
        ],
        "bell": [
            "M6.4 17.4h11.2l-1.4-2.1v-4.1a4.2 4.2 0 0 0-8.4 0v4.1z",
            "M10.4 20h3.2",
        ],
        "star": [
            "M12 4.2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z",
        ],
        "gear": [
            "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
            "M12 3.6v2.2M12 18.2v2.2M5.2 7.8l1.9 1.1M16.9 15.1l1.9 1.1M5.2 16.2l1.9-1.1M16.9 8.9l1.9-1.1",
        ],
        "box": [
            "M4.2 8.4 12 4.4l7.8 4v7.2L12 19.6l-7.8-4z",
            "M4.2 8.4 12 12.4l7.8-4",
            "M12 12.4v7.2",
        ],
        "heart": [
            "M12 20s-7-4.4-7-9.4A4.1 4.1 0 0 1 12 7.8a4.1 4.1 0 0 1 7 2.8c0 5-7 9.4-7 9.4z",
        ],
        "ticket": [
            "M4.2 8.4h15.6v3.2a2 2 0 0 0 0 4v3.2H4.2v-3.2a2 2 0 0 0 0-4z",
            "M12 8.4v11.2",
        ],
        "ret": [
            "M9.2 6.4 5.6 10l3.6 3.6",
            "M5.6 10h8.8a4.6 4.6 0 0 1 0 9.2h-2.8",
        ],
        "headset": [
            "M5.2 15v-3a6.8 6.8 0 0 1 13.6 0v3",
            "M5.2 14.4h2.6v5.2H6.2a1 1 0 0 1-1-1z",
            "M18.8 14.4h-2.6v5.2h1.6a1 1 0 0 0 1-1z",
        ],
        "clock": [
            "M12 3.6a8.4 8.4 0 1 0 0 16.8 8.4 8.4 0 0 0 0-16.8z",
            "M12 7.8v4.4l3 1.8",
        ],
        "search": [
            "M11 4.6a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z",
            "m16 16 4 4",
        ],
        "sofa": [
            "M4.6 12.6a1.8 1.8 0 0 1 3.6 0v2.4h7.6v-2.4a1.8 1.8 0 0 1 3.6 0v5.4H4.6z",
            "M6.6 12.4V8.6a2 2 0 0 1 2-2h6.8a2 2 0 0 1 2 2v3.8",
        ],
        "home": [
            "M3 10.2 12 3.4l9 6.8V20a1 1 0 0 1-1 1h-5v-6H10v6H4a1 1 0 0 1-1-1z",
        ],
        "cart": [
            "M2.8 4.4h2.4l3.2 10h10.6",
            "M6.3 7.8h14.5l-1.8 6.6",
            "M10.2 17.4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z",
            "M17.2 17.4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z",
        ],
        "trash": [
            "M4.6 7.2h14.8M9.8 7.2V5.6a1.4 1.4 0 0 1 1.4-1.4h1.6a1.4 1.4 0 0 1 1.4 1.4v1.6",
            "M6.8 7.2h10.4l-1 11.6a1.6 1.6 0 0 1-1.6 1.4H9.4a1.6 1.6 0 0 1-1.6-1.4z",
            "M10.4 10.8v5.8M13.6 10.8v5.8",
        ],
        "user": [
            "M12 4.8a3.6 3.6 0 1 0 0 7.2 3.6 3.6 0 0 0 0-7.2z",
            "M4.6 20.4c1-3.6 3.9-5.4 7.4-5.4s6.4 1.8 7.4 5.4",
        ],
        "filter": [
            "M4 7h4M13 7h7",
            "M4 12h9M18 12h2",
            "M4 17h3M12 17h8",
            "M10.5 5.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z",
            "M15.5 10.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z",
            "M9.5 15.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z",
        ],
        "grid": [
            "M3.4 5.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z",
            "M13.4 5.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2h-2.8a2.2 2.2 0 0 1-2.2-2.2zM3.4 15.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2z",
            "M13.4 15.6a2.2 2.2 0 0 1 2.2-2.2h2.8a2.2 2.2 0 0 1 2.2 2.2v2.8a2.2 2.2 0 0 1-2.2 2.2h-2.8a2.2 2.2 0 0 1-2.2-2.2z",
        ],
        "arrow-left": [
            "M14.5 5.5 8 12l6.5 6.5",
        ],
        "chevron-down": [
            "M7 10.2l5 5 5-5",
        ],
        "chevron-right": [
            "M10 7l5 5-5 5",
        ],
        "share": [
            "M12 4v10.4",
            "M8.4 7.6 12 4l3.6 3.6",
            "M5.6 13v5.4a1.8 1.8 0 0 0 1.8 1.8h9.2a1.8 1.8 0 0 0 1.8-1.8V13",
        ],
        "close": [
            "M6.6 6.6l10.8 10.8",
            "M17.4 6.6 6.6 17.4",
        ],
    ]

    static func paths(for name: String) -> [String] {
        glyphs[name] ?? glyphs["box"] ?? []
    }
}

/// One glyph, scaled from the 24x24 authoring grid to `size`.
struct MBIcon: View {
    let name: String
    var size: CGFloat = 20
    var tint: Color = MB.color.ink
    var lineWidth: CGFloat = 1.6

    var body: some View {
        GlyphShape(name: name)
            .stroke(
                tint,
                style: StrokeStyle(lineWidth: lineWidth, lineCap: .round, lineJoin: .round)
            )
            .frame(width: size, height: size)
    }

    init(_ name: String, size: CGFloat = 20, tint: Color = MB.color.ink, lineWidth: CGFloat = 1.6) {
        self.name = name
        self.size = size
        self.tint = tint
        self.lineWidth = lineWidth
    }
}

private struct GlyphShape: Shape {
    let name: String

    func path(in rect: CGRect) -> Path {
        // The stroke widens the drawn area, so scale by the 24-unit grid and let
        // SwiftUI's stroke bleed sit inside the frame the same way Android does.
        let scale = min(rect.width, rect.height) / 24
        var transform = CGAffineTransform(scaleX: scale, y: scale)

        var combined = Path()
        for data in MBIcons.paths(for: name) {
            let cgPath = SVGPath.cgPath(from: data)
            if let scaled = cgPath.copy(using: &transform) {
                combined.addPath(Path(scaled))
            }
        }
        return combined
    }
}
