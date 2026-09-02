import SwiftUI

/// One block of a page, fading up and rising into place — and, when the page
/// leaves, sinking back the way it came.
///
/// `index` is the block's place in the running order; the entrance is staggered
/// by it so the page assembles from the top down rather than flashing in at
/// once, and the exit is staggered against it so the page comes apart from the
/// bottom up. The Android client does the same thing in `MbReveal`.
struct MBReveal: ViewModifier {
    /// Place in the running order.
    let index: Int

    /// True once the page has been asked to leave.
    var leaving: Bool = false

    /// How far the block travels as it fades. Zero for a block that runs to the
    /// top of the screen — a photograph under the status bar cannot rise into
    /// place without showing a strip of bare page above it the whole way up.
    var rise: CGFloat = MBMotion.rise

    @State private var shown = false

    func body(content: Content) -> some View {
        let visible = shown && !leaving
        return content
            .opacity(visible ? 1 : 0)
            .offset(y: visible ? 0 : rise)
            .animation(
                leaving
                    ? .easeIn(duration: MBMotion.quick).delay(MBMotion.staggerOut(index))
                    : .easeOut(duration: MBMotion.emphasized).delay(MBMotion.stagger(index)),
                value: visible
            )
            .onAppear { shown = true }
    }
}

extension View {
    /// Fades and rises this block into place, `index` steps behind the first.
    func mbReveal(_ index: Int, leaving: Bool = false, rise: CGFloat = MBMotion.rise) -> some View {
        modifier(MBReveal(index: index, leaving: leaving, rise: rise))
    }
}

/// The press feedback a whole card makes: a dip under the finger.
///
/// A card is a large target and a tint over a large target is a weak signal, so
/// what answers the tap is the card itself moving. The same gesture the app's
/// buttons make, a shade shallower.
struct MBCardPressStyle: ButtonStyle {
    var pressedScale: CGFloat = 0.975

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? pressedScale : 1)
            .animation(
                configuration.isPressed ? MBMotion.easeQuick : MBMotion.ease,
                value: configuration.isPressed
            )
    }
}
