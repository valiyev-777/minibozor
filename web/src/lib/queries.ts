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
  CourierEarnings,
  CourierOrder,
  Dashboard,
  AdminImage,
  AdminProduct,
  AdminVariant,
  LabelSheet,
  LocationDetail,
  Page,
  PickTask,
  ShelfMap,
  StaffOrder,
  StaffUser,
  StockCount,
  Supply,
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
  staff: ["staff"] as const,
  couriers: ["couriers"] as const,
  round: ["round"] as const,
  available: ["round", "available"] as const,
  earnings: ["earnings"] as const,
  whereIs: (q: string) => ["where-is", q] as const,
  vocab: ["vocab"] as const,
  product: (id: number) => ["products", id, "detail"] as const,
  specs: (id: number) => ["products", id, "specs"] as const,
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

export function useStaff() {
  return useQuery({
    queryKey: keys.staff,
    // Paged, because the same door lists customers too — everybody who has
    // ever signed in. Staff are the first page of it in practice.
    queryFn: () => api<Page<StaffUser>>("/admin/users?page_size=100"),
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

/** Where this model already lives — the cell the receiving form offers. */
export function useSuggestedCell(productId: number | null) {
  return useQuery({
    queryKey: ["suggest-cell", productId ?? 0],
    queryFn: () =>
      api<{ code: string }>(`/warehouse/suggest-cell?product_id=${productId}`),
    enabled: Boolean(productId),
  })
}

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
      location_code?: string
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
    mutationFn: (input: { status: string; note?: string }) =>
      api(`/admin/orders/${id}/status`, { body: input }),
    onSuccess: () => invalidate(client, [["orders"], keys.dashboard, ["pick"]]),
  })
}

export function useSetRole(userId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { role: string; note?: string }) =>
      api<StaffUser>(`/admin/users/${userId}/role`, { method: "PATCH", body: input }),
    onSuccess: () => invalidate(client, [keys.staff, keys.couriers]),
  })
}

export function useWriteCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { slug: string; name: string; parent_slug?: string | null }) =>
      api<AdminCategory>("/admin/categories", { body: input }),
    onSuccess: () => invalidate(client, [keys.categories]),
  })
}

export function useBuildPickTask() {
  const client = useQueryClient()
  return useMutation({
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
