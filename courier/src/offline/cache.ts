import type { CourierOrder, PickupRun, Shift, StaffMe } from "@/api/types"
import { CACHE, clearStore, get, put } from "./db"

/**
 * The last thing the server said, kept so the app opens in a basement.
 *
 * Stored as whole responses rather than as normalised tables. The alternative
 * buys queries this app never makes: it reads a round, a shift and a run
 * whole, renders them, and replaces them on the next refresh. What it must
 * never do is show nothing because the lift has no signal.
 *
 * Every entry carries `at`, the moment it was fetched, and every screen that
 * renders from a stale entry says so out loud. A round that is quietly six
 * hours old is worse than one that is honestly absent — the courier would
 * knock on a door that was cancelled at ten.
 */
type Entry<T> = { key: string; at: number; data: T }

export type CacheShape = {
  orders: CourierOrder[]
  /** The shift the courier is on. Null when they are not out. */
  shift: Shift | null
  /**
   * The last shift seen, open or closed.
   *
   * `/courier/shifts/current` answers null once a shift is closed, which is
   * correct and useless to the person who just closed it: they declared a
   * figure thirty seconds ago and the screen would tell them there is no
   * shift. This keeps the closing answer so the money they handed over stays
   * readable until the next round starts.
   */
  lastShift: Shift | null
  pickups: PickupRun[]
  identity: StaffMe | null
}

export type Cached<K extends keyof CacheShape> = { at: number; data: CacheShape[K] } | null

export async function readCache<K extends keyof CacheShape>(key: K): Promise<Cached<K>> {
  const entry = await get<Entry<CacheShape[K]>>(CACHE, key)
  return entry ? { at: entry.at, data: entry.data } : null
}

export async function writeCache<K extends keyof CacheShape>(
  key: K,
  data: CacheShape[K],
): Promise<void> {
  await put<Entry<CacheShape[K]>>(CACHE, { key, at: Date.now(), data })
}

/**
 * Replace one stop in the cached round.
 *
 * Called when a queued delivery finally lands: the server answers with the
 * order in its new state, and the round on screen should agree with it without
 * waiting for a refresh that may be another hour away.
 */
export async function patchOrder(order: CourierOrder): Promise<void> {
  const cached = await readCache("orders")
  const rest = (cached?.data ?? []).filter((row) => row.id !== order.id)
  await writeCache("orders", [...rest, order].sort(bySequence))
}

export async function patchPickupRun(run: PickupRun): Promise<void> {
  const cached = await readCache("pickups")
  const rest = (cached?.data ?? []).filter((row) => row.id !== run.id)
  await writeCache("pickups", [run, ...rest])
}

/**
 * The order an operator planned, then the delivery window, then the code.
 *
 * The same fallback the API itself uses, repeated here because a locally
 * patched round is re-sorted by this code rather than by the server.
 */
export function bySequence(a: CourierOrder, b: CourierOrder): number {
  if (a.sequence !== b.sequence) return a.sequence - b.sequence
  const day = (a.delivery_day ?? "").localeCompare(b.delivery_day ?? "")
  if (day !== 0) return day
  const window = a.delivery_window.localeCompare(b.delivery_window)
  if (window !== 0) return window
  return a.code.localeCompare(b.code)
}

/** On sign-out. The queue is emptied separately and far more carefully. */
export async function clearCache(): Promise<void> {
  await clearStore(CACHE)
}
