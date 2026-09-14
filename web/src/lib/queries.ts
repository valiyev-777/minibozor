/**
 * Every read and write this app makes, as hooks.
 *
 * Two rules hold the file together.
 *
 * **A key names a thing, not a screen.** `["locations"]` is the room; three
 * screens read it and one write invalidates it for all of them. Keys named
 * after screens are how a putaway on one tab leaves a stale shelf map on
 * another.
 *
 * **A mutation says what it moved.** Every one lists the keys it makes stale,
 * beside itself, rather than leaving each caller to remember — a caller that
 * forgets shows somebody a figure that is wrong in the direction of "there is
 * more than there is", which is the direction that oversells.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query"

import { api, idempotencyKey } from "@/lib/api"
import type {
  AdminCategory,
  AuditRow,
  Bucket,
  CustomersReport,
  MoneyReport,
  OperationsReport,
  ProductsReport,
  SalesReport,
  StockReport,
  CellRemoved,
  Rack,
  CourierEarnings,
  CourierOrder,
  CustomerDetail,
  CustomerRow,
  Dashboard,
  AdminImage,
  AdminProduct,
  AdminVariant,
  LabelSheet,
  LocationDetail,
  Page,
  PickTask,
  OrderDetail,
  PickWaiting,
  PickupRun,
  PutawayPlan,
  Reason,
  Shelf,
  StaffReturn,
  StaffSlot,
  ShelfMap,
  StaffMember,
  StaffOrder,
  StaffUser,
  StockCount,
  Supply,
  UserRole,
  AdminProductDetail,
  Pile,
  PileSize,
  Spec,
  Vocab,
  WhereIs,
} from "@/lib/types"

export const keys = {
  locations: ["locations"] as const,
  location: (code: string) => ["locations", code] as const,
  supplies: (status?: string) => ["supplies", status ?? "all"] as const,
  supply: (id: number) => ["supplies", id] as const,
  pick: (status?: string) => ["pick", status ?? "all"] as const,
  pickWaiting: ["pick", "waiting"] as const,
  pickTask: (id: number) => ["pick", id] as const,
  count: (id: number) => ["counts", id] as const,
  products: (query: string, status: string, stock = "") =>
    ["products", query, status, stock] as const,
  variants: (productId: number) => ["products", productId, "variants"] as const,
  images: (productId: number) => ["products", productId, "images"] as const,
  labels: (what: string) => ["labels", what] as const,
  categories: ["categories"] as const,
  dashboard: ["dashboard"] as const,
  orders: (status: string) => ["orders", status] as const,
  /** Colleagues. One key for the list, whatever is being asked of it — the
   *  query string is part of *which* rows, not of what the thing is. */
  staff: ["staff"] as const,
  staffList: (query: string) => ["staff", "list", query] as const,
  /** Any account at all, by phone. A lookup, and a different thing from the
   *  staff directory — promoting somebody makes both stale. */
  accounts: (query: string) => ["accounts", query] as const,
  customers: (query: string) => ["customers", query] as const,
  customer: (id: number) => ["customers", id] as const,
  audit: (query: string) => ["audit", query] as const,
  couriers: ["couriers"] as const,
  round: ["round"] as const,
  available: ["round", "available"] as const,
  roundDone: ["round", "done"] as const,
  earnings: ["earnings"] as const,
  whereIs: (q: string) => ["where-is", q] as const,
  vocab: ["vocab"] as const,
  product: (id: number) => ["products", id, "detail"] as const,
  specs: (id: number) => ["products", id, "specs"] as const,
  /** One key per report per period. The period is part of *which* numbers,
   *  not of what the thing is — but it is also the only thing that changes
   *  between two views of the same report, so it belongs in the key. */
  report: (name: string, search: string) => ["reports", name, search] as const,
}

/**
 * The period every report shares, as a query string.
 *
 * Built here rather than in six screens: `from_day`, `to_day` and `bucket` are
 * the same three parameters on all six doors, and a screen that spelled one
 * of them differently would silently get the server's default month instead
 * of what the control on screen says.
 */
export type ReportQuery = {
  from: string
  to: string
  bucket: Bucket
  /** Extra parameters one report has and the others do not — the lapsed
   *  window, the dead-stock window. */
  extra?: Record<string, string | number>
}

export function reportSearch(period: ReportQuery): string {
  const search = new URLSearchParams({
    from_day: period.from,
    to_day: period.to,
    bucket: period.bucket,
  })
  for (const [name, value] of Object.entries(period.extra ?? {})) {
    search.set(name, String(value))
  }
  return search.toString()
}

// --------------------------------------------------------------------- reads

export function useShelfMap() {
  return useQuery({
    queryKey: keys.locations,
    queryFn: () => api<ShelfMap>("/warehouse/locations"),
    // The room is being changed by other people while it is on screen; ten
    // seconds is short enough that a stale cell is never the reason somebody
    // walks to the wrong shelf.
    refetchInterval: 30_000,
  })
}

export function useLocation(code: string | null) {
  return useQuery({
    queryKey: keys.location(code ?? ""),
    queryFn: () => api<LocationDetail>(`/warehouse/locations/${code}`),
    enabled: Boolean(code),
  })
}

export function useWhereIs(q: string) {
  return useQuery({
    queryKey: keys.whereIs(q),
    queryFn: () => api<WhereIs[]>(`/warehouse/where-is?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length > 1,
  })
}

export function useVocab() {
  return useQuery({
    queryKey: keys.vocab,
    queryFn: () => api<Vocab>("/warehouse/vocab"),
    // The chips grow as goods come through the door, and a stale list is a
    // brand somebody has to type a second time. Cheap query, long enough.
    staleTime: 60_000,
  })
}

export function useSupplies(status?: string) {
  return useQuery({
    queryKey: keys.supplies(status),
    queryFn: () =>
      api<Supply[]>(`/warehouse/supplies${status ? `?status=${status}` : ""}`),
  })
}

export function useSupply(id: number | null) {
  return useQuery({
    queryKey: keys.supply(id ?? 0),
    queryFn: () => api<Supply>(`/warehouse/supplies/${id}`),
    enabled: Boolean(id),
  })
}

export function usePickQueue(status?: string) {
  return useQuery({
    queryKey: keys.pick(status),
    queryFn: () =>
      api<PickTask[]>(`/warehouse/pick${status ? `?status=${status}` : ""}`),
    refetchInterval: 30_000,
  })
}

/** Orders nobody has begun. The front of the picker's board. */
export function usePickWaiting() {
  return useQuery({
    queryKey: keys.pickWaiting,
    queryFn: () => api<PickWaiting[]>("/warehouse/pick/waiting"),
    refetchInterval: 30_000,
  })
}

export function usePickTask(id: number | null) {
  return useQuery({
    queryKey: keys.pickTask(id ?? 0),
    queryFn: () => api<PickTask>(`/warehouse/pick/${id}`),
    enabled: Boolean(id),
  })
}

export function useCount(id: number | null) {
  return useQuery({
    queryKey: keys.count(id ?? 0),
    queryFn: () => api<StockCount>(`/warehouse/counts/${id}`),
    enabled: Boolean(id),
  })
}

export function useLabels(params: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.labels(params),
    queryFn: () => api<LabelSheet>(`/warehouse/labels?${params}`),
    enabled,
  })
}

export function useProducts(query: string, status: string, stock = "") {
  return useQuery({
    queryKey: keys.products(query, status, stock),
    queryFn: () => {
      const search = new URLSearchParams({ page_size: "30" })
      if (query.trim()) search.set("q", query.trim())
      if (status) search.set("status", status)
      // `out` is a live card with an empty cell, `low` one nearly empty. The
      // dashboard's tiles land here with it already set.
      if (stock) search.set("stock", stock)
      return api<Page<AdminProduct>>(`/admin/products?${search}`)
    },
  })
}

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: () => api<AdminCategory[]>("/admin/categories"),
    // The tree changes when somebody adds a category, which is rare and
    // deliberate; refetching it on every focus is a request that never
    // answers differently.
    staleTime: 5 * 60_000,
  })
}

export function useVariants(productId: number | null) {
  return useQuery({
    queryKey: keys.variants(productId ?? 0),
    queryFn: () => api<AdminVariant[]>(`/admin/products/${productId}/variants`),
    enabled: Boolean(productId),
  })
}

export function useProduct(productId: number | null) {
  return useQuery({
    queryKey: keys.product(productId ?? 0),
    queryFn: () => api<AdminProductDetail>(`/admin/products/${productId}`),
    enabled: Boolean(productId),
  })
}

export function useSpecs(productId: number | null) {
  return useQuery({
    queryKey: keys.specs(productId ?? 0),
    queryFn: () => api<Spec[]>(`/admin/products/${productId}/specs`),
    enabled: Boolean(productId),
  })
}

export function useImages(productId: number | null) {
  return useQuery({
    queryKey: keys.images(productId ?? 0),
    queryFn: () => api<AdminImage[]>(`/admin/products/${productId}/images`),
    enabled: Boolean(productId),
  })
}

/** A read whose result is only wanted once, on demand — a search box's Enter. */
export function useOnDemand<T>(
  key: readonly unknown[],
  path: string,
  options?: Partial<UseQueryOptions<T>>,
) {
  return useQuery({
    queryKey: key,
    queryFn: () => api<T>(path),
    enabled: false,
    ...options,
  } as UseQueryOptions<T>)
}

export function useDashboard(enabled = true) {
  return useQuery({
    queryKey: keys.dashboard,
    queryFn: () => api<Dashboard>("/admin/dashboard"),
    // The rail asks for this to put a count beside a menu item, and a courier
    // is not allowed to read it — so it is off unless somebody actually wants
    // the figure. Otherwise every page load a courier makes is a 403.
    enabled,
    // The screen that stays open all day, on a shop several people are
    // changing.
    refetchInterval: 60_000,
  })
}

/**
 * One report, over the period in the address bar.
 *
 * `placeholderData` holds the previous answer on screen while a new period is
 * being fetched, so changing the dates redraws the figures rather than
 * blanking the page and dropping it back to a skeleton — the charts keep
 * their layout and nothing jumps.
 */
function useReport<T>(name: string, period: ReportQuery, enabled = true) {
  const search = reportSearch(period)
  return useQuery({
    queryKey: keys.report(name, search),
    queryFn: () => api<T>(`/admin/reports/${name}?${search}`),
    enabled,
    placeholderData: (previous) => previous,
  })
}

export function useSalesReport(period: ReportQuery, enabled = true) {
  return useReport<SalesReport>("sales", period, enabled)
}

export function useMoneyReport(period: ReportQuery, enabled = true) {
  return useReport<MoneyReport>("money", period, enabled)
}

export function useCustomersReport(period: ReportQuery, enabled = true) {
  return useReport<CustomersReport>("customers", period, enabled)
}

export function useProductsReport(period: ReportQuery, enabled = true) {
  return useReport<ProductsReport>("products", period, enabled)
}

export function useStockReport(period: ReportQuery, enabled = true) {
  return useReport<StockReport>("stock", period, enabled)
}

export function useOperationsReport(period: ReportQuery, enabled = true) {
  return useReport<OperationsReport>("operations", period, enabled)
}

export function useOrders(status: string) {
  return useQuery({
    queryKey: keys.orders(status),
    queryFn: () => {
      const search = new URLSearchParams({ page_size: "40" })
      if (status) search.set("status", status)
      return api<Page<StaffOrder>>(`/admin/orders?${search}`)
    },
    refetchInterval: 60_000,
  })
}

/* ------------------------------------------------------------------ people */

/**
 * The people who work here — and nobody who buys here.
 *
 * The screen used to read `/admin/users`, which answers with every account in
 * the shop, so "Xodimlar" was a list of four thousand shoppers with the five
 * colleagues somewhere in it. `/admin/staff` is the question actually being
 * asked, and it is paged on the server because the filters are the server's:
 * a role, a state and a needle it looks for in both the name and the number.
 */
export function useStaffList(input: {
  q?: string
  role?: string
  active?: string
  page?: number
  size?: number
}) {
  const search = new URLSearchParams({
    page: String(input.page ?? 1),
    page_size: String(input.size ?? 20),
  })
  if (input.q?.trim()) search.set("q", input.q.trim())
  if (input.role) search.set("role", input.role)
  if (input.active) search.set("active", input.active)
  const query = search.toString()

  return useQuery({
    queryKey: keys.staffList(query),
    queryFn: () => api<Page<StaffMember>>(`/admin/staff?${query}`),
  })
}

/**
 * Every account there is, customers included — the lookup for "I have a
 * number and I do not know whose it is".
 *
 * Deliberately not a screen. It is enabled only once somebody has typed
 * enough to be looking for a particular person, because the whole shop's
 * account list is not an answer to anything.
 */
export function useAccountLookup(q: string) {
  const needle = q.trim()
  return useQuery({
    queryKey: keys.accounts(needle),
    queryFn: () =>
      api<Page<StaffUser>>(
        `/admin/users?page_size=10&q=${encodeURIComponent(needle)}`,
      ),
    enabled: needle.length > 2,
  })
}

/** The buyers, with the four figures somebody reads before ringing them. */
export function useCustomers(input: {
  q?: string
  ordering?: string
  page?: number
  size?: number
}) {
  const search = new URLSearchParams({
    ordering: input.ordering || "recent",
    page: String(input.page ?? 1),
    page_size: String(input.size ?? 20),
  })
  if (input.q?.trim()) search.set("q", input.q.trim())
  const query = search.toString()

  return useQuery({
    queryKey: keys.customers(query),
    queryFn: () => api<Page<CustomerRow>>(`/admin/customers?${query}`),
  })
}

/** One customer, whole — opened while they are on the telephone. */
export function useCustomer(id: number | null) {
  return useQuery({
    queryKey: keys.customer(id ?? 0),
    queryFn: () => api<CustomerDetail>(`/admin/customers/${id}`),
    enabled: Boolean(id),
  })
}

/**
 * The trail: who changed what, and when.
 *
 * Every filter here is a question somebody asks out loud — what happened to
 * order 412, what did the new lad do on his first day, who has been changing
 * prices. `action` matches on a prefix, so `user` is the whole family.
 */
export function useAudit(
  input: {
    actor_id?: string
    entity?: string
    entity_id?: string
    action?: string
    q?: string
    from_day?: string
    to_day?: string
    page?: number
    size?: number
  },
  enabled = true,
) {
  const search = new URLSearchParams({
    page: String(input.page ?? 1),
    page_size: String(input.size ?? 20),
  })
  for (const name of [
    "actor_id",
    "entity",
    "entity_id",
    "action",
    "q",
    "from_day",
    "to_day",
  ] as const) {
    const value = input[name]?.trim()
    if (value) search.set(name, value)
  }
  const query = search.toString()

  return useQuery({
    queryKey: keys.audit(query),
    queryFn: () => api<Page<AuditRow>>(`/admin/audit?${query}`),
    enabled,
  })
}

export function useCouriers() {
  return useQuery({
    queryKey: keys.couriers,
    queryFn: () => api<StaffUser[]>("/admin/couriers"),
  })
}

export function useMyRound() {
  return useQuery({
    queryKey: keys.round,
    queryFn: () => api<CourierOrder[]>("/courier/orders"),
    refetchInterval: 60_000,
  })
}

/**
 * The stops this courier has finished — which is a different list from the
 * round, and was being asked of the round.
 *
 * A delivered parcel **leaves** `/courier/orders`: that door answers with
 * what is in the van, filtered to `packing` and `shipped`. The history screen
 * read it and filtered for "not shipped", so the only thing it could ever
 * show was a parcel taken and not yet on the road — and a courier who had
 * delivered thirteen parcels was told "Hali yetkazilgan buyurtma yo'q" while
 * the earnings screen beside it counted all thirteen.
 *
 * `done=true` drops the status filter rather than inverting it, so this comes
 * back with the open stops in it too; the screen keeps the finished ones.
 */
export function useMyHistory() {
  return useQuery({
    queryKey: keys.roundDone,
    queryFn: () => api<CourierOrder[]>("/courier/orders?done=true"),
  })
}

export function useAvailableOrders() {
  return useQuery({
    queryKey: keys.available,
    queryFn: () => api<CourierOrder[]>("/courier/orders/available"),
    refetchInterval: 60_000,
  })
}

export function useEarnings() {
  return useQuery({
    queryKey: keys.earnings,
    queryFn: () => api<CourierEarnings>("/courier/earnings"),
  })
}

// ------------------------------------------------------------------- writes

/** Everything the room's own screens read. One write moves several of them. */
function roomKeys() {
  return [keys.locations, ["pick"], ["supplies"]]
}

/**
 * Carry a quantity from where it is to a cell.
 *
 * The only way a mis-shelved pile gets found again. Goods land on a shelf in
 * one action at the receiving desk, which is right — but it means the cell is
 * typed once, and a wrong one leaves the ledger and the room disagreeing with
 * nobody to notice.
 */
export function useMove() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Ko'chirildi" },
    mutationFn: (input: {
      variant_id: number
      qty: number
      from_code: string
      to_code: string
    }) =>
      api<LocationDetail>("/warehouse/move", {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, roomKeys()),
  })
}

/**
 * Carry everything standing in one cell over to another, in one action.
 *
 * A cell holds one model in four sizes, and tidying it through [[useMove]]
 * was four requests and four chances to be interrupted halfway — which leaves
 * the model in two cells, the exact mess the move was meant to clear up.
 *
 * No quantities: what moves is what is there, read inside the transaction
 * that moves it. A count the screen read some seconds ago is a count a picker
 * may already have spoiled. `variantIds` narrows it to some of the lines.
 */
export function useMoveCell() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Yacheyka ko'chirildi" },
    mutationFn: (input: {
      from_code: string
      to_code: string
      variant_ids?: number[]
    }) =>
      api<LocationDetail>("/warehouse/move-cell", {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, roomKeys()),
  })
}

/**
 * Where these N pieces would go if nobody thought about it.
 *
 * What the receiving screen asks once it knows the card and the count. It
 * supersedes [[useSuggestedCell]] there: that answers with one code, which
 * may be a cell with room for four more pairs, and leaves the person to place
 * the other forty by eye.
 */
export function usePutawayPlan(productId: number | null, quantity: number) {
  return useQuery({
    queryKey: ["putaway-plan", productId ?? 0, quantity],
    queryFn: () =>
      api<PutawayPlan>(
        `/warehouse/putaway-plan?product_id=${productId}&quantity=${quantity}`,
      ),
    enabled: Boolean(productId) && quantity > 0,
    // The room moves under it — a picker empties a cell while somebody is
    // still counting a sack — and a stale plan sends goods to a cell that
    // filled up in the meantime.
    staleTime: 30_000,
  })
}

// `useSuggestedCell` stood here, wrapping `GET /warehouse/suggest-cell`: one
// code, the first cell in walk order that already holds this model. The
// receiving screen was its only caller and now asks `usePutawayPlan` instead,
// which answers the same question with the quantity in it — where do *these
// forty* go, not where does this model live. The endpoint stays; it is a
// cheaper question and the next screen that has no quantity to hand will want
// it, and it will want a fresh hook rather than this one's stale key.

export function useStartRun() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      sacks: number
      place: string
      transport_cost: number
      note?: string
    }) => api<Supply[]>("/warehouse/supplies", { body: input }),
    onSuccess: () => invalidate(client, [["supplies"]]),
  })
}




export function useTakeTask() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      api<PickTask>(`/warehouse/pick/${id}/take`, {
        method: "POST",
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, [["pick"]]),
  })
}

/**
 * Start picking an order: build its task, then take it.
 *
 * Two calls because they are two facts — the room is read to make the walk
 * list, and then this picker's name goes on it — but one tap, because at the
 * bench they are one decision. Building is idempotent, so an order the office
 * had already put on the board comes back as the task that exists rather than
 * a second one.
 */
export function useStartPicking() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (orderId: number) => {
      const task = await api<PickTask>(`/warehouse/pick/orders/${orderId}`, {
        method: "POST",
      })
      return api<PickTask>(`/warehouse/pick/${task.id}/take`, {
        method: "POST",
        idempotencyKey: idempotencyKey(),
      })
    },
    onSuccess: () => invalidate(client, [["pick"], ["orders"]]),
  })
}

export function usePickLine(taskId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { lineId: number; qty: number }) =>
      api<PickTask>(`/warehouse/pick/${taskId}/lines/${input.lineId}`, {
        body: { qty: input.qty },
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, roomKeys()),
  })
}

export function useCompleteTask(taskId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api<PickTask>(`/warehouse/pick/${taskId}/complete`, {
        method: "POST",
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, [...roomKeys(), ["orders"]]),
  })
}

export function useStartCount() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (code: string) =>
      api<StockCount>("/warehouse/counts", { body: { code } }),
    onSuccess: () => invalidate(client, [["counts"]]),
  })
}

export function useSubmitCount(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Sanash yopildi" },
    mutationFn: (input: {
      lines: { variant_id: number; counted_qty: number }[]
      note?: string
    }) =>
      api<StockCount>(`/warehouse/counts/${id}/submit`, {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, [...roomKeys(), ["counts"]]),
  })
}

// ------------------------------------------------------- writing a card

/**
 * A pile off the van: booked in, shelved, and labelled, in one request.
 *
 * The one write on the receiving screen. It carries an idempotency key because
 * the person tapping it is standing in a warehouse on warehouse wifi, and a
 * second tap on a slow connection must not be a second sack.
 */
export function useBookInPile() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      product_id?: number
      kind?: string
      brand?: string
      colour?: string
      title?: string
      snapshot_url?: string
      sizes: PileSize[]
      unit_cost: number
      /** One cell — or `placements`, and exactly one of the two. */
      location_code?: string
      /** The split, in units per cell, summing to the pile. The sizes are
       *  allocated across it in order: the first cell is filled to its stated
       *  quantity, then the next. A size may straddle two cells, which is
       *  what physically happens when a sack is split. */
      placements?: { code: string; quantity: number }[]
      place?: string
      transport_cost?: number
    }) =>
      api<Pile>("/warehouse/piles", {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    // Everything this touches: the room, the receiving queue, the catalogue,
    // the publishing queue behind it, and the figures on the dashboard.
    onSuccess: () =>
      invalidate(client, [
        keys.locations,
        ["products"],
        ["supplies"],
        keys.dashboard,
        keys.vocab,
      ]),
  })
}

/** The reminder closed: its goods went in as piles, not as lines. */
export function useSackSorted(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<Supply>(`/warehouse/supplies/${id}/sorted`, { body: {} }),
    onSuccess: () => invalidate(client, [["supplies"], keys.dashboard]),
  })
}

/** One selling price for every cell of a card — what publishing needs. */
export function usePriceCard(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Narx saqlandi" },
    mutationFn: (input: { price: number; old_price?: number | null; colour?: string }) =>
      api<AdminVariant[]>(`/admin/products/${productId}/price`, { body: input }),
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

/**
 * The words on a card: where it is filed, what it is called, what it says.
 *
 * One door for all of them because they are one job — somebody looking at the
 * goods writing the shop window — and splitting it per field would mean a
 * request per keystroke or a form that saves in pieces.
 */
export function useFileCard(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Kategoriya saqlandi" },
    mutationFn: (input: {
      category_slug?: string
      title?: string
      subtitle?: string
      description?: string
      warranty?: string | null
      badge?: string | null
    }) =>
      api<AdminProductDetail>(`/admin/products/${productId}`, {
        method: "PATCH",
        body: input,
      }),
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

/**
 * A card gone, or archived where it has history.
 *
 * The server decides which: a card nothing has happened to is a piece of
 * writing somebody got wrong, and one with a movement or an order against it is
 * part of what happened here. The message says which it did.
 */
export function useDeleteCard(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Karta o'chirildi" },
    mutationFn: () =>
      api<{ message: string }>(`/admin/products/${productId}`, { method: "DELETE" }),
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

/**
 * Take everything off a cell, or out of the whole room.
 *
 * The one write here that makes stock disappear rather than move, so it asks
 * for a reason and the server refuses it to anybody but the office.
 */
export function useEmptyStock() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Hisobdan chiqarildi" },
    mutationFn: (input: { code?: string; reason: string }) =>
      api<{ moved: number; units: number; cells: number }>(
        "/warehouse/stock/empty",
        { body: input },
      ),
    onSuccess: () =>
      invalidate(client, [keys.locations, ["products"], keys.dashboard, ["supplies"]]),
  })
}

/** The specification table, replaced whole — the apps read it as a table. */
export function useWriteSpecs(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Xususiyatlar saqlandi" },
    mutationFn: (specs: Spec[]) =>
      api<Spec[]>(`/admin/products/${productId}/specs`, {
        method: "PUT",
        body: { specs },
      }),
    onSuccess: () => invalidate(client, [["products"]]),
  })
}

export function useCreateProduct() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      sku: string
      title: string
      category_slug: string
      price: number
    }) => api<AdminProduct>("/admin/products", { body: input }),
    onSuccess: () => invalidate(client, [["products"]]),
  })
}

export function useRetireVariant(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Saqlandi" },
    mutationFn: (input: { variantId: number; retired: boolean }) =>
      api<AdminVariant>(
        `/admin/products/${productId}/variants/${input.variantId}/retired`,
        { body: { retired: input.retired } },
      ),
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

export function useSetGrid(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "To'r saqlandi" },
    mutationFn: (input: {
      colours: { colour: string; hex: string }[]
      sizes: string[]
      price: number
    }) =>
      api<AdminVariant[]>(`/admin/products/${productId}/variants`, {
        method: "PUT",
        body: input,
      }),
    onSuccess: () => invalidate(client, [["products"]]),
  })
}

export function useAddImage(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Rasm qo'shildi" },
    mutationFn: (input: { url: string; colour: string }) =>
      api<AdminImage[]>(`/admin/products/${productId}/images`, { body: input }),
    // The dashboard too: a photograph is one of the three things holding a
    // card back, and the count in the rail is the only reason the queue gets
    // worked. A badge that still says 1 after you have fixed the one is a
    // badge people stop believing.
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

export function usePublish(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Holat o'zgardi" },
    mutationFn: (status: "active" | "draft" | "archived") =>
      api<AdminProduct>(`/admin/products/${productId}/status`, { body: { status } }),
    onSuccess: () => invalidate(client, [["products"], keys.dashboard]),
  })
}

// -------------------------------------------------------------- the last mile

/** Everything a courier's own screens read. */
function roundKeys() {
  return [keys.round, keys.available, keys.earnings]
}

export function useTakeOrder() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      api<CourierOrder>(`/courier/orders/${id}/take`, {
        method: "POST",
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, roundKeys()),
  })
}

export function useDeliver(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      recipient_name: string
      cash_collected: number
      note?: string
    }) =>
      api<CourierOrder>(`/courier/orders/${id}/deliver`, {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, [...roundKeys(), ["orders"]]),
  })
}

export function useFailed(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (reason: string) =>
      api<CourierOrder>(`/courier/orders/${id}/failed`, {
        body: { reason },
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, [...roundKeys(), ["orders"]]),
  })
}

export function useMoveOrder(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Buyurtma holati o'zgardi" },
    mutationFn: (input: { status: string; note?: string }) =>
      api(`/admin/orders/${id}/status`, { body: input }),
    onSuccess: () => invalidate(client, [["orders"], keys.dashboard, ["pick"]]),
  })
}

/* ---------------------------------------------------------- hiring and firing */

/** Everything a change to one account is visible in: the directory, the
 *  buyers' list (a promotion takes somebody out of it), the courier picker
 *  the order queue uses, and the trail that just gained a row. */
function peopleKeys() {
  return [keys.staff, ["accounts"], ["customers"], keys.couriers, ["audit"]]
}

/**
 * Appoint somebody, by the only thing anybody knows about them: a number.
 *
 * The account is **made** if the number is unknown, so a courier taken on at
 * the counter on Monday is set up before they have ever opened the app. A
 * customer is promoted in place and keeps their id, their orders and their
 * basket. Somebody who already works here is refused with a sentence naming
 * the job they hold — which is the answer the person filling in the form
 * needs, rather than a warehouse manager quietly turned into a courier.
 */
export function useAppointStaff() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Xodim qo'shildi" },
    mutationFn: (input: {
      phone: string
      full_name: string
      role: UserRole
      note?: string
    }) => api<StaffMember>("/admin/staff", { body: input }),
    onSuccess: () => invalidate(client, peopleKeys()),
  })
}

/**
 * Change what somebody may do — with the reason.
 *
 * `note` is the field the audit trail has always had and the old screen never
 * sent: five role buttons in a row, one click, no record of why. A privilege
 * change is the thing asked about months later, so the note is the point of
 * the door rather than an extra on it.
 */
export function useSetRole(userId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Rol berildi" },
    mutationFn: (input: { role: UserRole; note?: string }) =>
      api<StaffUser>(`/admin/users/${userId}/role`, { method: "PATCH", body: input }),
    onSuccess: () => invalidate(client, peopleKeys()),
  })
}

/**
 * Somebody left, or somebody came back.
 *
 * Not a delete: their orders, the addresses they were delivered to and every
 * audit row naming them stay where they are. What changes is that the guard
 * stops letting them in. Refused for the last live admin, by the server.
 */
export function useSetActive(userId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Saqlandi" },
    mutationFn: (input: { active: boolean; note?: string }) =>
      api<StaffMember>(`/admin/users/${userId}/active`, { body: input }),
    onSuccess: () => invalidate(client, peopleKeys()),
  })
}

/** Correct a name taken down over the telephone, or an email with a letter
 *  missing. Two fields and no more — the role has its own door, and the
 *  language and the notification switches are the account holder's own. */
export function useEditUser(userId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Saqlandi" },
    mutationFn: (input: { full_name?: string; email?: string }) =>
      api<StaffMember>(`/admin/users/${userId}`, { method: "PATCH", body: input }),
    onSuccess: () => invalidate(client, peopleKeys()),
  })
}

export function useWriteCategory() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Kategoriya saqlandi" },
    mutationFn: (input: { slug: string; name: string; parent_slug?: string | null }) =>
      api<AdminCategory>("/admin/categories", { body: input }),
    onSuccess: () => invalidate(client, [keys.categories]),
  })
}

/**
 * Rename a category, or move it under another one.
 *
 * A category is written in a hurry — beside an open sack, by somebody filing a
 * card that has nowhere to go — so the typo is the normal case rather than the
 * unlucky one. The slug is not editable on purpose: it is what the apps' links
 * and every filed card point at, and changing it would be a rename that breaks
 * what is already in somebody's hands. The name is what anybody reads.
 */
export function useEditCategory(slug: string) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Kategoriya saqlandi" },
    mutationFn: (input: {
      name?: string
      subtitle?: string
      parent_slug?: string | null
    }) =>
      api<AdminCategory>(`/admin/categories/${slug}`, {
        method: "PATCH",
        body: input,
      }),
    // The words are on the cards too — a product list shows what it is filed
    // under, so a rename that only refreshed this screen would leave the other
    // one saying the old thing until somebody reloaded.
    onSuccess: () => invalidate(client, [keys.categories, ["products"]]),
  })
}

/**
 * Throw a category away, which the server allows only while nothing points at
 * it — no cards filed under it and no categories beneath it.
 *
 * The refusal is the useful half: deleting one with cards in it would leave
 * them filed under a row that is not there, and a listing that answers with
 * nothing. So the screen says why rather than offering a button that fails.
 */
export function useDeleteCategory(slug: string) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Kategoriya o'chirildi" },
    mutationFn: () =>
      api<{ message: string }>(`/admin/categories/${slug}`, { method: "DELETE" }),
    onSuccess: () => invalidate(client, [keys.categories, ["products"]]),
  })
}

/**
 * Build a shelf unit: a letter and a grid of cells.
 *
 * The racks were always data — three units of four by four is where the owner
 * starts, not where they end — but adding a fourth meant editing a list in the
 * source and running the seed. A shelf that goes up on a Saturday should not
 * need a deployment on the Monday.
 */
export function useAddRack() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Javon qo'shildi" },
    mutationFn: (input: {
      rack: string
      columns: number
      rows: number
      capacity?: number
    }) => api<Rack>("/warehouse/racks", { body: input }),
    // The map, and the dashboard's count of how full the room is.
    onSuccess: () => invalidate(client, [keys.locations, keys.dashboard]),
  })
}

/**
 * Bolt cells onto a rack that is already standing.
 *
 * The shape it should **have**, not a delta: somebody is in front of the
 * shelf counting columns, and "A is five by four now" is what they can say
 * without knowing what the system thought A was. Sending it twice adds
 * nothing the second time. Nothing is ever removed — a smaller shape is not
 * a demolition, it adds nothing and says so.
 */
export function useExtendRack(rack: string) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Javon kengaytirildi" },
    mutationFn: (input: { columns: number; rows: number; capacity?: number }) =>
      api<Rack>(`/warehouse/racks/${rack}/cells`, { body: input }),
    onSuccess: () => invalidate(client, [keys.locations, keys.dashboard]),
  })
}

/**
 * Take a cell out of the room, for good.
 *
 * This was a boolean — `active: false` to retire, `active: true` to restore —
 * and the boolean was the problem. Retiring flipped a flag: the row stayed,
 * the code stayed, and the map drew the dead cell struck through in the grid
 * with a way back on it, so a rack grown to 6×4 by a typo showed two columns
 * of crossed-out tiles for ever. Correct about the ledger, and a lie about
 * the room — there is no fifth column standing in the shop to point at.
 *
 * So it is a delete, and the server decides how literally it can afford to be
 * one: the row goes when nothing in the ledger names the cell, and is kept
 * invisibly when a movement or a stocktake does. `erased` says which
 * happened, and no screen has to care — both are gone from the map.
 *
 * The server refuses it while the cell is holding anything and says what to
 * do instead; it refuses a staging area outright. Both come back as a
 * sentence to show, not a code to interpret.
 *
 * The way back is [[useExtendRack]] — asking the rack for that column again —
 * and not a button on a cell that is no longer drawn.
 */
export function useRemoveCell() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Yacheyka olib tashlandi" },
    mutationFn: (input: { code: string; reason: string }) =>
      api<CellRemoved>(
        `/warehouse/cells/${input.code}?reason=${encodeURIComponent(input.reason)}`,
        { method: "DELETE" },
      ),
    // The room, the label sheet's idea of what to print, and the dashboard's
    // of how full the shop is.
    onSuccess: () => invalidate(client, [keys.locations, ["labels"], keys.dashboard]),
  })
}

/**
 * Take a whole column or row of cells out of the room, in one act.
 *
 * The same door as [[useRemoveCell]], walked once per cell. A shelf is
 * dismantled a column at a time — somebody unbolts the planks and the rack is
 * four wide again — and asking the office to open four tiles and type the same
 * reason into each is asking for three of them to be done and the fourth
 * forgotten, which leaves the rack carrying a dead cell for ever.
 *
 * **One at a time, and a refusal stops nothing after it.** A column where one
 * cell still holds forty pairs gives up that cell and removes the other three,
 * and says which one it could not take — because the alternative is a column
 * that is half gone and a screen that claims it is all gone. In order, too, so
 * the audit trail reads the way the cells were named.
 *
 * The refusals come back as the server's own sentences: a cell with goods in
 * it already says what to do instead, and the caller's job is to show that,
 * not to work out what went wrong.
 */
export function useRemoveCells() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Yacheykalar olib tashlandi" },
    mutationFn: async (input: { codes: string[]; reason: string }) => {
      const done: string[] = []
      const refused: { code: string; why: string }[] = []
      for (const code of input.codes) {
        try {
          await api<CellRemoved>(
            `/warehouse/cells/${code}?reason=${encodeURIComponent(input.reason)}`,
            { method: "DELETE" },
          )
          done.push(code)
        } catch (error) {
          refused.push({
            code,
            why: error instanceof Error ? error.message : String(error),
          })
        }
      }
      return { done, refused }
    },
    onSuccess: () => invalidate(client, [keys.locations, ["labels"], keys.dashboard]),
  })
}

// ------------------------------------------------------------------- returns

/** Everything that touches a return: the queue itself, the order it came
 *  from, the room it lands in, and the dashboard. */
function returnKeys() {
  return [["returns"], ["orders"], keys.locations, keys.dashboard] as const
}

/**
 * The queue of people waiting for an answer.
 *
 * `awaiting: "inspection"` is its own question and not a status: a parcel
 * that has arrived and nobody has opened is a distinct piece of work, and it
 * is invisible on the status axis because inspecting is orthogonal to
 * deciding. The server sorts what is waiting oldest-first and everything else
 * newest-first, which is the difference between a queue and a history.
 */
export function useReturns(status: string, awaiting = "") {
  return useQuery({
    queryKey: ["returns", status, awaiting],
    queryFn: () => {
      const search = new URLSearchParams()
      if (status) search.set("status", status)
      if (awaiting) search.set("awaiting", awaiting)
      const query = search.toString()
      return api<StaffReturn[]>(`/admin/returns${query ? `?${query}` : ""}`)
    },
  })
}

export function useReturn(id: number | null) {
  return useQuery({
    queryKey: ["returns", id ?? 0],
    queryFn: () => api<StaffReturn>(`/admin/returns/${id}`),
    enabled: Boolean(id),
  })
}

/**
 * Approve, reject or pay a return.
 *
 * `restock` has **no default** on the refund door, deliberately: a stock
 * count must not move because somebody left a field alone. A rejection's
 * reason is required and becomes the sentence the customer reads.
 */
export function useDecideReturn(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Qaror yozildi" },
    mutationFn: (input: {
      decision: "approve" | "reject" | "refund"
      reason?: string
      note?: string
      restock?: boolean
    }) => {
      const { decision, ...body } = input
      return api<StaffReturn>(`/admin/returns/${id}/${decision}`, { body })
    },
    onSuccess: () => invalidate(client, returnKeys()),
  })
}

/**
 * The warehouse opens the parcel and says whole or damaged.
 *
 * One shot — the server refuses a second look — and it is what moves the
 * goods: whole goes back towards the shelf, damaged goes to the damaged
 * corner. A different door from the office's decision on purpose: the person
 * holding the garment is not the person deciding about the money.
 */
export function useInspectReturn(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Ko'rik yozildi" },
    mutationFn: (input: { result: "ok" | "damaged"; note?: string }) =>
      api<StaffReturn>(`/warehouse/returns/${id}/inspect`, { body: input }),
    onSuccess: () => invalidate(client, returnKeys()),
  })
}

// ----------------------------------------------------------------- one order

/**
 * The order in full, which is a different question from the queue row.
 *
 * The row says where an order is; this says what happened to it — every line
 * with its frozen price, the timeline, and **every knock at the door**, which
 * is carried here and nowhere else. An operator deciding whether to give up
 * on a delivery is deciding on that list.
 */
export function useOrder(id: number | null) {
  return useQuery({
    queryKey: ["orders", id ?? 0, "detail"],
    queryFn: () => api<OrderDetail>(`/admin/orders/${id}`),
    enabled: Boolean(id),
  })
}

/** The five reasons an order is called off, in a table, translated. The panel
 *  has been writing free sentences beside them. */
export function useCancelReasons() {
  return useQuery({
    queryKey: ["reasons", "cancel"],
    queryFn: () => api<Reason[]>("/orders/reasons/cancel"),
    staleTime: 60 * 60_000,
  })
}

// ----------------------------------------------------------- delivery windows

/** Every window in a range, **including the sold-out and the past ones** —
 *  which is the whole difference from the customer's list. */
export function useSlots(fromDay: string, toDay: string) {
  return useQuery({
    queryKey: ["slots", fromDay, toDay],
    queryFn: () =>
      api<StaffSlot[]>(`/admin/delivery/slots?from_day=${fromDay}&to_day=${toDay}`),
  })
}

/**
 * Open windows across days.
 *
 * Days times windows, and **idempotent per day and hours**: a day that
 * already has that window is skipped, so "top up the next fortnight" is
 * re-runnable. It answers with only what it actually created, so an empty
 * list means everything already existed — not a failure.
 */
export function useCreateSlots() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Oynalar ochildi" },
    mutationFn: (input: {
      days: string[]
      windows: {
        start_time: string
        end_time: string
        note?: string
        price?: number
        express?: boolean
        capacity?: number
      }[]
    }) => api<StaffSlot[]>("/admin/delivery/slots", { body: input }),
    onSuccess: () => invalidate(client, [["slots"]]),
  })
}

export function useUpdateSlot(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Oyna saqlandi" },
    mutationFn: (input: {
      capacity_left?: number
      price?: number
      note?: string
      express?: boolean
    }) => api<StaffSlot>(`/admin/delivery/slots/${id}`, { method: "PATCH", body: input }),
    onSuccess: () => invalidate(client, [["slots"]]),
  })
}

// -------------------------------------------------------------- pickup runs

export function usePickups(status: string) {
  return useQuery({
    queryKey: ["pickups", status],
    queryFn: () =>
      api<PickupRun[]>(`/admin/pickups${status ? `?status=${status}` : ""}`),
  })
}

/** A round of collections. Only returns the office has **approved** may go on
 *  one, and a return already riding a live run is refused. */
export function useCreatePickup() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Reys yaratildi" },
    mutationFn: (input: {
      courier_id: number
      return_request_ids: number[]
      note?: string
    }) => api<PickupRun>("/admin/pickups", { body: input }),
    onSuccess: () => invalidate(client, [["pickups"], ["returns"]]),
  })
}

/** The warehouse says the run arrived. It moves no stock — each parcel is
 *  opened separately, because arriving and being whole are two facts. */
export function useReceivePickup(id: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Qabul qilindi" },
    mutationFn: () => api<PickupRun>(`/admin/pickups/${id}/receive`, { body: {} }),
    onSuccess: () => invalidate(client, [["pickups"], ["returns"]]),
  })
}

// ----------------------------------------------------- the catalogue's photos

/**
 * Take a photograph down.
 *
 * The door has always existed and the panel never knew the image id, so a
 * wrong photograph was permanent — and because the first picture of a colour
 * is that colour's cover, there was also no way to change a cover. Deleting
 * the last photograph of a colour on a live card **takes the card out of the
 * shop**: a card that stayed on sale because the picture was deleted rather
 * than never taken is the same grey square to a customer.
 */
export function useDeleteImage(productId: number) {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Rasm o'chirildi" },
    mutationFn: (imageId: number) =>
      api<{ message: string }>(`/admin/products/${productId}/images/${imageId}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidate(client, [keys.images(productId), ["products"]]),
  })
}

// ------------------------------------------------------------ damaged goods

/**
 * A garment that cannot be sold, off the shelf and into the damaged corner.
 *
 * Not a write-off: a torn shirt has not evaporated, it is in the corner by
 * the door, it is countable, and somebody will decide later whether it goes
 * back to the market or into a bin. The reason is required — three months on
 * it is the only thing telling damage from a miscount.
 */
export function useDamage() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Brakka o'tkazildi" },
    mutationFn: (input: { variant_id: number; quantity: number; reason: string }) =>
      api<Shelf>("/warehouse/stock/damage", { body: input }),
    onSuccess: () =>
      invalidate(client, [keys.locations, ["products"], keys.dashboard]),
  })
}

/** A sack that was never goods — a miscount at the door, a sack that went
 *  back. Not "sorted": sorted says the goods went in as piles. */
export function useCancelSupply(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (reason: string) =>
      api<Supply>(`/warehouse/supplies/${id}/cancel`, { body: { reason } }),
    onSuccess: () => invalidate(client, [["supplies"], keys.dashboard]),
  })
}

export function useBuildPickTask() {
  const client = useQueryClient()
  return useMutation({
    meta: { done: "Terishga qo'yildi" },
    mutationFn: (orderId: number) =>
      api(`/warehouse/pick/orders/${orderId}`, { method: "POST" }),
    onSuccess: () => invalidate(client, [["pick"], ["orders"]]),
  })
}

function invalidate(
  client: ReturnType<typeof useQueryClient>,
  keyList: readonly (readonly unknown[])[],
) {
  for (const key of keyList) void client.invalidateQueries({ queryKey: key })
}
