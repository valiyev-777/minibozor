import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, PackageX, TriangleAlert } from "lucide-react"
import { api } from "@/api/client"
import type { Shelf, StaffOffer } from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Input, Label } from "@/components/ui/field"
import { Async } from "@/ui/states"
import { money } from "@/lib/utils"

const KEY = ["staff", "shelf"]

/** Below this, the row is worth acting on rather than reading. */
const LOW = 3

type State = "out" | "low" | "ok" | "withdrawn"

/**
 * The shelf.
 *
 * **This screen used to fire one HTTP request per offer.** It loaded the offer
 * list, then called `GET /staff/offers/{id}/shelf` once for every row —
 * measured at **43 requests** on a database with 39 offers, every time the
 * page was opened, because "held" and "left to sell" are only on the
 * per-offer endpoint. It is one request now.
 *
 * What one request gives, and what it does not:
 *
 * - `GET /staff/offers` carries `stock_left` per offer **and the whole variant
 *   grid** — every colour and size with its own count. So "what is there" and
 *   "what has run out" are answerable for every row, down to the size, from
 *   one call. That is what the three states below are built on.
 * - It does **not** carry `reserved` or `sellable`. Those are derived from
 *   holds — baskets and unpaid orders — and only `.../{id}/shelf` computes
 *   them. So the held figure appears when a row is opened, which is one
 *   request for the one offer being looked at, rather than 39 for the 38
 *   nobody asked about.
 *
 * Putting the held figure back in the list needs `reserved` and `sellable` on
 * `StaffOfferOut`. That is a backend change and the backend was not to be
 * touched; it is written up in the handover.
 *
 * The other half of the brief was that this screen be legible: what can be
 * sold, what is held, what is gone, told apart at a glance. The three states
 * are a filter and a colour, the count that matters is the largest thing in
 * the row, and the row says which *size* has gone rather than only that
 * something has.
 */
export function ShelfPage() {
  const [query, setQuery] = React.useState("")
  const [state, setState] = React.useState<State | "all">("all")
  const [open, setOpen] = React.useState<StaffOffer | null>(null)

  const offers = useQuery({
    queryKey: [...KEY, "offers"],
    queryFn: () => api<StaffOffer[]>("/staff/offers"),
  })

  const all = React.useMemo(() => (offers.data ?? []).map(describe), [offers.data])

  const counts = React.useMemo(
    () => ({
      all: all.length,
      out: all.filter((r) => r.state === "out").length,
      low: all.filter((r) => r.state === "low").length,
      ok: all.filter((r) => r.state === "ok").length,
      withdrawn: all.filter((r) => r.state === "withdrawn").length,
    }),
    [all],
  )

  const rows = React.useMemo(() => {
    const needle = query.trim().toLowerCase()
    return all
      .filter((row) => (state === "all" ? true : row.state === state))
      .filter(
        (row) =>
          !needle ||
          row.offer.product_title.toLowerCase().includes(needle) ||
          row.offer.seller.name.toLowerCase().includes(needle),
      )
      // Fewest first: the reason to open this screen is to find what is
      // running out, and sorting by name would bury it.
      .sort((a, b) => a.onHand - b.onHand)
  }, [all, state, query])

  const columns: Column<Row>[] = [
    {
      key: "product",
      header: "Mahsulot",
      sortValue: (row) => row.offer.product_title,
      cell: (row) => (
        <>
          <span className="block max-w-72 truncate font-medium text-ink">
            {row.offer.product_title}
          </span>
          <span className="block text-[length:var(--text-micro)] text-ink-faint">
            {row.offer.seller.name}
          </span>
        </>
      ),
    },
    {
      key: "on_hand",
      header: "Javonda",
      headClassName: "text-right",
      className: "text-right",
      sortValue: (row) => row.onHand,
      cell: (row) => (
        <span
          className={
            row.state === "out"
              ? "tabular text-[length:var(--text-body)] font-semibold text-danger"
              : row.state === "low"
                ? "tabular text-[length:var(--text-body)] font-semibold text-warn-ink"
                : "tabular text-[length:var(--text-body)] font-semibold text-ink"
          }
        >
          {row.onHand}
        </span>
      ),
    },
    {
      key: "grid",
      header: "Ranglar va razmerlar",
      // The whole point of having the grid in the list: "the black M has run
      // out" is a different fact from "there are fourteen left", and it is the
      // one somebody acts on.
      cell: (row) =>
        row.cells.length ? (
          <div className="flex flex-wrap gap-1">
            {row.cells.slice(0, 12).map((cell) => (
              <span
                key={cell.id}
                title={`${cell.label}: ${cell.stock}`}
                className={
                  cell.stock === 0
                    ? "rounded border border-danger/40 bg-danger-soft px-1.5 text-[length:var(--text-micro)] text-danger"
                    : cell.stock <= LOW
                      ? "rounded border border-warn/40 bg-warn-soft px-1.5 text-[length:var(--text-micro)] text-warn-ink"
                      : "rounded border border-line bg-line-soft px-1.5 text-[length:var(--text-micro)] text-ink-soft"
                }
              >
                {cell.label} {cell.stock}
              </span>
            ))}
            {row.cells.length > 12 ? (
              <span className="text-[length:var(--text-micro)] text-ink-faint">
                +{row.cells.length - 12}
              </span>
            ) : null}
          </div>
        ) : (
          <span className="text-ink-faint">Rangsiz</span>
        ),
    },
    {
      key: "price",
      header: "Narx",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.offer.price,
      cell: (row) => money(row.offer.price),
    },
    {
      key: "state",
      header: "",
      cell: (row) =>
        row.state === "withdrawn" ? (
          <Badge tone="neutral">Sotuvdan olingan</Badge>
        ) : row.state === "out" ? (
          <Badge tone="danger">
            <PackageX />
            Tugadi
          </Badge>
        ) : row.state === "low" ? (
          <Badge tone="warn">
            <TriangleAlert />
            Kam qoldi
          </Badge>
        ) : row.offer.is_winner ? (
          <Badge tone="good">Kartochkada</Badge>
        ) : null,
    },
  ]

  return (
    <Page
      floor
      title="Javon"
      hint="Kam qolganlar birinchi. Qatorni bosing — band va sotishga tayyor soni ochiladi."
    >
      <DataTable
        rows={offers.isPending ? undefined : rows}
        columns={columns}
        rowKey={(row) => row.offer.id}
        loading={offers.isPending}
        error={offers.error}
        onRetry={() => void offers.refetch()}
        onRowClick={(row) => setOpen(row.offer)}
        clientPageSize={30}
        emptyTitle={
          state === "all" ? "Javon bo'sh" : "Bu holatda hech narsa yo'q"
        }
        emptyHint={
          state === "all"
            ? "Tovar javonga partiya qabul qilinganda tushadi."
            : "Filtrni «Hammasi» ga qaytaring."
        }
        toolbar={
          <>
            {/* The primary thing this screen is opened for, first: which
                rows need doing something about. */}
            <div className="flex flex-wrap gap-1">
              {(
                [
                  ["out", `Tugadi ${counts.out}`],
                  ["low", `Kam qoldi ${counts.low}`],
                  ["ok", `Bor ${counts.ok}`],
                  ["withdrawn", `Olingan ${counts.withdrawn}`],
                  ["all", `Hammasi ${counts.all}`],
                ] as const
              ).map(([value, label]) => (
                <Button
                  key={value}
                  size="sm"
                  variant={state === value ? "primary" : "outline"}
                  aria-pressed={state === value}
                  onClick={() => setState(value)}
                >
                  {label}
                </Button>
              ))}
            </div>
            <Label htmlFor="shelf-q" className="sr-only">
              Qidirish
            </Label>
            <Input
              id="shelf-q"
              className="w-56"
              placeholder="Mahsulot yoki sotuvchi"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </>
        }
      />

      {open ? <ShelfDetail offer={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

type Row = {
  offer: StaffOffer
  onHand: number
  state: State
  cells: { id: number; label: string; stock: number }[]
}

/**
 * One offer, as a row: its total, its state, and its countable cells.
 *
 * A cell is a size where there are sizes and a colour otherwise, which is the
 * level the warehouse counts on — the same rule as everywhere else, so a zero
 * here means the same thing as a zero in the ledger.
 */
function describe(offer: StaffOffer): Row {
  const colours = new Map(
    offer.variants.filter((v) => v.kind === "color").map((v) => [v.variant_id, v.label]),
  )
  const sizes = offer.variants.filter((v) => v.kind === "size" && v.parent_id !== null)
  const cells = (
    sizes.length
      ? sizes.map((v) => ({
          id: v.variant_id,
          label: `${colours.get(v.parent_id!) ?? "?"}/${v.label}`,
          stock: v.stock_left,
        }))
      : offer.variants
          .filter((v) => v.kind === "color")
          .map((v) => ({ id: v.variant_id, label: v.label, stock: v.stock_left }))
  ).sort((a, b) => a.stock - b.stock)

  const onHand = offer.stock_left
  const state: State = !offer.active
    ? "withdrawn"
    : onHand === 0
      ? "out"
      : onHand <= LOW || cells.some((c) => c.stock === 0)
        ? "low"
        : "ok"
  return { offer, onHand, state, cells }
}

/**
 * The held figure, for the one offer somebody asked about.
 *
 * This is the request the list used to make thirty-nine of. Held and
 * sellable are derived from baskets and unpaid orders, so only this endpoint
 * knows them — and one row at a time is the honest place to pay for it.
 */
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
        <Async query={query} lines={4}>
          {(rows) => (
            <>
              <table className="w-full text-left text-[length:var(--text-body)]">
                <caption className="sr-only">
                  Rang va o'lcham bo'yicha javon, band va sotishga tayyor soni
                </caption>
                <thead>
                  <tr className="border-b border-line text-[length:var(--text-micro)] uppercase tracking-wide text-ink-soft">
                    <th scope="col" className="py-2">
                      Rang / o'lcham
                    </th>
                    <th scope="col" className="py-2 text-right">
                      Javonda
                    </th>
                    <th scope="col" className="py-2 text-right">
                      Band
                    </th>
                    <th scope="col" className="py-2 text-right">
                      Sotishga tayyor
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
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
                        {row.reserved ? (
                          <span className="text-warn-ink">{row.reserved}</span>
                        ) : (
                          <span className="text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="tabular py-2 text-right">
                        <span
                          className={
                            row.sellable === 0 ? "font-semibold text-danger" : ""
                          }
                        >
                          {row.sellable}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <Hint className="mt-3 flex items-start gap-1.5">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-ink-faint" />
                Band — savatdagi va to'lanmagan buyurtmadagi tovar: hali bizda
                turadi, lekin boshqa hech kim sotib olmaydi. Javonda − band =
                sotishga tayyor.
              </Hint>
            </>
          )}
        </Async>
      </DialogPanel>
    </Dialog>
  )
}
