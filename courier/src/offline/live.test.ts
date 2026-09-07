import "fake-indexeddb/auto"
import { beforeAll, describe, expect, it } from "vitest"
import { IdbOutbox, enqueue } from "./outbox"
import { resetDbHandle } from "./db"
import { runOutbox, type SyncSink, type Transport } from "./sync"

/**
 * The queue against the real server.
 *
 * `outbox.test.ts` proves the queue behaves; this proves the two halves agree
 * — that the header this app sends is the header `app/idempotency.py` reads,
 * and that a delivery recorded underground and retried four times is one sale
 * and one lot of cash at the far end rather than four.
 *
 * Skipped unless a backend is running, because a unit suite that needs a
 * database to pass is a suite people stop running:
 *
 *     MB_LIVE=1 MB_API_URL=http://127.0.0.1:8001 npm test
 *
 * It needs the round from `tools/seed-round.py` and it consumes it — a
 * delivered stop stays delivered. Re-run the fixture afterwards.
 */

const LIVE = process.env["MB_LIVE"] === "1"
const BASE = `${process.env["MB_API_URL"] ?? "http://127.0.0.1:8001"}/api/v1`
const COURIER_PHONE = "+998900000007"

let token = ""

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: {
      "Accept-Language": "uz",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  })
  const text = await res.text()
  const body = text ? JSON.parse(text) : null
  if (!res.ok) {
    throw Object.assign(new Error(body?.detail ?? res.statusText), { status: res.status })
  }
  return body as T
}

describe.skipIf(!LIVE)("against a running backend", () => {
  beforeAll(async () => {
    const requested = await call<{ dev_code: string | null }>("/auth/otp/request", {
      method: "POST",
      body: JSON.stringify({ phone: COURIER_PHONE }),
    })
    expect(requested.dev_code, "the dev server must echo the code").toBeTruthy()
    const pair = await call<{ access_token: string }>("/auth/otp/verify", {
      method: "POST",
      body: JSON.stringify({ phone: COURIER_PHONE, code: requested.dev_code }),
    })
    token = pair.access_token

    // Only a courier gets past here at all — the guard the login screen relies on.
    const me = await call<{ role: string }>("/staff/me")
    expect(me.role).toBe("courier")

    resetDbHandle()
    await new Promise<void>((resolve) => {
      const request = indexedDB.deleteDatabase("minibozor-courier")
      request.onsuccess = () => resolve()
      request.onerror = () => resolve()
      request.onblocked = () => resolve()
    })
  })

  it("records a delivery underground and lands it exactly once", async () => {
    const store = new IdbOutbox()

    const orders = await call<
      { id: number; code: string; cash_due: number; status: string }[]
    >("/courier/orders")
    const stop = orders.find((order) => order.cash_due > 0 && order.status === "shipped")
    expect(stop, "the fixture must leave a cash stop to deliver").toBeDefined()

    let offline = true
    const attempts: { path: string; key: string; body: string }[] = []
    const transport: Transport = async (path, key, body) => {
      attempts.push({ path, key, body })
      if (offline) throw { status: 0, message: "Tarmoq yo'q." }
      return call(path, { method: "POST", body, headers: { "Idempotency-Key": key } })
    }

    let knownShift: number | null = null
    const sink: SyncSink = {
      async onOrder() {},
      async onShift(shift) {
        knownShift = (shift as { id: number }).id
      },
      async onPickupRun() {},
      async knownShiftId() {
        return knownShift
      },
    }

    // A basement: the courier opens their shift and hands the parcel over.
    await enqueue(store, { kind: "shift-open", targetId: 0, body: {}, label: "Smena ochish" })
    await enqueue(store, {
      kind: "deliver",
      targetId: stop!.id,
      body: {
        recipient_name: "Aziza Karimova",
        photo_url: "",
        cash_collected: stop!.cash_due,
        note: "",
      },
      label: `${stop!.code} · Yetkazildi`,
      cash: stop!.cash_due,
    })

    for (let i = 0; i < 3; i++) {
      const report = await runOutbox({ store, transport, sink })
      expect(report.sent).toBe(0)
    }
    const queued = await store.rows()
    expect(queued).toHaveLength(2)
    const deliveryKey = queued[1]!.key

    // Out of the building.
    offline = false
    const report = await runOutbox({ store, transport, sink })
    expect(report.sent).toBe(2)
    expect(await store.rows()).toHaveLength(0)
    // The key that reached the server is the one minted underground.
    expect(attempts.at(-1)!.key).toBe(deliveryKey)

    const shift = await call<{
      cash_expected: number
      orders_delivered: number
      attempts: unknown[]
    }>("/courier/shifts/current")
    expect(shift.cash_expected).toBe(stop!.cash_due)
    expect(shift.orders_delivered).toBe(1)
    expect(shift.attempts).toHaveLength(1)

    // And the case the whole design exists for: the answer to the first
    // attempt was lost in the lift and the app sends it again. Same key, same
    // bytes — the server replays its own answer and the shift does not move.
    const replayed = await call<{ id: number }>(
      `/courier/orders/${stop!.id}/deliver`,
      {
        method: "POST",
        body: attempts.at(-1)!.body,
        headers: { "Idempotency-Key": deliveryKey },
      },
    )
    expect(replayed.id).toBe(stop!.id)

    const after = await call<{ cash_expected: number; orders_delivered: number }>(
      "/courier/shifts/current",
    )
    expect(after.cash_expected).toBe(stop!.cash_due)
    expect(after.orders_delivered).toBe(1)
  })

  it("refuses the same key carrying a different request", async () => {
    // Not a retry: a bug. The server answers 409 rather than replaying the
    // wrong answer, and the app's job is never to get here — which is why the
    // body is frozen at enqueue and never re-encoded.
    const orders = await call<{ id: number; cash_due: number; status: string }[]>(
      "/courier/orders",
    )
    const stop = orders.find((order) => order.status === "shipped")
    expect(stop).toBeDefined()

    const key = `test-${Date.now()}`
    await call(`/courier/orders/${stop!.id}/failed`, {
      method: "POST",
      body: JSON.stringify({ reason: "Telefonni ko'tarmadi", photo_url: "" }),
      headers: { "Idempotency-Key": key },
    })

    await expect(
      call(`/courier/orders/${stop!.id}/failed`, {
        method: "POST",
        body: JSON.stringify({ reason: "Boshqa sabab", photo_url: "" }),
        headers: { "Idempotency-Key": key },
      }),
    ).rejects.toMatchObject({ status: 409 })
  })
})
