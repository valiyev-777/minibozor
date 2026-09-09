/**
 * Boshqaruv — the first screen, and the only one allowed to be a list of
 * numbers.
 *
 * **Every figure is a link.** A dashboard number that is not one is a dead
 * end: somebody reads "4 cards held back for want of a photograph" and then
 * has to go and find them. The server sends the path with the figure, so the
 * link and the number cannot drift apart.
 *
 * **One tile is allowed to shout.** Sacks standing unsorted overnight are what
 * this shop actually loses money on, so that tile turns red and the rest do
 * not. If everything is urgent, nothing is.
 */

import { ArrowUpRight } from "lucide-react"
import { Link } from "react-router-dom"
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { cn } from "@/lib/cn"
import { date, groups, money } from "@/lib/format"
import { useDashboard } from "@/lib/queries"
import type { DashboardTile } from "@/lib/types"

export function DashboardPage() {
  const board = useDashboard()

  return (
    <div className="space-y-4">
      <PageHeader title="Boshqaruv" subtitle="Bugun nima bo'lyapti" />
      <Problem error={board.error} />
      {board.isLoading ? <Waiting what="Raqamlar" /> : null}

      {board.data ? (
        <>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
            {board.data.tiles.map((tile) => (
              <Tile key={tile.key} tile={tile} />
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <section className="rounded-panel border bg-surface p-3 lg:col-span-2">
              <h2 className="mb-2 text-small font-semibold">
                So'nggi 14 kun
              </h2>
              <Sales points={board.data.sales} />
            </section>

            <section className="rounded-panel border bg-surface p-3">
              <h2 className="mb-2 text-small font-semibold">Eng ko'p ketgani</h2>
              {board.data.movers.length === 0 ? (
                <Empty what="Hali hech narsa yetkazilmagan." />
              ) : (
                <ul className="divide-y">
                  {board.data.movers.map((mover) => (
                    <li
                      key={mover.variant_id}
                      className="flex items-baseline justify-between gap-2 py-2"
                    >
                      <div className="min-w-0">
                        <div className="truncate text-small">{mover.product_title}</div>
                        <div className="text-micro text-ink-faint">
                          {mover.variant_label}
                        </div>
                      </div>
                      <span className="tabular text-small font-semibold">
                        {groups(mover.qty)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      ) : null}
    </div>
  )
}

function Tile({ tile }: { tile: DashboardTile }) {
  return (
    <Link
      to={tile.href || "#"}
      className={cn(
        "group rounded-panel border bg-surface p-3 transition hover:border-brand",
        tile.urgent && "border-danger bg-danger-soft",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-micro text-ink-soft">{tile.label}</span>
        <ArrowUpRight className="size-3.5 shrink-0 text-ink-faint opacity-0 transition group-hover:opacity-100" />
      </div>
      <div className={cn("figure", tile.urgent && "text-danger")}>
        {groups(tile.value)}
      </div>
      {tile.hint ? (
        <div className="truncate text-micro text-ink-faint">{tile.hint}</div>
      ) : null}
    </Link>
  )
}

/** `2M`, `500k`, `0` — an axis label, not a price. */
function short(value: number): string {
  if (value >= 1_000_000) return `${Math.round((value / 1_000_000) * 10) / 10}M`
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`
  return String(value)
}

function Sales({ points }: { points: { day: string; orders: number; total: number }[] }) {
  const data = points.map((point) => ({
    day: date(point.day).slice(0, 5),
    orders: point.orders,
    total: point.total,
  }))

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="var(--color-line-soft)" vertical={false} />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={44}
            tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
            // Abbreviated, because a day's takings are seven digits and an
            // axis that prints them all is an axis that clips them instead.
            tickFormatter={short}
          />
          <Tooltip
            cursor={{ fill: "var(--color-line-soft)" }}
            contentStyle={{
              borderRadius: "var(--radius-control)",
              border: "1px solid var(--color-line)",
              fontSize: 12,
            }}
            formatter={(value: number, name) =>
              name === "total" ? [money(value), "summa"] : [groups(value), "buyurtma"]
            }
          />
          <Bar dataKey="total" fill="var(--color-brand)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
