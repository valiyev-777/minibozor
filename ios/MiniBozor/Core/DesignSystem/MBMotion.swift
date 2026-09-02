import SwiftUI

/// How long the app's own motion takes, and on what curve.
///
/// Three durations, not a number per call site. Everything the product page
/// animates sits between a fifth and a third of a second: under 0.2 s a
/// transition reads as a jump, and over 0.35 s the customer is waiting for the
/// interface to finish having an opinion. Anything that has to feel instant —
/// the press dip on a card — takes ``quick``; anything the eye follows across
/// the screen — a photograph opening, a panel rising into place — takes
/// ``emphasized``.
///
/// Springs are still the right answer where a control settles under a finger
/// (the chevrons, the pager dots). These are for the choreography, where a known
/// duration is what lets several things be staggered against each other. The
/// same three numbers are in the Android client's `MbMotion`, so the two apps
/// move at the same pace.
enum MBMotion {
    /// A press, a tint, a swap — fast enough to read as the touch itself.
    static let quick: Double = 0.20

    /// The default: a panel appearing, a bar taking something over.
    static let standard: Double = 0.28

    /// A photograph crossing the screen, or the page arriving.
    static let emphasized: Double = 0.34

    /// The gap between one block entering and the next.
    static let staggerStep: Double = 0.045

    /// Blocks past this many stop being delayed further.
    static let staggerCap = 4

    /// How far a block rises into place as it fades up.
    static let rise: CGFloat = 18

    /// Starts and stops on screen.
    static var ease: Animation { .easeInOut(duration: standard) }

    /// The same, for something that has to keep up with a finger.
    static var easeQuick: Animation { .easeInOut(duration: quick) }

    /// Arriving: quick off the mark, settles gently.
    static var arrive: Animation { .easeOut(duration: emphasized) }

    /// Leaving: gives way slowly, then goes.
    static var leave: Animation { .easeIn(duration: quick) }

    /// A photograph opening out of the page.
    static var flight: Animation { .easeInOut(duration: emphasized) }

    /// And going back into it.
    static var flightBack: Animation { .easeInOut(duration: standard) }

    /// The delay the `index`th block waits before entering.
    static func stagger(_ index: Int) -> Double {
        staggerStep * Double(min(max(index, 0), staggerCap))
    }

    /// The same, in reverse: the last block in leaves first.
    static func staggerOut(_ index: Int) -> Double {
        (staggerStep / 2) * Double(staggerCap - min(max(index, 0), staggerCap))
    }

    /// How long a page needs to clear itself before it may be navigated away.
    static var pageExit: Double { quick + (staggerStep / 2) * Double(staggerCap) }
}
