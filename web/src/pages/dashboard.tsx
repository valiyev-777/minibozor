/**
 * Boshqaruv — the first screen, and the only one allowed to be a list of
 * numbers.
 *
 * **It was a flat grid of seven counters.** All the same size, all the same
 * weight, in the order the server happened to build them — so the biggest
 * number on the page was whichever count happened to be largest, and the one
 * thing worth acting on was a tile among six others. The owner opens this
 * screen to find out how the day went and what needs doing; those are two
 * different questions and they are now two parts of the page.
 *
 * **The day, then what needs doing, then the shape of the fortnight.** Money
 * first, because that is the question. Then only the counters that are
 * actually asking for something, urgent ones first; the ones reading nought
 * are good news and go in one quiet line, still links, because "no unsorted
 * sacks" is worth being able to see and not worth a card.
 *
 * **Every figure is a link.** A dashboard number that is not one is a dead
 * end: somebody reads "1 card is on sale with nothing on the shelf" and then
 * has to go and find it. The server sends the path with the figure, so the
 * link and the number cannot drift apart.
 */

import { ArrowUpRight, TrendingDown, TrendingUp } from "lucide-react"
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

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { cn } from "@/lib/cn"
import { date, groups, money } from "@/lib/format"
import { useDashboard } from "@/lib/queries"
import type { DashboardTile, SalesPoint } from "@/lib/types"

/** The takings tile is the headline of this page, not one card among seven. */
const HEADLINE = "orders_today"

export function DashboardPage() {
  const board = useDashboard()
  const tiles = board.data?.tiles ?? []
  const sales = board.data?.sales ?? []

  // Asking for action, and not. A counter reading nought is good news: it
  // belongs on the page, in one line, not in a card the size of a problem.
  const asking = tiles
    .filter((tile) => tile.key !== HEADLINE && (tile.urgent || tile.value > 0))
    .sort((a, b) => Number(b.urgent) - Number(a.urgent))
  const quiet = tiles.filter(
    (tile) => tile.key !== HEADLINE && !tile.urgent && tile.value === 0,
  )

  return (
    <div className="space-y-(--gap-page)">
      <PageHeader title="Boshqaruv" subtitle={`Bugun · ${date(new Date())}`} />
      <Problem error={board.error} />
      {board.isLoading ? <Waiting what="Raqamlar" /> : null}

      {board.data ? (
        <>
          <Today points={sales} />

          {asking.length ? (
            <section>
              <h2 className="mb-2 text-small font-semibold tracking-tight">
                E'tibor kerak
              </h2>
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                {asking.map((tile) => (
                  <TileCard key={tile.key} tile={tile} />
                ))}
              </div>
            </section>
          ) : null}

          {quiet.length ? <Clear tiles={quiet} /> : null}

          <div className="grid gap-(--gap-page) lg:grid-cols-3">
            <Panel
              title="So'nggi 14 kun"
              className="lg:col-span-2"
              aside={
                <span className="tabular text-small font-semibold">
                  {money(sales.reduce((sum, one) => sum + one.total, 0))}
                </span>
              }
            >
              <Sales points={sales} />
            </Panel>

            <Panel title="Eng ko'p ketgani" bare>
              {board.data.movers.length === 0 ? (
                <div className="p-3">
                  <Empty what="Hali hech narsa yetkazilmagan." />
                </div>
              ) : (
                <ol className="divide-y divide-line">
                  {board.data.movers.map((mover, index) => (
                    <li
                      key={mover.variant_id}
                      className="flex items-center gap-3 px-3 py-(--cell-y)">
                      <span className="w-4 shrink-0 tabular text-micro text-ink-faint">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-small">{mover.product_title}</div>
                        <div className="truncate text-micro text-ink-faint">
                          {mover.variant_label}
                        </div>
                      </div>
                      <span className="tabular text-small font-semibold">
                        {groups(mover.qty)}
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  )
}

/**
 * The day, in the three figures somebody actually asks for.
 *
 * Takings big, because that is the question; the count beside it, because
 * "800 000 from one order" and "from nine" are different days. The line
 * against yesterday is the only comparison worth having on a shop this size
 * — a week-on-week average would be arithmetic about eleven orders.
 */
function Today({ points }: { points: SalesPoint[] }) {
  const today = points.at(-1)
  const yesterday = points.at(-2)
  const week = points.slice(-7).reduce((sum, one) => sum + one.total, 0)
  // No comparison before there is anything to compare. A shop that has not
  // sold anything yet this morning was reading "kechagidan -100%", which is
  // arithmetic rather than news — it says the same thing every day before the
  // first customer.
  const change =
    today && yesterday && today.total > 0 && yesterday.total > 0
      ? Math.round(((today.total - yesterday.total) / yesterday.total) * 100)
      : null

  return (
    <Panel>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <div className="text-micro font-medium text-ink-soft">Bugungi savdo</div>
          <div className="figure mt-1">{money(today?.total ?? 0)}</div>
          {change !== null ? (
            <div
              className={cn(
                "mt-0.5 flex items-center gap-1 text-micro",
                change > 0 ? "text-good" : change < 0 ? "text-danger" : "text-ink-faint",
              )}
            >
              {change > 0 ? (
                <TrendingUp className="size-3.5" />
              ) : change < 0 ? (
                <TrendingDown className="size-3.5" />
              ) : null}
              kechagidan {change > 0 ? "+" : ""}
              {change}%
            </div>
          ) : (
            <div className="mt-0.5 text-micro text-ink-faint">
              {today?.total ? "kecha savdo bo'lmagan" : "hali savdo yo'q"}
            </div>
          )}
        </div>

        <Link
          to="/buyurtmalar"
          className="group rounded-control px-2 py-1 transition-colors hover:bg-line-soft">
          <div className="flex items-center gap-1 text-micro font-medium text-ink-soft">
            Buyurtma
            <ArrowUpRight className="size-3 opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
          <div className="figure mt-1">{groups(today?.orders ?? 0)}</div>
        </Link>

        <div className="ml-auto text-right">
          <div className="text-micro font-medium text-ink-soft">So'nggi 7 kun</div>
          <div className="figure mt-1 text-ink-soft">{money(week)}</div>
        </div>
      </div>
    </Panel>
  )
}

/** The counters that are asking for nothing, in one line. Still links. */
function Clear({ tiles }: { tiles: DashboardTile[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-1 gap-y-1 text-micro text-ink-faint">
      <span className="text-ink-soft">Joyida:</span>
      {tiles.map((tile, index) => (
        <span key={tile.key} className="flex items-center gap-1">
          <Link
            to={tile.href || "#"}
            className="rounded-full px-1.5 py-0.5 transition-colors hover:bg-line-soft hover:text-ink">
            {tile.label.toLowerCase()} <span className="tabular">0</span>
          </Link>
          {index < tiles.length - 1 ? <span aria-hidden>·</span> : null}
        </span>
      ))}
    </p>
  )
}

function TileCard({ tile }: { tile: DashboardTile }) {
  return (
    <Link
      to={tile.href || "#"}
      className={cn(
        "group rounded-panel border border-line bg-surface shadow-panel p-3 shadow-panel transition-colors",
        tile.urgent
          ? "border-danger/35 hover:border-danger"
          : "border-line hover:border-brand",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-micro font-medium text-ink-soft">{tile.label}</span>
        <ArrowUpRight className="size-3.5 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <div className={cn("figure mt-1", tile.urgent && "text-danger")}>
        {groups(tile.value)}
      </div>
      {tile.hint ? (
        <div className="mt-0.5 truncate text-micro text-ink-faint">{tile.hint}</div>
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

/**
 * Fourteen days of takings.
 *
 * Horizontal gridlines only and no axis lines: the bars are the figure and
 * everything else is scaffolding. Every other day is labelled — fourteen
 * `dd.mm` labels in a column this wide overlap into a grey smear, and the
 * shape of the fortnight is what this chart is for.
 */
function Sales({ points }: { points: SalesPoint[] }) {
  const data = points.map((point) => ({
    day: date(point.day).slice(0, 5),
    orders: point.orders,
    total: point.total,
  }))

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--color-line-soft)" vertical={false} />
          <XAxis
            dataKey="day"
            interval={1}
            tickLine={false}
            axisLine={false}
            tickMargin={6}
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
              boxShadow: "var(--shadow-raised)",
              fontSize: 12,
            }}
            formatter={(value: number, name) =>
              name === "total" ? [money(value), "summa"] : [groups(value), "buyurtma"]
            }
          />
          <Bar dataKey="total" fill="var(--color-brand)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
