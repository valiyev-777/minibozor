import type { OutboxRow, OutboxStore } from "./outbox"

/**
 * How a queued row actually goes out. The real one is `postKeyed`; a test
 * hands in a fake that records what it was called with.
 */
export type Transport = (path: string, key: string, body: string) => Promise<unknown>

/** What the app does with a write the server has just accepted. */
export interface SyncSink {
  onOrder(order: unknown): Promise<void>
  onShift(shift: unknown): Promise<void>
  onPickupRun(run: unknown): Promise<void>

  /**
   * The id of the shift the courier is on, if the app knows one.
   *
   * Needed because a shift can be opened *and* closed without ever seeing a
   * network: the close is queued behind an open that has no server id yet. The
   * id is resolved here at send time, once the open has landed. Only the
   * **path** is resolved — the body the key was issued against does not
   * change, which is what keeps the retry honest.
   */
  knownShiftId(): Promise<number | null>
}

export type SyncReport = {
  sent: number
  blocked: number
  /** Why the run stopped early, if it did. Usually "no network". */
  stoppedBy: string | null
}

/** Anything with a status: `ApiError`, or a test's stand-in for one. */
type Statused = { status?: number; message?: string }

function statusOf(error: unknown): number | null {
  const status = (error as Statused | null)?.status
  return typeof status === "number" ? status : null
}

function messageOf(error: unknown, fallback: string): string {
  const message = (error as Statused | null)?.message
  return typeof message === "string" && message.trim() ? message : fallback
}

export function pathFor(row: OutboxRow, shiftId: number | null): string | null {
  switch (row.kind) {
    case "shift-open":
      return "/courier/shifts"
    case "shift-close": {
      const id = row.targetId > 0 ? row.targetId : shiftId
      return id ? `/courier/shifts/${id}/close` : null
    }
    case "deliver":
      return `/courier/orders/${row.targetId}/deliver`
    case "failed":
      return `/courier/orders/${row.targetId}/failed`
    case "pickup-collect":
      return `/courier/pickups/${row.targetId}/collect`
  }
}

/**
 * Empty the queue, oldest first, one at a time.
 *
 * Three rules, and each costs something worth paying:
 *
 * **In order.** A delivery cannot land before the shift it belongs to was
 * opened — the server refuses it with `shift_required` — and a shift must not
 * close before the deliveries that make up its cash. Sending rows
 * concurrently would be faster and would occasionally invent a cash
 * discrepancy nobody could explain afterwards.
 *
 * **One at a time, stopping on a network failure.** If a row fails because
 * there is no network, every row behind it fails the same way. Carrying on
 * would spend the courier's battery learning the same thing five times.
 *
 * **A refusal is not a retry.** A 4xx means the server understood and said no:
 * already delivered, already collected, not yours any more. Retrying that
 * forever would bury it. The row is marked blocked, stays on the queue screen
 * with the server's own sentence on it, and the loop moves on — the rows
 * behind it are unrelated deliveries at other doors, and holding them hostage
 * to one argument helps nobody. The single action everything else depends on,
 * opening a shift, cannot fail this way: the server hands back the shift you
 * already have rather than an error.
 *
 * Re-entrancy is the caller's problem to avoid and `pulse.ts` avoids it with a
 * lock. Two passes at once would send a row twice; twice with the same key is
 * survivable — that is what the key is for — but it is still two round trips
 * and two chances to confuse the log.
 */
export async function runOutbox(deps: {
  store: OutboxStore
  transport: Transport
  sink: SyncSink
}): Promise<SyncReport> {
  const { store, transport, sink } = deps
  let sent = 0
  let blocked = 0
  let stoppedBy: string | null = null

  const rows = await store.sendable()
  for (const row of rows) {
    if (row.id === undefined) continue

    const path = pathFor(row, await sink.knownShiftId())
    if (!path) {
      // A close whose open has not landed yet. Not an error, just not now.
      await store.noteFailure(row.id, "Smena hali serverda yaratilmagan.")
      stoppedBy = "Smena hali serverda yaratilmagan."
      break
    }

    try {
      // The stored bytes, unchanged, under the key minted with them.
      const answer = await transport(path, row.key, row.body)
      switch (row.kind) {
        case "shift-open":
        case "shift-close":
          await sink.onShift(answer)
          break
        case "deliver":
        case "failed":
          await sink.onOrder(answer)
          break
        case "pickup-collect":
          await sink.onPickupRun(answer)
          break
      }
      await store.discard(row.id)
      sent++
    } catch (error) {
      const status = statusOf(error)
      // Status 0 is "the request never got an answer". The key means asking
      // again is free, so the row keeps its place.
      if (status === null || status === 0) {
        stoppedBy = messageOf(error, "Tarmoq yo'q.")
        await store.noteFailure(row.id, stoppedBy)
        break
      }
      // 401 here means the refresh already failed: the session is genuinely
      // over. The courier signs in again and the queue is still here, which is
      // the point of keeping it on disk.
      if (status === 401 || status === 408 || status === 425 || status === 429 || status >= 500) {
        stoppedBy = messageOf(error, "Server javob bermayapti.")
        await store.noteFailure(row.id, stoppedBy)
        break
      }
      await store.block(row.id, messageOf(error, "Server rad etdi."))
      blocked++
    }
  }

  return { sent, blocked, stoppedBy }
}
