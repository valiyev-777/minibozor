import SwiftUI

/// The photograph, on its own, as large as the screen allows.
///
/// The page's own frame is square and shares the screen with a price panel and a
/// bar of buttons, so a photograph there is always partly a thumbnail — fine for
/// recognising the thing, not enough for looking at it. This is the looking: the
/// picture as large as the screen allows, on the pale ground it is drawn on
/// everywhere else, with black around it and nothing else on the screen, and
/// double tap or pinch to go closer.
///
/// It does not appear; it grows out of the picture that was tapped. `origin` is
/// where that picture sits on the screen, and the whole view is scaled and
/// offset to coincide with it on the first frame, then animated out to full size
/// while the black ground fades up under it. Closing runs the same path
/// backwards — by the button, by the swipe, or by a tap anywhere — so the
/// picture always ends up where the customer left it rather than sliding off an
/// edge.
///
/// The plate matters. Half the catalogue is cut out against transparency, so a
/// picture drawn straight onto black loses the pale studio backdrop it has on
/// the page and the shoe reads as having had its background deleted. The same
/// component as the page uses, at the same 1:1 the whole catalogue is shot at,
/// so what opens is what was tapped; the black is the room around the picture
/// rather than its backdrop.
struct HeroViewerView: View {
    let images: [String]
    let initialPage: Int
    /// Where the picture sits on the screen, in global coordinates.
    let origin: CGRect
    let onClose: () -> Void

    @State private var page: Int
    /// 0 = sitting in the page where it was tapped, 1 = filling the screen.
    @State private var flight: CGFloat = 0
    @State private var zoom: CGFloat = 1
    @State private var zoomBase: CGFloat = 1
    @State private var pan: CGSize = .zero
    @State private var panBase: CGSize = .zero
    /// How far the picture has been dragged towards being put down.
    @State private var thrown: CGSize = .zero
    @State private var closing = false

    /// How far in a double tap takes the picture.
    private let zoomedInScale: CGFloat = 2.6
    /// The most a pinch is allowed to reach.
    private let maxZoom: CGFloat = 5
    /// Drag the picture this far and letting go closes the view.
    private let dismissDistance: CGFloat = 120

    init(images: [String], initialPage: Int, origin: CGRect, onClose: @escaping () -> Void) {
        self.images = images
        self.initialPage = initialPage
        self.origin = origin
        self.onClose = onClose
        _page = State(initialValue: min(max(initialPage, 0), max(images.count - 1, 0)))
    }

    private var zoomedIn: Bool { zoom > 1.01 }

    /// 0 while the picture sits still, 1 once it is a dismissal away.
    private var thrownProgress: CGFloat {
        let distance = sqrt(thrown.width * thrown.width + thrown.height * thrown.height)
        return min(max(distance / dismissDistance, 0), 1)
    }

    var body: some View {
        GeometryReader { geometry in
            // The two rectangles the flight runs between, worked out where the
            // screen's own size is known. Fitted to the screen a catalogue
            // photograph is a square as wide as the narrower side of the
            // display, so the flight is one scale and one offset — and at the
            // top of a page, where the frame is already full width, it comes out
            // as pure movement with no scaling at all.
            let frame = geometry.frame(in: .global)
            let side = min(frame.width, frame.height)
            let fromScale = side > 0 ? min(max(origin.width / side, 0.05), 4) : 1
            let fromX = origin.midX - frame.midX
            let fromY = origin.midY - frame.midY
            let put = thrownProgress
            // Shrinks a little as it is thrown, so the picture reads as being
            // put down rather than sliding off a table.
            let scale = (fromScale + (1 - fromScale) * flight) * (1 - put * 0.12)

            ZStack {
                Color.black
                    .opacity(Double(flight) * (1 - Double(put) * 0.7))
                    .ignoresSafeArea()

                pager(side: side)
                    .scaleEffect(scale)
                    .offset(
                        x: fromX * (1 - flight) + thrown.width,
                        y: fromY * (1 - flight) + thrown.height
                    )
                    // Only while it has somewhere to fly from: without an origin
                    // the picture simply fades up at full size.
                    .opacity(origin.width > 0 ? 1 : Double(flight))

                chrome.opacity(Double(flight) * (1 - Double(put)))
            }
            .frame(width: frame.width, height: frame.height)
            // The dismissal drag. Off while the picture is zoomed — those drags
            // move the picture — and simultaneous with the pager, which keeps
            // sideways for itself.
            .simultaneousGesture(dismissDrag, including: zoomedIn ? .none : .all)
        }
        .ignoresSafeArea()
        .onAppear { withAnimation(MBMotion.flight) { flight = 1 } }
    }

    // MARK: - The picture

    private func pager(side: CGFloat) -> some View {
        TabView(selection: $page) {
            ForEach(Array(images.enumerated()), id: \.offset) { offset, url in
                plate(url: url, side: side, live: offset == page).tag(offset)
            }
        }
        .tabViewStyle(.page(indexDisplayMode: .never))
        // A new page starts at its natural size. Carrying the zoom across meant
        // swiping to the next photograph and landing halfway into a corner of it.
        .onChange(of: page) { _, _ in
            zoom = 1
            zoomBase = 1
            pan = .zero
            panBase = .zero
        }
    }

    private func plate(url: String, side: CGFloat, live: Bool) -> some View {
        MBProductImage(url: url, cornerRadius: 0)
            .frame(width: side, height: side)
            // The zoom rides on the plate, not on the picture inside it, so
            // going closer takes the backdrop with it instead of growing the
            // product out of its own frame. Only the live page follows it; the
            // neighbours stay at their natural size behind the fold.
            .scaleEffect(live ? zoom : 1)
            .offset(live ? pan : .zero)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .contentShape(Rectangle())
            // Declared before the single tap, so a double tap is not read as
            // two closes.
            .onTapGesture(count: 2) { toggleZoom() }
            .onTapGesture { close() }
            .gesture(magnify, including: live ? .all : .none)
            .highPriorityGesture(panDrag, including: live && zoomedIn ? .all : .none)
    }

    // MARK: - The bar over it

    private var chrome: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                if images.count > 1 {
                    // Which of how many, in words rather than dots: on a black
                    // screen with no page under it, "2 / 5" is the only thing
                    // that says the swipe has anywhere to go.
                    Text("\(page + 1) / \(images.count)")
                        .mbFont(MB.type.label)
                        .foregroundStyle(.white.opacity(0.85))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 7)
                        .background(.white.opacity(0.14))
                        .clipShape(Capsule())
                }
                Spacer(minLength: 0)
                Button { close() } label: {
                    MBIcon("close", size: 20, tint: .white, lineWidth: 2)
                        .frame(width: 44, height: 44)
                        .background(.white.opacity(0.14))
                        .clipShape(Circle())
                        .contentShape(Circle())
                }
                .buttonStyle(MBCardPressStyle(pressedScale: 0.9))
            }
            .padding(.horizontal, 14)
            .padding(.top, ProductHero.statusBarInset + 8)
            Spacer(minLength: 0)
        }
    }

    // MARK: - Gestures

    private var magnify: some Gesture {
        MagnifyGesture()
            .onChanged { value in
                zoom = min(max(zoomBase * value.magnification, 1), maxZoom)
                if zoom <= 1.01 { pan = .zero }
            }
            .onEnded { _ in
                zoomBase = zoom
                panBase = pan
            }
    }

    private var panDrag: some Gesture {
        DragGesture()
            .onChanged { value in
                pan = CGSize(
                    width: panBase.width + value.translation.width,
                    height: panBase.height + value.translation.height
                )
            }
            .onEnded { _ in panBase = pan }
    }

    private var dismissDrag: some Gesture {
        DragGesture(minimumDistance: 12)
            .onChanged { value in
                // Vertical only: sideways belongs to the pager. A single
                // photograph has nowhere to page to, so it may go either way.
                if images.count > 1
                    && abs(value.translation.width) > abs(value.translation.height) {
                    return
                }
                thrown = images.count > 1
                    ? CGSize(width: 0, height: value.translation.height)
                    : value.translation
            }
            .onEnded { _ in
                if thrownProgress >= 1 {
                    close()
                } else {
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        thrown = .zero
                    }
                }
            }
    }

    // MARK: - Opening and closing

    private func toggleZoom() {
        withAnimation(MBMotion.easeQuick) {
            if zoomedIn {
                zoom = 1
                pan = .zero
            } else {
                zoom = zoomedInScale
                pan = .zero
            }
        }
        zoomBase = zoom
        panBase = pan
    }

    /// The reverse flight: home to where it came from, then gone.
    private func close() {
        guard !closing else { return }
        closing = true
        // Zoom and pan unwind with it, so the picture lands at the size the page
        // draws it rather than shrinking into its own corner.
        zoom = 1
        zoomBase = 1
        pan = .zero
        panBase = .zero
        withAnimation(MBMotion.flightBack, completionCriteria: .removed) {
            flight = 0
            thrown = .zero
        } completion: {
            onClose()
        }
    }
}
