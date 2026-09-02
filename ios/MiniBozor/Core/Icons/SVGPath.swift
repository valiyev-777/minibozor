import CoreGraphics
import Foundation

/// Minimal SVG path-data parser.
///
/// The icon set is authored as SVG path strings so Android and iOS render the
/// exact same geometry from `design/icons.json`. SwiftUI has no path-data
/// parser, so this covers the subset the design actually uses: M/m, L/l, H/h,
/// V/v, C/c, S/s, A/a and Z/z.
enum SVGPath {

    static func cgPath(from data: String) -> CGPath {
        let path = CGMutablePath()
        var scanner = TokenScanner(data)

        var current = CGPoint.zero
        var subpathStart = CGPoint.zero
        var lastControl: CGPoint?
        var command: Character = "M"

        while let next = scanner.nextCommandOrNumberPrefix() {
            if let letter = next.letter {
                command = letter
            }
            // A repeated coordinate set after M continues as an implicit L.
            else if command == "M" {
                command = "L"
            } else if command == "m" {
                command = "l"
            }

            switch command {
            case "M", "m":
                guard let p = scanner.point(relativeTo: command == "m" ? current : .zero) else { return path }
                current = p
                subpathStart = p
                lastControl = nil
                path.move(to: p)

            case "L", "l":
                guard let p = scanner.point(relativeTo: command == "l" ? current : .zero) else { return path }
                current = p
                lastControl = nil
                path.addLine(to: p)

            case "H", "h":
                guard let x = scanner.number() else { return path }
                current = CGPoint(x: command == "h" ? current.x + x : x, y: current.y)
                lastControl = nil
                path.addLine(to: current)

            case "V", "v":
                guard let y = scanner.number() else { return path }
                current = CGPoint(x: current.x, y: command == "v" ? current.y + y : y)
                lastControl = nil
                path.addLine(to: current)

            case "C", "c":
                let origin = command == "c" ? current : .zero
                guard let c1 = scanner.point(relativeTo: origin),
                      let c2 = scanner.point(relativeTo: origin),
                      let end = scanner.point(relativeTo: origin) else { return path }
                path.addCurve(to: end, control1: c1, control2: c2)
                lastControl = c2
                current = end

            case "S", "s":
                let origin = command == "s" ? current : .zero
                guard let c2 = scanner.point(relativeTo: origin),
                      let end = scanner.point(relativeTo: origin) else { return path }
                // The first control point mirrors the previous one.
                let c1 = lastControl.map {
                    CGPoint(x: 2 * current.x - $0.x, y: 2 * current.y - $0.y)
                } ?? current
                path.addCurve(to: end, control1: c1, control2: c2)
                lastControl = c2
                current = end

            case "A", "a":
                guard let rx = scanner.number(),
                      let ry = scanner.number(),
                      let rotation = scanner.number(),
                      let largeArc = scanner.flag(),
                      let sweep = scanner.flag(),
                      let end = scanner.point(relativeTo: command == "a" ? current : .zero)
                else { return path }
                appendArc(
                    to: path,
                    from: current,
                    to: end,
                    rx: rx,
                    ry: ry,
                    rotationDegrees: rotation,
                    largeArc: largeArc,
                    sweep: sweep
                )
                lastControl = nil
                current = end

            case "Z", "z":
                path.closeSubpath()
                current = subpathStart
                lastControl = nil

            default:
                return path
            }
        }
        return path
    }

    // MARK: - Arc

    /// Endpoint-parameterised arc → centre parameterisation → cubic segments,
    /// following the SVG implementation notes (F.6.5).
    private static func appendArc(
        to path: CGMutablePath,
        from start: CGPoint,
        to end: CGPoint,
        rx: CGFloat,
        ry: CGFloat,
        rotationDegrees: CGFloat,
        largeArc: Bool,
        sweep: Bool
    ) {
        if rx == 0 || ry == 0 || (start.x == end.x && start.y == end.y) {
            path.addLine(to: end)
            return
        }

        var rx = abs(rx)
        var ry = abs(ry)
        let phi = rotationDegrees * .pi / 180
        let cosPhi = cos(phi)
        let sinPhi = sin(phi)

        let dx2 = (start.x - end.x) / 2
        let dy2 = (start.y - end.y) / 2
        let x1p = cosPhi * dx2 + sinPhi * dy2
        let y1p = -sinPhi * dx2 + cosPhi * dy2

        // Scale the radii up if they are too small to span the two points.
        let lambda = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
        if lambda > 1 {
            let scale = sqrt(lambda)
            rx *= scale
            ry *= scale
        }

        let sign: CGFloat = (largeArc != sweep) ? 1 : -1
        let numerator = max(0, rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p)
        let denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p
        let coefficient = denominator == 0 ? 0 : sign * sqrt(numerator / denominator)

        let cxp = coefficient * rx * y1p / ry
        let cyp = -coefficient * ry * x1p / rx
        let cx = cosPhi * cxp - sinPhi * cyp + (start.x + end.x) / 2
        let cy = sinPhi * cxp + cosPhi * cyp + (start.y + end.y) / 2

        func angle(_ ux: CGFloat, _ uy: CGFloat, _ vx: CGFloat, _ vy: CGFloat) -> CGFloat {
            let dot = ux * vx + uy * vy
            let len = sqrt(ux * ux + uy * uy) * sqrt(vx * vx + vy * vy)
            guard len != 0 else { return 0 }
            var value = acos(min(1, max(-1, dot / len)))
            if ux * vy - uy * vx < 0 { value = -value }
            return value
        }

        let theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
        var delta = angle(
            (x1p - cxp) / rx, (y1p - cyp) / ry,
            (-x1p - cxp) / rx, (-y1p - cyp) / ry
        )
        if !sweep && delta > 0 { delta -= 2 * .pi }
        if sweep && delta < 0 { delta += 2 * .pi }

        // A cubic approximates at most a quarter turn well.
        let segments = max(1, Int(ceil(abs(delta) / (.pi / 2))))
        let step = delta / CGFloat(segments)
        let alpha = 4.0 / 3.0 * tan(step / 4)

        var angleStart = theta1
        var point = start
        for _ in 0..<segments {
            let angleEnd = angleStart + step

            let cosStart = cos(angleStart), sinStart = sin(angleStart)
            let cosEnd = cos(angleEnd), sinEnd = sin(angleEnd)

            let dxStart = -rx * cosPhi * sinStart - ry * sinPhi * cosStart
            let dyStart = -rx * sinPhi * sinStart + ry * cosPhi * cosStart
            let dxEnd = -rx * cosPhi * sinEnd - ry * sinPhi * cosEnd
            let dyEnd = -rx * sinPhi * sinEnd + ry * cosPhi * cosEnd

            let endPoint = CGPoint(
                x: cx + rx * cosPhi * cosEnd - ry * sinPhi * sinEnd,
                y: cy + rx * sinPhi * cosEnd + ry * cosPhi * sinEnd
            )
            let control1 = CGPoint(x: point.x + alpha * dxStart, y: point.y + alpha * dyStart)
            let control2 = CGPoint(x: endPoint.x - alpha * dxEnd, y: endPoint.y - alpha * dyEnd)

            path.addCurve(to: endPoint, control1: control1, control2: control2)

            point = endPoint
            angleStart = angleEnd
        }
    }

    // MARK: - Scanning

    private struct TokenScanner {
        private let chars: [Character]
        private var index = 0

        init(_ text: String) {
            chars = Array(text)
        }

        struct Token {
            let letter: Character?
        }

        mutating func nextCommandOrNumberPrefix() -> Token? {
            skipSeparators()
            guard index < chars.count else { return nil }
            let ch = chars[index]
            if ch.isLetter {
                index += 1
                return Token(letter: ch)
            }
            return Token(letter: nil)
        }

        mutating func number() -> CGFloat? {
            skipSeparators()
            guard index < chars.count else { return nil }

            var text = ""
            if chars[index] == "-" || chars[index] == "+" {
                text.append(chars[index])
                index += 1
            }
            while index < chars.count, chars[index].isNumber || chars[index] == "." {
                text.append(chars[index])
                index += 1
            }
            if index < chars.count, chars[index] == "e" || chars[index] == "E" {
                text.append(chars[index])
                index += 1
                if index < chars.count, chars[index] == "-" || chars[index] == "+" {
                    text.append(chars[index])
                    index += 1
                }
                while index < chars.count, chars[index].isNumber {
                    text.append(chars[index])
                    index += 1
                }
            }
            return Double(text).map { CGFloat($0) }
        }

        /// Arc flags are single digits and may be written without separators.
        mutating func flag() -> Bool? {
            skipSeparators()
            guard index < chars.count else { return nil }
            let ch = chars[index]
            guard ch == "0" || ch == "1" else { return number().map { $0 != 0 } }
            index += 1
            return ch == "1"
        }

        mutating func point(relativeTo origin: CGPoint) -> CGPoint? {
            guard let x = number(), let y = number() else { return nil }
            return CGPoint(x: origin.x + x, y: origin.y + y)
        }

        private mutating func skipSeparators() {
            while index < chars.count, chars[index] == " " || chars[index] == ","
                || chars[index] == "\n" || chars[index] == "\t" || chars[index] == "\r" {
                index += 1
            }
        }
    }
}
