import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { CatalogSummary, OrderPage, Return, Supply } from "@/api/types"
import { Async } from "@/ui/states"
import { Figure, Panel } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { num } from "@/lib/format"
import { productStatus, t } from "@/lib/labels"

/**
 * Four numbers, and each of them is a link to the list behind it.
 *
 * The plan asks for exactly four and that is the whole screen: no chart, no
 * analytics, no "recent activity". An admin opens this to find out whether
 * anything is waiting for a person, and every one of the four answers that
 * with a count and a way to go and do it. A number nobody can act on would be
 * decoration.
 *
 * They are four counts from four different lists rather than one summary
 * endpoint, because there is no endpoint that answers this question and
 * inventing one would mean a fifth place that can disagree with the four.
 * Each query asks for one page and reads its `total`, so the counts are the
 * server's own arithmetic and not this screen's.
 */
export function OverviewPage() {
  const placed = useQuery({
    queryKey: ["summary", "placed"],
    queryFn: () =>
      api<OrderPage>("/staff/orders", { query: { status: "placed", page_size: 1 } }),
  })
  const packing = useQuery({
    queryKey: ["summary", "packing"],
    queryFn: () =>
      api<OrderPage>("/staff/orders", { query: { status: "packing", page_size: 1 } }),
  })
  const supplies = useQuery({
    queryKey: ["summary", "supplies"],
    queryFn: () => api<Supply[]>("/staff/supplies", { query: { status: "declared" } }),
  })
  const returns = useQuery({
    queryKey: ["summary", "returns"],
    queryFn: () => api<Return[]>("/staff/returns", { query: { status: "submitted" } }),
  })
  const catalog = useQuery({
    queryKey: ["summary", "catalog"],
    queryFn: () => api<CatalogSummary>("/staff/catalog/summary"),
  })

  return (
    <>
      <PageTitle>{t.overview}</PageTitle>

      <div className="grid gap-[var(--gap-page)] sm:grid-cols-2 lg:grid-cols-4">
        <Tile
          to="/orders?status=placed"
          label={t.newOrders}
          query={placed}
          read={(page) => page.total}
        />
        <Tile
          to="/supplies?status=declared"
          label={t.awaitingSupplies}
          query={supplies}
          read={(rows) => rows.length}
        />
        <Tile
          to="/returns?awaiting="
          label={t.awaitingReturns}
          query={returns}
          read={(rows) => rows.length}
        />
        <Tile
          to="/orders?status=packing"
          label={t.unpickedOrders}
          query={packing}
          read={(page) => page.total}
        />
      </div>

      {/* The catalogue's own counts, which are an admin's other question:
          how many cards are waiting on a batch, and how many were refused. */}
      <Panel title={t.catalog}>
        <Async query={catalog} lines={2}>
          {(summary) => (
            <div className="flex flex-wrap gap-x-8 gap-y-2 border-t border-line-soft px-5 py-4 text-[length:var(--text-small)]">
              {/* The server's keys are the enum's own words — `moderating`,
                  `published` — and they are not what anybody at this desk
                  calls them. This is the one place a status word is translated
                  here rather than taken from the row, because these arrive as
                  dictionary *keys* and a key has no label beside it. */}
              {Object.entries(summary.counts).map(([state, count]) => (
                <span key={state} className="text-ink-soft">
                  {productStatus[state] ?? state}:{" "}
                  <span className="tabular text-ink">{num(count)}</span>
                </span>
              ))}
            </div>
          )}
        </Async>
      </Panel>
    </>
  )
}

function Tile<T>({
  to,
  label,
  query,
  read,
}: {
  to: string
  label: string
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined; refetch: () => unknown }
  read: (data: T) => number
}) {
  return (
    <Link
      to={to}
      className="rounded-[var(--radius-panel)] border border-line bg-surface px-5 py-4
                 outline-none transition-colors hover:border-brand
                 focus-visible:ring-2 focus-visible:ring-brand/40"
    >
      <Async query={query} lines={1}>
        {(data) => {
          const count = read(data)
          return (
            <Figure
              label={label}
              value={num(count)}
              {...(count > 0 ? { tone: "brand" as const } : {})}
            />
          )
        }}
      </Async>
    </Link>
  )
}
