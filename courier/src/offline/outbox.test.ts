import "fake-indexeddb/auto"
import { beforeEach, describe, expect, it } from "vitest"
import { IdbOutbox, enqueue, pendingFor, type OutboxRow } from "./outbox"
import { resetDbHandle } from "./db"
import { runOutbox, type SyncSink, type Transport } from "./sync"

/**
 * The queue, tested against a real IndexedDB.
 *
 * `fake-indexeddb` rather than a hand-written stub, because the thing being
 * proved is that a delivery survives — a stub that keeps rows in an array
 * would prove that an array keeps rows. Between the two halves of the central
 * test the database handle is dropped and reopened, which is what a reload in
 * a lift does to this application.
 */

type Attempt = { path: string; key: string; body: string }

function recorder() {
  const attempts: Attempt[] = []
  let refuse: { status: number; message: string } | null = null
  let answer: unknown = { id: 1 }

  const transport: Transport = async (path, key, body) => {
    attempts.push({ path, key, body })
    if (refuse) throw refuse
    return answer
  }
  return {
    attempts,
    transport,
    offline() {
      refuse = { status: 0, message: "Tarmoq yo'q." }
    },
    online(response: unknown = { id: 1 }) {
      refuse = null
      answer = response
    },
    refuseWith(status: number, message: string) {
      refuse = { status, message }
    },
  }
}

function sink(shiftId: number | null = null): SyncSink & { orders: unknown[]; shifts: unknown[] } {
  const orders: unknown[] = []
  const shifts: unknown[] = []
  let known = shiftId
  return {
    orders,
    shifts,
    async onOrder(order) {
      orders.push(order)
    },
    async onShift(shift) {
      shifts.push(shift)
      known = (shift as { id?: number }).id ?? known
    },
    async onPickupRun() {},
    async knownShiftId() {
      return known
    },
  }
}

const DELIVERY = {
  kind: "deliver" as const,
  targetId: 42,
  body: { recipient_name: "Aziza Karimova", photo_url: "", cash_collected: 240_000, note: "" },
  label: "MB-1042 · Yetkazildi",
  cash: 240_000,
}

beforeEach(async () => {
  resetDbHandle()
  await new Promise<void>((resolve) => {
    const request = indexedDB.deleteDatabase("minibozor-courier")
    request.onsuccess = () => resolve()
    request.onerror = () => resolve()
    request.onblocked = () => resolve()
  })
})

describe("a delivery recorded with no network", () => {
  it("is sent exactly once, under the key it was given, when the network comes back", async () => {
    const store = new IdbOutbox()
    const net = recorder()
    const effects = sink()

    // In a basement. The courier hands the goods over and marks the stop.
    net.offline()
    await enqueue(store, DELIVERY)

    const queued = (await store.rows())[0] as OutboxRow
    expect(queued.key).toMatch(/\w/)
    const key = queued.key
    const body = queued.body

    // Every attempt down here fails, and the row must survive all of them.
    for (let i = 0; i < 3; i++) {
      const report = await runOutbox({ store, transport: net.transport, sink: effects })
      expect(report.sent).toBe(0)
      expect(report.stoppedBy).not.toBeNull()
    }
    expect(await store.rows()).toHaveLength(1)
    // Three attempts, three requests, and the same key on every one of them. A
    // fresh key here would be a second delivery and a second 240 000 so'm.
    expect(net.attempts).toHaveLength(3)
    expect(new Set(net.attempts.map((a) => a.key))).toEqual(new Set([key]))
    expect(new Set(net.attempts.map((a) => a.body))).toEqual(new Set([body]))

    // The phone is restarted on the way back to the depot.
    resetDbHandle()
    const afterReboot = new IdbOutbox()
    const survivors = await afterReboot.rows()
    expect(survivors).toHaveLength(1)
    expect(survivors[0]!.key).toBe(key)
    expect(survivors[0]!.body).toBe(body)

    // Out of the building.
    net.online({ id: 42, code: "MB-1042", status: "delivered" })
    const report = await runOutbox({ store: afterReboot, transport: net.transport, sink: effects })

    expect(report.sent).toBe(1)
    expect(await afterReboot.rows()).toHaveLength(0)
    // Four requests in total, one of which succeeded — and the successful one
    // carried the key minted underground.
    expect(net.attempts).toHaveLength(4)
    expect(net.attempts.at(-1)!.key).toBe(key)
    expect(net.attempts.at(-1)!.path).toBe("/courier/orders/42/deliver")
    expect(effects.orders).toHaveLength(1)

    // And a second pass sends nothing at all: the row is gone, so there is no
    // way for the same delivery to reach the server twice.
    const again = await runOutbox({ store: afterReboot, transport: net.transport, sink: effects })
    expect(again.sent).toBe(0)
    expect(net.attempts).toHaveLength(4)
  })

  it("sends the body byte for byte, so the server's digest matches on the retry", async () => {
    const store = new IdbOutbox()
    const net = recorder()
    net.offline()
    await enqueue(store, DELIVERY)
    await runOutbox({ store, transport: net.transport, sink: sink() })
    net.online()
    await runOutbox({ store, transport: net.transport, sink: sink() })

    expect(net.attempts[0]!.body).toBe(net.attempts[1]!.body)
    expect(JSON.parse(net.attempts[1]!.body)).toEqual(DELIVERY.body)
  })
})

describe("the order things are sent in", () => {
  it("opens the shift before the delivery that needs it", async () => {
    const store = new IdbOutbox()
    const net = recorder()
    net.offline()

    await enqueue(store, { kind: "shift-open", targetId: 0, body: {}, label: "Smena ochish" })
    await enqueue(store, DELIVERY)

    // Offline, only the first row is attempted: everything behind it would
    // fail the same way, and the courier's battery is not free.
    await runOutbox({ store, transport: net.transport, sink: sink() })
    expect(net.attempts).toHaveLength(1)
    expect(net.attempts[0]!.path).toBe("/courier/shifts")

    net.online({ id: 7, status: "open" })
    const report = await runOutbox({ store, transport: net.transport, sink: sink() })
    expect(report.sent).toBe(2)
    expect(net.attempts.map((a) => a.path)).toEqual([
      "/courier/shifts",
      "/courier/shifts",
      "/courier/orders/42/deliver",
    ])
  })

  it("closes a shift that was opened offline, once the open has landed", async () => {
    const store = new IdbOutbox()
    const net = recorder()
    const effects = sink(null)

    // Both recorded underground, so the close has no shift id to point at.
    await enqueue(store, { kind: "shift-open", targetId: 0, body: {}, label: "Smena ochish" })
    await enqueue(store, {
      kind: "shift-close",
      targetId: 0,
      body: { cash_declared: 240_000, note: "" },
      label: "Smenani yopish",
    })

    net.online({ id: 7, status: "open" })
    const report = await runOutbox({ store, transport: net.transport, sink: effects })

    expect(report.sent).toBe(2)
    // The id was resolved from the answer to the open — and only the path
    // changed, never the body the key was issued against.
    expect(net.attempts[1]!.path).toBe("/courier/shifts/7/close")
    expect(JSON.parse(net.attempts[1]!.body)).toEqual({ cash_declared: 240_000, note: "" })
  })
})

describe("a refusal", () => {
  it("is kept and shown rather than retried forever, and does not hold up the rest", async () => {
    const store = new IdbOutbox()
    const net = recorder()

    await enqueue(store, DELIVERY)
    await enqueue(store, { ...DELIVERY, targetId: 43, label: "MB-1043 · Yetkazildi" })

    // The first stop was cancelled by an operator while the courier was
    // underground: the server understands and says no.
    let seen = 0
    const transport: Transport = async (path, key, body) => {
      seen++
      if (seen === 1) throw { status: 409, message: "Buyurtma bu holatdan o'tolmaydi." }
      return net.transport(path, key, body)
    }

    const report = await runOutbox({ store, transport, sink: sink() })
    expect(report.blocked).toBe(1)
    expect(report.sent).toBe(1)

    const rows = await store.rows()
    expect(rows).toHaveLength(1)
    expect(rows[0]!.blocked).toBe(true)
    expect(rows[0]!.lastError).toBe("Buyurtma bu holatdan o'tolmaydi.")

    // A blocked row is never attempted again on its own.
    const before = seen
    await runOutbox({ store, transport, sink: sink() })
    expect(seen).toBe(before)
  })

  it("treats a server fault as something to try again, not something to bury", async () => {
    const store = new IdbOutbox()
    const net = recorder()
    await enqueue(store, DELIVERY)

    net.refuseWith(503, "Server javob bermayapti.")
    await runOutbox({ store, transport: net.transport, sink: sink() })

    const rows = await store.rows()
    expect(rows[0]!.blocked).toBe(false)
    expect(rows[0]!.attempts).toBe(1)
  })
})

describe("tapping the button twice", () => {
  it("is caught before a second key is ever minted", async () => {
    const store = new IdbOutbox()
    await enqueue(store, DELIVERY)
    const rows = await store.rows()

    expect(pendingFor(rows, "deliver", 42)).toBeDefined()
    expect(pendingFor(rows, "deliver", 99)).toBeUndefined()
  })
})
