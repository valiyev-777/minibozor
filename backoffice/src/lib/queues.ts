import { useQueries } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { OrderPage, Return, Removal, PickupRun, Supply, Role } from "@/api/types"
import { allowed, SCREENS } from "./nav"

/**
 * How much is waiting, per screen, for the rail to say so.
 *
 * The reason this exists: a warehouse signing in lands on **Qabul qilish**,
 * because that is the first thing they do. An order placed a minute ago is on
 * a different screen, and nothing on the landing screen said so — so an order
 * that had arrived perfectly well looked, to the person meant to pick it, like
 * an order that never came. The rail now carries the count and the work
 * announces itself.
 *
 * "Waiting" is deliberately narrow on every row: things **nobody has acted
 * on**. A batch counted in is not waiting; a batch declared is. An order being
 * picked is somebody's, an order still `placed` is nobody's. A badge that
 * counted work in progress would never reach nought, and a number that is
 * always on is a number nobody reads.
 *
 * Only the rows in this role's own menu are asked for. Firing the warehouse's
 * queries for an operator would mean four requests whose answers are refused,
 * which is noise in the console and a wrong number if one ever came back.
 */
const WAITING: Record<string, { key: string; run: () => Promise<number> }> = {
  "/supplies": {
    key: "supplies-declared",
    run: () =>
      api<Supply[]>("/staff/supplies", { query: { status: "declared" } }).then(
        (rows) => rows.length,
      ),
  },
  "/orders": {
    key: "orders-placed",
    run: () =>
      api<OrderPage>("/staff/orders", {
        query: { status: "placed", page_size: 1 },
      }).then((page) => page.total),
  },
  "/pickups": {
    key: "pickups-open",
    run: () =>
      api<PickupRun[]>("/staff/pickups", { query: { status: "open" } }).then(
        (rows) => rows.length,
      ),
  },
  "/removals": {
    key: "removals-requested",
    run: () =>
      api<Removal[]>("/staff/removals", { query: { status: "requested" } }).then(
        (rows) => rows.length,
      ),
  },
  "/returns": {
    key: "returns-submitted",
    run: () =>
      api<Return[]>("/staff/returns", { query: { status: "submitted" } }).then(
        (rows) => rows.length,
      ),
  },
}

/** The waiting count per path, for the rows this role can open. */
export function useQueueCounts(role: Role): Record<string, number> {
  // Paired with their query up front, so neither the `useQueries` call nor
  // the read below has to index `WAITING` again and prove to the compiler
  // that the row is still there.
  const queues = SCREENS.filter(
    (screen) => screen.menu && allowed(screen, role) && WAITING[screen.path],
  ).map((screen) => ({ path: screen.path, waiting: WAITING[screen.path]! }))

  const results = useQueries({
    queries: queues.map(({ waiting }) => ({
      queryKey: ["queue", waiting.key],
      queryFn: waiting.run,
      // A picker glances at the rail; a minute-old count is still true enough
      // to send them to the right screen, and a rail that refetched on every
      // navigation would be five requests per click.
      staleTime: 30_000,
      refetchInterval: 60_000,
    })),
  })

  const out: Record<string, number> = {}
  queues.forEach(({ path }, index) => {
    const value = results[index]?.data
    if (typeof value === "number") out[path] = value
  })
  return out
}
