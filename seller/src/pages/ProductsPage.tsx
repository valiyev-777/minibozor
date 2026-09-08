import * as React from "react"
import { Link } from "react-router-dom"
import { Plus, Search } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Listing, ListingStage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Input } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { PageTitle } from "@/components/Shell"
import { cn } from "@/ui/cn"
import { num, som } from "@/lib/format"
import { stageWord, t } from "@/lib/labels"

/**
 * Everything this seller opened, and where each of it has got to.
 *
 * It was an undivided list of every product the shop has ever had, oldest
 * habits and all, with the refused ones scattered through it — so a seller
 * with sixty cards could not find the two that needed fixing without reading
 * sixty rows. Two controls fix that and no more than two: a search box, and
 * one filter chip per stage with its own count.
 *
 * **The filters are counted and the empty ones are absent.** A chip that says
 * `Rad etildi 0` is a chip that has to be read to learn there is nothing
 * behind it; a chip that says `Rad etildi 2` is the reason this row of chips
 * exists at all.
 *
 * Filtered here rather than by the server, deliberately. `GET
 * /staff/catalog/listings` answers with this seller's whole shop — tens of
 * rows, not thousands — so a round trip per keystroke would buy nothing and
 * the counts on the chips would each need a request of their own.
 */
const TONE: Record<ListingStage, "neutral" | "brand" | "good" | "warn" | "danger"> = {
  awaiting_warehouse: "warn",
  in_warehouse: "brand",
  on_sale: "good",
  sold_out: "neutral",
  rejected: "danger",
  archived: "neutral",
}

/** The order the chips appear in: what needs doing first, then the shop. */
const STAGES: readonly ListingStage[] = [
  "rejected",
  "awaiting_warehouse",
  "on_sale",
  "sold_out",
  "archived",
]

export function ProductsPage() {
  const listings = useQuery({
    queryKey: ["listings"],
    queryFn: () => api<Listing[]>("/staff/catalog/listings"),
  })
  const [query, setQuery] = React.useState("")
  const [stage, setStage] = React.useState<ListingStage | "">("")

  const rows = listings.data ?? []
  const counts = Object.fromEntries(
    STAGES.map((one) => [one, rows.filter((row) => row.stage === one).length]),
  ) as Record<ListingStage, number>

  const needle = query.trim().toLowerCase()
  const shown = rows.filter(
    (row) =>
      (!stage || row.stage === stage) &&
      (!needle ||
        row.title.toLowerCase().includes(needle) ||
        row.sku.toLowerCase().includes(needle)),
  )

  return (
    <>
      <PageTitle
        action={
          <Button asChild variant="primary">
            <Link to="/products/new">
              <Plus />
              {t.newProduct}
            </Link>
          </Button>
        }
      >
        {t.products}
      </PageTitle>

      {rows.length ? (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-52 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t.searchProducts}
              aria-label={t.searchProducts}
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-1">
            <Chip active={!stage} onClick={() => setStage("")}>
              {t.all} {num(rows.length)}
            </Chip>
            {STAGES.filter((one) => counts[one] > 0).map((one) => (
              <Chip
                key={one}
                active={stage === one}
                onClick={() => setStage(stage === one ? "" : one)}
              >
                {stageWord[one]} {num(counts[one])}
              </Chip>
            ))}
          </div>
        </div>
      ) : null}

      <Panel>
        <Async
          query={listings}
          lines={4}
          empty={
            <Empty
              title={t.productsEmpty}
              hint={t.productsEmptyHint}
              action={
                <Button asChild variant="primary">
                  <Link to="/products/new">
                    <Plus />
                    {t.newProduct}
                  </Link>
                </Button>
              }
            />
          }
        >
          {() =>
            shown.length ? (
              <>
                {/* Column headings on a laptop only. On a phone each row is
                    read as a small paragraph and a header row would be a
                    legend for three words. */}
                <div className="hidden border-t border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
                  <span className="w-11" />
                  <span className="flex-1">{t.title}</span>
                  <span className="w-28 text-right">{t.price}</span>
                  <span className="w-24 text-right">{t.onHand}</span>
                  <span className="w-28 text-right">{t.status}</span>
                </div>

                {shown.map((row) => {
                  const declared = row.stock.reduce((sum, cell) => sum + cell.declared, 0)
                  const waiting = row.stage === "awaiting_warehouse"
                  return (
                    <Link
                      key={row.id}
                      to={`/products/${row.id}`}
                      className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t
                                 border-line-soft px-5 py-3 outline-none transition-colors
                                 hover:bg-line-soft/50 focus-visible:bg-line-soft
                                 sm:flex-nowrap"
                    >
                      <Thumb src={row.images[0]} className="size-11 shrink-0" />

                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[length:var(--text-body)] font-medium text-ink">
                          {row.title}
                        </span>
                        <span className="block truncate text-[length:var(--text-micro)] text-ink-faint">
                          {row.sku}
                        </span>
                      </span>

                      <span className="tabular w-28 text-right text-[length:var(--text-body)] text-ink">
                        {som(row.price)}
                      </span>

                      {/* One figure, and which one follows the stage: a card
                          still waiting has nothing on a shelf to report, so
                          the honest number is what was handed in. */}
                      <span className="tabular w-24 text-right text-[length:var(--text-small)] text-ink-soft">
                        {num(waiting ? declared : row.on_hand_total)}
                        <span className="hidden sm:inline"> {t.pieces}</span>
                      </span>

                      {/* The short word, not the server's phrase: this column
                          is 7rem wide and "Omborga kutilmoqda" wrapped to two
                          lines in every row that was waiting. The phrase is
                          still what the product's own screen shows, where
                          there is room for it to say more. */}
                      <span className="w-28 text-right">
                        <Badge tone={TONE[row.stage]}>
                          {stageWord[row.stage] ?? row.stage_label}
                        </Badge>
                      </span>
                    </Link>
                  )
                })}
              </>
            ) : (
              <Empty title={t.nothingFound} hint={t.nothingFoundHint} />
            )
          }
        </Async>
      </Panel>
    </>
  )
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-[var(--radius-control)] px-2.5 py-1.5 text-[length:var(--text-small)]",
        "font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-brand/40",
        active ? "bg-brand text-brand-ink" : "text-ink-soft hover:bg-line-soft",
      )}
    >
      {children}
    </button>
  )
}
