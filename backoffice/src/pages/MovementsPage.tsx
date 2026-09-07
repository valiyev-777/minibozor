import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Movement, MovementKind, MovementPage, StaffOffer } from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { MOVEMENT_KIND } from "@/lib/labels"
import { when } from "@/lib/utils"

const KEY = ["staff", "movements"]
const PAGE_SIZE = 50

const KINDS: MovementKind[] = [
  "opening",
  "intake",
  "sale",
  "cancel_return",
  "customer_return",
  "write_off",
  "count_adjustment",
  "seller_return",
]

const TONE: Record<MovementKind, "neutral" | "accent" | "good" | "warn" | "danger"> = {
  opening: "neutral",
  intake: "good",
  sale: "accent",
  cancel_return: "warn",
  customer_return: "warn",
  write_off: "danger",
  count_adjustment: "warn",
  seller_return: "danger",
}

/**
 * The ledger.
 *
 * A count that looks wrong is not an opinion — it is this list. Filters exist
 * because the question is never "what happened" in general but "what happened
 * to *this*", and the answer has to be reachable while somebody is still
 * standing in front of the shelf.
 */
export function MovementsPage() {
  const [kind, setKind] = React.useState<"" | MovementKind>("")
  const [offerId, setOfferId] = React.useState("")
  const [who, setWho] = React.useState("")
  const [since, setSince] = React.useState("")
  const [page, setPage] = React.useState(1)

  const offers = useQuery({
    queryKey: ["staff", "shelf", "offers"],
    queryFn: () => api<StaffOffer[]>("/staff/offers"),
  })

  const query = useQuery({
    queryKey: [...KEY, kind, offerId, page],
    queryFn: () =>
      api<MovementPage>("/staff/stock/movements", {
        query: {
          kind,
          offer_id: offerId ? Number(offerId) : undefined,
          page,
          page_size: PAGE_SIZE,
        },
      }),
  })

  // The person and the date are filtered here rather than asked of the API:
  // both are answers about the page in hand, and adding query parameters for
  // them would mean paging over a filter the server does not know about.
  const rows = React.useMemo(() => {
    const items = query.data?.items ?? []
    const needle = who.trim().toLowerCase()
    return items.filter((row) => {
      if (needle && !row.actor.toLowerCase().includes(needle)) return false
      if (since && row.created_at.slice(0, 10) < since) return false
      return true
    })
  }, [query.data, who, since])

  const columns: Column<Movement>[] = [
    {
      key: "when",
      header: "Qachon",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
    {
      key: "kind",
      header: "Tur",
      sortValue: (row) => row.kind,
      cell: (row) => <Badge tone={TONE[row.kind]}>{MOVEMENT_KIND[row.kind]}</Badge>,
    },
    {
      key: "quantity",
      header: "Miqdor",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.quantity,
      cell: (row) => (
        <span
          className={
            row.quantity > 0 ? "font-semibold text-good" : "font-semibold text-danger"
          }
        >
          {row.quantity > 0 ? "+" : ""}
          {row.quantity}
        </span>
      ),
    },
    {
      key: "what",
      header: "Tovar",
      sortValue: (row) => row.product_title,
      cell: (row) => (
        <>
          <span className="block max-w-64 truncate text-ink">{row.product_title}</span>
          <span className="tabular block text-[12px] text-ink-faint">
            {row.sku} · {row.variant_label}
          </span>
        </>
      ),
    },
    {
      key: "actor",
      header: "Kim",
      sortValue: (row) => row.actor,
      cell: (row) => row.actor,
    },
    {
      key: "reason",
      header: "Sabab",
      cell: (row) => (
        <span className="line-clamp-2 max-w-72 text-ink-soft">{row.reason || "—"}</span>
      ),
    },
    {
      key: "cause",
      header: "Manba",
      cell: (row) => {
        const link =
          row.supply_id !== null
            ? `SUP #${row.supply_id}`
            : row.count_id !== null
              ? `CNT #${row.count_id}`
              : row.removal_id !== null
                ? `RMV #${row.removal_id}`
                : row.order_id !== null
                  ? `Buyurtma #${row.order_id}`
                  : row.return_request_id !== null
                    ? `Ariza #${row.return_request_id}`
                    : null
        return link ? (
          <span className="tabular text-[12px] text-ink-soft">{link}</span>
        ) : (
          <span className="text-ink-faint">—</span>
        )
      },
    },
  ]

  return (
    <Page floor title="Harakatlar" hint="Javon — shu qatorlarning yig'indisi.">
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Harakat yo'q"
        emptyHint="Filtrni bo'shatib ko'ring."
        server={{
          page,
          pageSize: PAGE_SIZE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
        }}
        toolbar={
          <>
            <div className="flex items-center gap-1.5">
              <Label htmlFor="mv-kind" className="sr-only">
                Tur
              </Label>
              <Select
                id="mv-kind"
                className="w-48"
                value={kind}
                onChange={(event) => {
                  setKind(event.target.value as "" | MovementKind)
                  setPage(1)
                }}
              >
                <option value="">Hamma tur</option>
                {KINDS.map((value) => (
                  <option key={value} value={value}>
                    {MOVEMENT_KIND[value]}
                  </option>
                ))}
              </Select>
            </div>
            <Select
              className="w-56"
              aria-label="Taklif"
              value={offerId}
              onChange={(event) => {
                setOfferId(event.target.value)
                setPage(1)
              }}
            >
              <option value="">Hamma javon</option>
              {(offers.data ?? []).map((offer) => (
                <option key={offer.id} value={String(offer.id)}>
                  {offer.product_title} — {offer.seller.name}
                </option>
              ))}
            </Select>
            <Input
              className="w-40"
              aria-label="Kim"
              placeholder="Kim"
              value={who}
              onChange={(event) => setWho(event.target.value)}
            />
            <Input
              className="w-36"
              type="date"
              aria-label="Shu kundan"
              value={since}
              onChange={(event) => setSince(event.target.value)}
            />
            <Hint>
              {rows.length} / {query.data?.total ?? 0}
            </Hint>
          </>
        }
      />
    </Page>
  )
}
