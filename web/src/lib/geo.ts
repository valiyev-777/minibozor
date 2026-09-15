/**
 * How far apart two doors are — the only arithmetic the courier's map needs.
 *
 * **Straight lines, and said so on screen.** A real route length wants a
 * routing service: another network dependency, another key, another thing that
 * fails in a basement, for a figure nobody steers by. What the courier is
 * actually asking at the top of the day is "is this round twenty kilometres or
 * sixty", and the sum of the straight lines between consecutive stops answers
 * that within the error of the question. Every screen that shows it calls it
 * `taxminiy` — approximate — rather than presenting it as a driven distance.
 *
 * A stop with no coordinates contributes nothing and does not break the chain:
 * the line is drawn from the stop before it to the stop after it. That is a
 * slight under-count and it is the honest one — inventing a position for a door
 * nobody pinned would put a wrong number on the screen rather than a low one.
 */

export type Point = { lat: number; lng: number }

const EARTH_KM = 6371

function radians(degrees: number): number {
  return (degrees * Math.PI) / 180
}

/** Great-circle distance between two points, in kilometres. */
export function between(one: Point, two: Point): number {
  const dLat = radians(two.lat - one.lat)
  const dLng = radians(two.lng - one.lng)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(radians(one.lat)) * Math.cos(radians(two.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * EARTH_KM * Math.asin(Math.min(1, Math.sqrt(a)))
}

/** The length of a round, walked in the order given. Nought for fewer than
 *  two pinned stops, which is the honest answer rather than zero-as-unknown:
 *  the screens check the count before they print it. */
export function along(points: Point[]): number {
  let total = 0
  for (let at = 1; at < points.length; at += 1) {
    total += between(points[at - 1], points[at])
  }
  return total
}

/**
 * Minutes a round of this length takes, roughly.
 *
 * 18 km/h is city driving with a stop at the end of each leg — traffic, a
 * parking space, a lift. Plus eight minutes standing at each door, which is
 * where a round's time actually goes: five stops two kilometres apart is forty
 * minutes of doors and fifteen of driving.
 *
 * A constant with a reason beside it, shown under the word `taxminiy`. The
 * alternative is showing nothing, and a courier planning their afternoon would
 * rather have a number with an error bar than no number.
 */
export function minutesFor(kilometres: number, stops: number): number {
  return Math.round((kilometres / 18) * 60 + stops * 8)
}

/** Does this stop have a pin? Narrows the nullable pair to a `Point` so the
 *  callers stop repeating the two null checks. */
export function pinned(what: {
  latitude?: number | null
  longitude?: number | null
}): Point | null {
  const { latitude, longitude } = what
  if (typeof latitude !== "number" || typeof longitude !== "number") return null
  // A pair of noughts is the null island in the Gulf of Guinea, and it is what
  // an unset column looks like when somebody defaults it to zero rather than
  // leaving it null. A stop there is a stop nobody pinned.
  if (latitude === 0 && longitude === 0) return null
  return { lat: latitude, lng: longitude }
}
