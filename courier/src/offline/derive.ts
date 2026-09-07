import type { CourierOrder, PickupRun, Shift } from "@/api/types"
import type { OutboxRow } from "./outbox"

/**
 * What the courier sees, which is the server's answer plus what they have done
 * since.
 *
 * The alternative — showing only what the server has confirmed — was tried on
 * paper and is unusable: a courier who marks a delivery in a basement watches
 * the stop sit there as if nothing happened, taps again, and now there are two
 * of everything. So the screens render the cache with the queue laid over it,
 * and every overlaid row is labelled as unsent rather than pretending to be
 * fact.
 */

export type QueuedMark = "deliver" | "failed" | null

export type Stop = {
  order: CourierOrder
  /** What this courier has already recorded here but not yet sent. */
  queued: QueuedMark
  /** Where it belongs on the round screen. */
  done: boolean
}

export function stops(orders: CourierOrder[], rows: OutboxRow[]): Stop[] {
  const pending = new Map<number, QueuedMark>()
  for (const row of rows) {
    if (row.blocked) continue
    if (row.kind === "deliver") pending.set(row.targetId, "deliver")
    // A failed attempt does not settle a stop, so it must not overwrite a
    // delivery queued for the same order — which can only happen if the two
    // were recorded in that order, and the delivery is the later word.
    else if (row.kind === "failed" && !pending.has(row.targetId)) {
      pending.set(row.targetId, "failed")
    }
  }
  return orders.map((order) => {
    const queued = pending.get(order.id) ?? null
    return {
      order,
      queued,
      done: order.status === "delivered" || queued === "deliver",
    }
  })
}

/**
 * The money, counted twice.
 *
 * `confirmed` is the server's figure for the shift. `unsent` is the cash from
 * deliveries the courier has recorded and the queue has not yet delivered — it
 * is in their pocket either way, so a close screen that showed only the
 * server's figure would ask them to hand over less than they are holding.
 */
export type CashView = {
  confirmed: number
  unsent: number
  total: number
}

export function cash(shift: Shift | null, rows: OutboxRow[]): CashView {
  const confirmed = shift?.cash_expected ?? 0
  const unsent = rows
    .filter((row) => row.kind === "deliver" && !row.blocked)
    .reduce((total, row) => total + row.cash, 0)
  return { confirmed, unsent, total: confirmed + unsent }
}

/**
 * Where the shift has got to, including the part only this phone knows.
 *
 * `opening` and `closing` are states the server has never heard of: they are a
 * courier who tapped the button with no signal. They are shown as distinct
 * from `open` and `closed` because a courier who believes the office can see
 * their shift, when it cannot, is a courier who walks away at the end of the
 * day with an unsent queue.
 */
export type ShiftState = "none" | "opening" | "open" | "closing" | "closed"

export function shiftState(shift: Shift | null, rows: OutboxRow[]): ShiftState {
  const live = rows.filter((row) => !row.blocked)
  if (live.some((row) => row.kind === "shift-close")) return "closing"
  if (shift?.status === "open") return "open"
  if (live.some((row) => row.kind === "shift-open")) return "opening"
  if (shift?.status === "closed") return "closed"
  return "none"
}

/**
 * Whether a delivery may be recorded at all.
 *
 * The server refuses one without an open shift, and refuses it *after* the
 * courier has walked away from the door. Checking here means the refusal
 * happens while they can still act on it — and a shift queued but unsent
 * counts, because it is ahead of the delivery in the queue and will land
 * first.
 */
export function canDeliver(state: ShiftState): boolean {
  return state === "open" || state === "opening"
}

/** A queued collection hides the run's real state the same way. */
export function pickupQueued(run: PickupRun, rows: OutboxRow[]): boolean {
  return rows.some((row) => row.kind === "pickup-collect" && row.targetId === run.id && !row.blocked)
}

export function countUnsent(rows: OutboxRow[]): { pending: number; blocked: number } {
  return {
    pending: rows.filter((row) => !row.blocked).length,
    blocked: rows.filter((row) => row.blocked).length,
  }
}
