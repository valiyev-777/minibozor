import { add, all, clearStore, get, OUTBOX, put, remove } from "./db"

/** What kind of write is waiting, and therefore which endpoint sends it. */
export type ActionKind =
  | "shift-open"
  | "shift-close"
  | "deliver"
  | "failed"
  | "pickup-collect"

/**
 * One write the courier has made and the server has not yet accepted.
 *
 * Three of these fields are the whole point of the application:
 *
 * - **`key`** is a uuid minted *once*, at the moment the courier tapped the
 *   button, and written to disk before anything is sent. Every attempt to send
 *   this row carries that same key. Minting a fresh one on retry is the bug
 *   this app exists to avoid: the server would see two unrelated requests and
 *   put the same 240 000 so'm on the shift twice, and nobody would notice
 *   until the courier was accused of being short.
 * - **`body`** is the encoded request, frozen at that same moment and sent
 *   verbatim. The server hashes the body alongside the key, so a row's body
 *   must never be edited — a different body under the same key is refused with
 *   a 409, and rightly so, because it is a different request.
 * - **`createdAt`** is when the courier acted, not when we managed to send it.
 *   It is what the queue screen counts from.
 *
 * A row lives until the server accepts it and is then deleted. The exception
 * is `blocked`: a request the server refused for a reason retrying will not
 * change stays here, visible and idle, because the courier needs to know that
 * what they wrote down did not land.
 */
export type OutboxRow = {
  id?: number
  key: string
  kind: ActionKind
  /** Order id, shift id or run id — whatever the path needs. Zero for shift-open. */
  targetId: number
  body: string
  /** What to call this on the queue screen: "MB-1042 · Yetkazildi". */
  label: string
  /** Cash this action adds to the shift once it lands, so the total can say so. */
  cash: number
  createdAt: number
  attempts: number
  lastError: string | null
  blocked: boolean
}

/**
 * Where a key comes from.
 *
 * Indirected so a test can hand out keys it can name. The property under test
 * is that the key a row is sent with is the key it was minted with — possibly
 * hours and several attempts earlier — and a test that cannot predict the key
 * can only assert that two attempts matched, not that neither was fresh.
 */
export type Mint = () => string

export const uuidMint: Mint = () =>
  // `randomUUID` needs a secure context. A courier's phone talks to the app
  // over https, but a developer on a LAN address does not, and a queue that
  // throws on the first delivery would be a strange thing to discover then.
  globalThis.crypto?.randomUUID?.() ??
  `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`

/** Anything that can hold the queue. The real one is IndexedDB; tests fake it. */
export interface OutboxStore {
  enqueue(row: Omit<OutboxRow, "id">): Promise<number>
  rows(): Promise<OutboxRow[]>
  sendable(): Promise<OutboxRow[]>
  noteFailure(id: number, error: string): Promise<void>
  block(id: number, error: string): Promise<void>
  discard(id: number): Promise<void>
  clear(): Promise<void>
}

export class IdbOutbox implements OutboxStore {
  async enqueue(row: Omit<OutboxRow, "id">): Promise<number> {
    return (await add(OUTBOX, row)) as number
  }

  async rows(): Promise<OutboxRow[]> {
    return all<OutboxRow>(OUTBOX)
  }

  async sendable(): Promise<OutboxRow[]> {
    return (await this.rows()).filter((row) => !row.blocked)
  }

  async noteFailure(id: number, error: string): Promise<void> {
    await this.patch(id, (row) => ({ ...row, attempts: row.attempts + 1, lastError: error }))
  }

  async block(id: number, error: string): Promise<void> {
    await this.patch(id, (row) => ({
      ...row,
      attempts: row.attempts + 1,
      lastError: error,
      blocked: true,
    }))
  }

  async discard(id: number): Promise<void> {
    await remove(OUTBOX, id)
  }

  async clear(): Promise<void> {
    await clearStore(OUTBOX)
  }

  private async patch(id: number, change: (row: OutboxRow) => OutboxRow): Promise<void> {
    const row = await get<OutboxRow>(OUTBOX, id)
    if (!row) return
    await put(OUTBOX, change(row))
  }
}

/**
 * Write the action down and hand back its row id.
 *
 * Everything the app writes goes through here, online or not. There is no
 * "send it now if we can, queue it otherwise" branch anywhere in the screens,
 * and that absence is the design: a delivery recorded on a good connection and
 * one recorded in a lift take the same path, get the same key, and are sent by
 * the same loop. The only difference is how long the row lives.
 */
export async function enqueue(
  store: OutboxStore,
  action: {
    kind: ActionKind
    targetId: number
    body: unknown
    label: string
    cash?: number
  },
  mint: Mint = uuidMint,
): Promise<number> {
  return store.enqueue({
    key: mint(),
    kind: action.kind,
    targetId: action.targetId,
    // Encoded here, once. Not at send time: two encodings of the same object
    // could differ by a key order or an omitted default, and the server hashes
    // these bytes together with the key above.
    body: JSON.stringify(action.body ?? {}),
    label: action.label,
    cash: action.cash ?? 0,
    createdAt: Date.now(),
    attempts: 0,
    lastError: null,
    blocked: false,
  })
}

/**
 * Whether this exact action is already waiting.
 *
 * A courier standing in the cold taps a button twice as a matter of course.
 * Two rows would be two keys, and two keys are two deliveries as far as the
 * server is concerned — the second one bouncing off the status check with a
 * 409 the courier then has to make sense of. Cheaper to notice here.
 */
export function pendingFor(
  rows: OutboxRow[],
  kind: ActionKind,
  targetId: number,
): OutboxRow | undefined {
  return rows.find((row) => row.kind === kind && row.targetId === targetId && !row.blocked)
}
