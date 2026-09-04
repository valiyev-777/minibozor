import * as React from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { AlertTriangle } from "lucide-react"
import { api } from "@/api/client"
import type { Shelf, StaffOffer } from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Input, Label } from "@/components/ui/field"
import { money } from "@/lib/utils"

const KEY = ["staff", "shelf"]

/** A row of the shelf list: one offer, with its own count beside it. */
type Row = StaffOffer & { sellable: number; reserved: number }

export function ShelfPage() {
  const [query, setQuery] = React.useState("")
  const [open, setOpen] = React.useState<StaffOffer | null>(null)

  const offers = useQuery({
    queryKey: [...KEY, "offers"],
    queryFn: () => api<StaffOffer[]>("/staff/offers"),
  })

  // One shelf reading per offer. The list endpoint carries the running total;
  // what is promised and what is left to sell are a question about holds, and
  // only the shelf endpoint answers it.
  const shelves = useQueries({
    queries: (offers.data ?? []).map((offer) => ({
      queryKey: [...KEY, "reading", offer.id],
      queryFn: () => api<Shelf[]>(`/staff/offers/${offer.id}/shelf`),
      staleTime: 15_000,
    })),
  })

  const rows: Row[] | undefined = React.useMemo(() => {
    if (!offers.data) return undefined
    const enriched = offers.data.map((offer, index) => {
      const total = shelves[index]?.data?.find((row) => row.variant_id === null)
      return {
        ...offer,
        sellable: total?.sellable ?? offer.stock_left,
        reserved: total?.reserved ?? 0,
      }
    })
    const needle = query.trim().toLowerCase()
    const matched = needle
      ? enriched.filter(
          (row) =>
            row.product_title.toLowerCase().includes(needle) ||
            row.seller.name.toLowerCase().includes(needle),
        )
      : enriched
    // Fewest first: the reason to open this screen is to find what is running
    // out, and sorting by name would bury it.
    return [...matched].sort((a, b) => a.sellable - b.sellable)
  }, [offers.data, shelves, query])

  const columns: Column<Row>[] = [
    {
      key: "product",
      header: "Mahsulot",
      sortValue: (row) => row.product_title,
      cell: (row) => (
        <>
          <span className="block max-w-72 truncate font-medium text-ink">
            {row.product_title}
          </span>
          <span className="block text-[12px] text-ink-faint">{row.seller.name}</span>
        </>
      ),
    },
    {
      key: "price",
      header: "Narx",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.price,
      cell: (row) => money(row.price),
    },
    {
      key: "on_hand",
      header: "Javonda",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.stock_left,
      cell: (row) => row.stock_left,
    },
    {
      key: "reserved",
      header: "Band",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.reserved,
      cell: (row) =>
        row.reserved ? <span className="text-warn">{row.reserved}</span> : "—",
    },
    {
      key: "sellable",
      header: "Sotishga tayyor",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.sellable,
      cell: (row) => (
        <span
          className={
            row.sellable === 0
              ? "font-semibold text-danger"
              : row.sellable <= 3
                ? "font-semibold text-warn"
                : "text-ink"
          }
        >
          {row.sellable}
        </span>
      ),
    },
    {
      key: "state",
      header: "",
      cell: (row) =>
        !row.active ? (
          <Badge tone="neutral">Qaytarilgan</Badge>
        ) : row.sellable === 0 ? (
          <Badge tone="danger">
            <AlertTriangle className="mr-1 size-3" />
            Tugadi
          </Badge>
        ) : row.is_winner ? (
          <Badge tone="good">Kartochkada</Badge>
        ) : null,
    },
  ]

  return (
    <Page
      floor
      title="Javon"
      hint="Kam qolganlar birinchi. Javonda − band = sotishga tayyor."
    >
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={(row) => row.id}
        loading={offers.isPending}
        error={offers.error}
        onRetry={() => void offers.refetch()}
        onRowClick={setOpen}
        clientPageSize={30}
        emptyTitle="Javon bo'sh"
        toolbar={
          <>
            <Label htmlFor="shelf-q" className="sr-only">
              Qidirish
            </Label>
            <Input
              id="shelf-q"
              className="w-64"
              placeholder="Mahsulot yoki sotuvchi"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Hint>{rows?.length ?? 0} ta javon</Hint>
          </>
        }
      />

      {open ? <ShelfDetail offer={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

function ShelfDetail({ offer, onClose }: { offer: StaffOffer; onClose: () => void }) {
  const query = useQuery({
    queryKey: [...KEY, "reading", offer.id],
    queryFn: () => api<Shelf[]>(`/staff/offers/${offer.id}/shelf`),
  })

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        className="w-[min(94vw,40rem)]"
        title={offer.product_title}
        description={`${offer.seller.name} · ${money(offer.price)} so'm`}
        footer={
          <Button size="lg" variant="ghost" onClick={onClose}>
            Yopish
          </Button>
        }
      >
        <table className="w-full text-left text-[15px]">
          <thead>
            <tr className="border-b border-line text-[12px] uppercase tracking-wide text-ink-soft">
              <th className="py-2">Rang / o'lcham</th>
              <th className="py-2 text-right">Javonda</th>
              <th className="py-2 text-right">Band</th>
              <th className="py-2 text-right">Tayyor</th>
            </tr>
          </thead>
          <tbody>
            {(query.data ?? []).map((row) => (
              <tr
                key={`${row.variant_id ?? "all"}`}
                className={
                  row.variant_id === null
                    ? "border-b-2 border-line font-semibold"
                    : "border-b border-line-soft"
                }
              >
                <td className="py-2">{row.variant_label}</td>
                <td className="tabular py-2 text-right">{row.on_hand}</td>
                <td className="tabular py-2 text-right">
                  {row.reserved || <span className="text-ink-faint">—</span>}
                </td>
                <td className="tabular py-2 text-right">
                  <span className={row.sellable === 0 ? "text-danger" : ""}>
                    {row.sellable}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {query.isPending ? <Hint>Yuklanmoqda…</Hint> : null}
      </DialogPanel>
    </Dialog>
  )
}
