import * as React from "react"
import { toast } from "sonner"
import { ApiError, api, postKeyed } from "@/api/client"
import type { CourierOrder, PickupRun, Shift } from "@/api/types"
import { askForPersistence } from "./db"
import { clearCache, patchOrder, patchPickupRun, readCache, writeCache } from "./cache"
import { countUnsent } from "./derive"
import { IdbOutbox, enqueue as enqueueRow, type ActionKind, type OutboxRow } from "./outbox"
import { runOutbox, type SyncSink } from "./sync"

/**
 * The one place that knows what the courier has and has not sent.
 *
 * Every screen reads from here and nothing reads the network directly. That is
 * the rule that makes the offline behaviour a property of the application
 * rather than something each screen remembers to do: a screen asks for the
 * round, and gets the cached round with the queue laid over it, whether or not
 * there is signal.
 */

const store = new IdbOutbox()

type Loaded<T> = { data: T; at: number | null }

type OfflineValue = {
  rows: OutboxRow[]
  orders: Loaded<CourierOrder[]>
  shift: Loaded<Shift | null>
  pickups: Loaded<PickupRun[]>
  /** Whether the last thing we asked the server actually got an answer. */
  reachable: boolean
  syncing: boolean
  refreshing: boolean
  unsent: { pending: number; blocked: number }

  refresh: () => Promise<void>
  sync: () => Promise<void>
  record: (action: {
    kind: ActionKind
    targetId: number
    body: unknown
    label: string
    cash?: number
  }) => Promise<void>
  discard: (id: number) => Promise<void>
  reset: () => Promise<void>
}

const Context = React.createContext<OfflineValue | null>(null)

export function OfflineProvider({ children }: { children: React.ReactNode }) {
  const [rows, setRows] = React.useState<OutboxRow[]>([])
  const [orders, setOrders] = React.useState<Loaded<CourierOrder[]>>({ data: [], at: null })
  const [shift, setShift] = React.useState<Loaded<Shift | null>>({ data: null, at: null })
  const [pickups, setPickups] = React.useState<Loaded<PickupRun[]>>({ data: [], at: null })
  const [reachable, setReachable] = React.useState(navigator.onLine)
  const [syncing, setSyncing] = React.useState(false)
  const [refreshing, setRefreshing] = React.useState(false)

  const reloadRows = React.useCallback(async () => {
    setRows(await store.rows())
  }, [])

  const reloadCache = React.useCallback(async () => {
    const [cachedOrders, cachedShift, cachedPickups] = await Promise.all([
      readCache("orders"),
      readCache("shift"),
      readCache("pickups"),
    ])
    if (cachedOrders) setOrders({ data: cachedOrders.data, at: cachedOrders.at })
    if (cachedShift) setShift({ data: cachedShift.data, at: cachedShift.at })
    if (cachedPickups) setPickups({ data: cachedPickups.data, at: cachedPickups.at })
  }, [])

  /**
   * What to do with a write the server has just accepted.
   *
   * The cache is updated from the response rather than by re-fetching: the
   * courier may already be back underground by the time the queue drains, and
   * the answer in hand is newer than anything a failed refresh would leave.
   */
  const sink: SyncSink = React.useMemo(
    () => ({
      onOrder: async (order) => {
        await patchOrder(order as CourierOrder)
      },
      onShift: async (updated) => {
        await writeCache("shift", updated as Shift)
      },
      onPickupRun: async (run) => {
        await patchPickupRun(run as PickupRun)
      },
      knownShiftId: async () => (await readCache("shift"))?.data?.id ?? null,
    }),
    [],
  )

  /**
   * A lock, in a ref rather than in state.
   *
   * Three things ask for a pass at once — the reconnect handler, the interval
   * and the screen that has just recorded something — and a state flag would
   * let all three through before any of them re-rendered.
   */
  const running = React.useRef(false)

  const sync = React.useCallback(async () => {
    if (running.current) return
    running.current = true
    setSyncing(true)
    try {
      const report = await runOutbox({
        store,
        transport: (path, key, body) => postKeyed(path, key, body),
        sink,
      })
      setReachable(report.stoppedBy === null || report.sent > 0)
      await reloadRows()
      await reloadCache()
      if (report.sent > 0) {
        toast.success(
          report.sent === 1 ? "1 amal serverga yuborildi." : `${report.sent} amal serverga yuborildi.`,
        )
      }
      if (report.blocked > 0) {
        toast.error(
          `${report.blocked} amalni server rad etdi. Navbat sahifasiga qarang.`,
          { duration: 8000 },
        )
      }
    } finally {
      running.current = false
      setSyncing(false)
    }
  }, [reloadCache, reloadRows, sink])

  /**
   * Pull the round, the shift and the collections.
   *
   * Failure is not an error state. A courier in a lift refreshing the round is
   * doing something reasonable and gets the cached round back with its age on
   * it; only the network flag changes.
   */
  const refresh = React.useCallback(async () => {
    setRefreshing(true)
    try {
      const [freshOrders, freshShift, freshPickups] = await Promise.all([
        api<CourierOrder[]>("/courier/orders"),
        api<Shift | null>("/courier/shifts/current"),
        api<PickupRun[]>("/courier/pickups"),
      ])
      await Promise.all([
        writeCache("orders", freshOrders),
        writeCache("shift", freshShift),
        writeCache("pickups", freshPickups),
      ])
      setOrders({ data: freshOrders, at: Date.now() })
      setShift({ data: freshShift, at: Date.now() })
      setPickups({ data: freshPickups, at: Date.now() })
      setReachable(true)
    } catch (error) {
      if (error instanceof ApiError && error.isOffline) setReachable(false)
      await reloadCache()
    } finally {
      setRefreshing(false)
    }
  }, [reloadCache])

  const record = React.useCallback<OfflineValue["record"]>(
    async (action) => {
      await enqueueRow(store, action)
      await reloadRows()
      // Try immediately. On a good connection the row is gone before the next
      // screen finishes its transition and the courier never learns there was
      // a queue; underground it stays, which is the same code path.
      void sync()
    },
    [reloadRows, sync],
  )

  const discard = React.useCallback(
    async (id: number) => {
      await store.discard(id)
      await reloadRows()
    },
    [reloadRows],
  )

  const reset = React.useCallback(async () => {
    await clearCache()
    setOrders({ data: [], at: null })
    setShift({ data: null, at: null })
    setPickups({ data: [], at: null })
    await reloadRows()
  }, [reloadRows])

  // First paint: the disk, then the network. In that order, so a courier who
  // opens the app underground sees their round rather than a spinner that
  // times out.
  React.useEffect(() => {
    void (async () => {
      await reloadRows()
      await reloadCache()
      void askForPersistence()
      await refresh()
      void sync()
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * When to try again.
   *
   * `online` fires when the phone gets an IP address, which is the closest
   * thing the browser offers to "you are out of the lift". It is a hint and
   * not a fact — one bar of signal reports online and then times out — so
   * there is also an interval, and a check when the courier brings the app
   * back to the foreground, which is what actually happens when they come up
   * the stairs.
   *
   * There is deliberately no Background Sync registration. It would need the
   * service worker to hold the access token to send anything, which means
   * putting a credential somewhere this code was careful to keep it out of,
   * and it buys sending while the app is closed — which for a tool the
   * courier has open all shift is not worth that trade.
   */
  React.useEffect(() => {
    const wake = () => {
      setReachable(navigator.onLine)
      void sync()
    }
    const onVisible = () => {
      if (document.visibilityState === "visible") wake()
    }
    window.addEventListener("online", wake)
    window.addEventListener("offline", () => setReachable(false))
    document.addEventListener("visibilitychange", onVisible)
    const timer = window.setInterval(() => {
      if (rows.some((row) => !row.blocked)) void sync()
    }, 30_000)
    return () => {
      window.removeEventListener("online", wake)
      document.removeEventListener("visibilitychange", onVisible)
      window.clearInterval(timer)
    }
  }, [rows, sync])

  const value: OfflineValue = {
    rows,
    orders,
    shift,
    pickups,
    reachable,
    syncing,
    refreshing,
    unsent: countUnsent(rows),
    refresh,
    sync,
    record,
    discard,
    reset,
  }

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useOffline(): OfflineValue {
  const value = React.useContext(Context)
  if (!value) throw new Error("useOffline outside OfflineProvider")
  return value
}
