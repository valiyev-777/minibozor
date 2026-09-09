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
  AdminImage,
  AdminProduct,
  AdminVariant,
  LabelSheet,
  LocationDetail,
  Page,
  PickTask,
  PutawayLine,
  ShelfMap,
  StockCount,
  Supply,
  WhereIs,
} from "@/lib/types"

export const keys = {
  locations: ["locations"] as const,
  location: (code: string) => ["locations", code] as const,
  putaway: ["putaway"] as const,
  supplies: (status?: string) => ["supplies", status ?? "all"] as const,
  supply: (id: number) => ["supplies", id] as const,
  pick: (status?: string) => ["pick", status ?? "all"] as const,
  pickTask: (id: number) => ["pick", id] as const,
  count: (id: number) => ["counts", id] as const,
  products: (query: string, status: string) => ["products", query, status] as const,
  variants: (productId: number) => ["products", productId, "variants"] as const,
  images: (productId: number) => ["products", productId, "images"] as const,
  labels: (what: string) => ["labels", what] as const,
  categories: ["categories"] as const,
  whereIs: (q: string) => ["where-is", q] as const,
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

export function usePutawayQueue() {
  return useQuery({
    queryKey: keys.putaway,
    queryFn: () => api<PutawayLine[]>("/warehouse/putaway"),
    refetchInterval: 30_000,
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

export function useProducts(query: string, status: string) {
  return useQuery({
    queryKey: keys.products(query, status),
    queryFn: () => {
      const search = new URLSearchParams({ page_size: "30" })
      if (query.trim()) search.set("q", query.trim())
      if (status) search.set("status", status)
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

// ------------------------------------------------------------------- writes

/** Everything the room's own screens read. One write moves several of them. */
function roomKeys() {
  return [keys.locations, keys.putaway, ["pick"], ["supplies"]]
}

export function usePutAway() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: { variant_id: number; qty: number; code: string }) =>
      api<LocationDetail>("/warehouse/putaway", {
        body: input,
        idempotencyKey: idempotencyKey(),
      }),
    onSuccess: () => invalidate(client, roomKeys()),
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

export function useSortRun(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (input: {
      lines: { variant_id: number; quantity: number; unit_cost: number }[]
      place?: string
      transport_cost?: number
      note?: string
    }) =>
      api<Supply>(`/warehouse/supplies/${id}/lines`, {
        method: "PUT",
        body: input,
      }),
    onSuccess: () => invalidate(client, [["supplies"]]),
  })
}

export function useReceiveRun(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api<Supply>(`/warehouse/supplies/${id}/receive`, { method: "POST" }),
    onSuccess: () => invalidate(client, [...roomKeys(), ["products"]]),
  })
}

export function useCancelRun(id: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (reason: string) =>
      api<Supply>(`/warehouse/supplies/${id}/cancel`, { body: { reason } }),
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
    onSuccess: () => invalidate(client, [["products"]]),
  })
}

export function usePublish(productId: number) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (status: "active" | "draft" | "archived") =>
      api<AdminProduct>(`/admin/products/${productId}/status`, { body: { status } }),
    onSuccess: () => invalidate(client, [["products"]]),
  })
}

function invalidate(
  client: ReturnType<typeof useQueryClient>,
  keyList: readonly (readonly unknown[])[],
) {
  for (const key of keyList) void client.invalidateQueries({ queryKey: key })
}
