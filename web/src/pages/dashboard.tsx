/**
 * Boshqaruv — the first screen, and the only one allowed to be a list of
 * numbers.
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
 *
 * ------------------------------------------------------- why it was redrawn
 *
 * The order above was right and the drawing was not.
 *
 * **The three figures of the day were a `flex-wrap` with an `ml-auto` on the
 * end.** Three numbers of three different lengths, each finding its own left
 * edge, one shoved to the far wall — so the panel was a metre of white space
 * with figures scattered along it, and none of the three lined up with
 * anything. They are a three-column grid now, with a rule between them: equal
 * cells, one baseline, and a shape that is the same on a shop screen at
 * 1440 and on a laptop at 1100.
 *
 * **The counters were cards, and cards stretch.** Four across a wide screen
 * meant four boxes that were mostly empty, and a label of three words wrapped
 * to a second line while its neighbour's did not — which moved that card's
 * figure down and left the row looking like a spreadsheet somebody had
 * dragged. They are **rows** now: icon, name, figure, chevron, two to a line,
 * and the figures land in a column you can read down. A row is meant to be as
 * wide as its container. A card that is only wide is just a stretched card.
 *
 * **And every hint was set at the same size as the number it explained** —
 * the type scale in `shared/theme.css` was declared where Tailwind could not
 * see it, so `text-micro` and `text-small` compiled to nothing and the whole
 * app came out at one size. That is fixed in the theme, not here; this screen
 * is simply the one where a missing hierarchy was most obvious.
 */

import {
  ArrowUpRight,
  Boxes,
  CheckCircle2,
  ChevronRight,
  Map,
  PackageMinus,
  PackageSearch,
  PackageX,
  Sparkles,
  Truck,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Link } from "react-router-dom"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { cn } from "@/lib/cn"
import { date, groups, money } from "@/lib/format"
import { useDashboard } from "@/lib/queries"
import { Delta, figureText } from "@/pages/report-chrome"
import type { DashboardTile, Figure, Mover, SalesPoint } from "@/lib/types"

/** The takings tile is the headline of this page, not one card among seven. */
const HEADLINE = "orders_today"

/**
 * A face for each counter, from the same set the menu uses.
 *
 * Not decoration: six rows of grey text are six rows of grey text, and the
 * one about labelled goods waiting in the receiving area is the one somebody
 * is scanning for. The icon is what the eye finds before it has read anything,
 * and it is the *same* icon as the menu item the row leads to.
 */
const FACES: Record<string, LucideIcon> = {
  labelled_unshelved: PackageSearch,
  held_back: Sparkles,
  cells_full: Map,
  sold_out: PackageX,
  low_stock: PackageMinus,
  couriers_out: Truck,
}

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
          <Today headlines={board.data.headlines} />

          <Tasks asking={asking} quiet={quiet} />

          <div className="grid gap-(--gap-page) lg:grid-cols-3 lg:items-start">
            <Panel
              title="So'nggi 14 kun"
              className="lg:col-span-2"
              aside={
                <span className="tabular text-small font-semibold">
                  {money(sales.reduce((sum, one) => sum + one.total, 0))}
                </span>
              }
            >
              {/* Named, because it is a **different axis** from the figures
                  above: this chart is orders as they were placed, and the
                  headline is revenue as it was delivered. Two totals that do
                  not match is fine; two totals that do not say which is which
                  is a bug report. */}
              <p className="mb-3 text-micro text-ink-faint">
                Buyurtma berilgan kun bo'yicha — bekor qilinganlarsiz. Yuqoridagi
                tushum esa yetkazilgan kun bo'yicha.
              </p>
              <Sales points={sales} />
            </Panel>

            <Panel title="Eng ko'p ketgani" bare>
              <Movers rows={board.data.movers} />
            </Panel>
          </div>
        </>
      ) : null}
    </div>
  )
}

/**
 * The day, in the figures somebody actually asks for.
 *
 * **The comparison is the server's, not this component's.** Every trend here
 * used to be differenced in the browser off the last two points of the
 * fortnight chart — which can only ever answer "today against yesterday",
 * answers it wrong at eleven in the morning when today is a third over, and
 * put the definition of the shop's own revenue inside a React component where
 * nobody could test it. Worse, the chart it read is **orders placed**, so the
 * dashboard and `/hisobotlar` could give two answers to "what did the shop
 * take". The figures now arrive already compared, over three windows, from
 * the same server function the reports use.
 *
 * Revenue here is therefore **delivered** revenue, bucketed by the day it was
 * delivered — the reports' definition and the only honest one. The order
 * count is orders *placed*, which is a different question and says so.
 *
 * Four equal cells divided by a rule rather than four floats in a row: the
 * week and the month are figures, not afterthoughts pushed to the right-hand
 * wall, and the eye reads across one line rather than hunting.
 */
function Today({ headlines }: { headlines: Figure[] }) {
  const at = (key: string) => headlines.find((one) => one.key === key)
  const today = at("revenue_today")
  const orders = at("orders_today")
  const week = at("revenue_week")
  const month = at("revenue_month")

  // Before the server sends headlines there is nothing honest to draw, and a
  // panel of noughts is worse than no panel.
  if (!today || !orders) return null

  return (
    <Panel bare>
      <div className="grid grid-cols-2 divide-x divide-line lg:grid-cols-4">
        <Slot
          label="Bugungi tushum"
          figure={today}
          lead
          hint="yetkazilgan kun bo'yicha"
          className="col-span-2 border-b border-line lg:col-span-1 lg:border-b-0"
        />
        <Slot
          label="Bugungi buyurtma"
          figure={orders}
          hint="berilgan kun bo'yicha"
          to="/buyurtmalar"
          className="border-b border-line lg:border-b-0"
        />
        {week ? (
          <Slot
            label="So'nggi 7 kun"
            figure={week}
            hint="oldingi 7 kunga nisbatan"
            to="/hisobotlar?report=savdo"
            className="border-b border-line lg:border-b-0"
          />
        ) : null}
        {month ? (
          <Slot
            label="So'nggi 30 kun"
            figure={month}
            hint="oldingi 30 kunga nisbatan"
            to="/hisobotlar?report=savdo"
          />
        ) : null}
      </div>
    </Panel>
  )
}

/**
 * One cell of the day: a caption, a figure, the server's comparison, and one
 * line saying which day the figure is counted under.
 *
 * A cell with a `to` is a link over its whole area rather than a link around
 * the number — the target is the size of the cell, and the arrow appears on
 * hover so a resting screen is figures and not chrome.
 */
function Slot({
  label,
  figure,
  hint,
  to,
  lead = false,
  className,
}: {
  label: string
  figure: Figure
  hint: string
  to?: string
  /** The one figure the page is about, set a step larger than the rest.
   *  Exactly one cell has this. */
  lead?: boolean
  className?: string
}) {
  const inside = (
    <>
      <div className="flex items-center gap-1">
        <span className="caption truncate">{label}</span>
        {to ? (
          <ArrowUpRight className="size-3 shrink-0 text-ink-faint opacity-0 transition-opacity group-hover:opacity-100" />
        ) : null}
      </div>
      <div className={cn("mt-1.5 truncate", lead ? "display" : "figure")}>
        {figureText(figure)}
      </div>
      <div className="mt-1.5 flex min-h-4 flex-wrap items-center">
        <Delta figure={figure} />
      </div>
      <div className="mt-1 truncate text-micro text-ink-faint">{hint}</div>
    </>
  )

  if (!to) return <div className={cn("min-w-0 p-4", className)}>{inside}</div>
  return (
    <Link
      to={to}
      className={cn("group min-w-0 p-4 transition-colors hover:bg-line-soft", className)}>
      {inside}
    </Link>
  )
}

/**
 * What needs doing, as rows.
 *
 * Two to a line on a desk and one on a phone, hairline-ruled: the figures sit
 * in a column and can be read down it, which four free-standing cards can
 * never do. The rules are gaps in a tinted grid rather than borders on each
 * row — a border on every cell doubles up between neighbours and reads as a
 * table, and an odd count leaves a hole in the tint, so it is filled.
 */
function Tasks({ asking, quiet }: { asking: DashboardTile[]; quiet: DashboardTile[] }) {
  if (!asking.length && !quiet.length) return null

  return (
    <Panel
      title="E'tibor kerak"
      bare
      aside={
        asking.length ? (
          <span className="tabular text-micro font-medium text-ink-soft">
            {asking.length} ta ish
          </span>
        ) : null
      }
    >
      {asking.length ? (
        <div className="grid gap-px bg-line md:grid-cols-2">
          {asking.map((tile) => (
            <Task key={tile.key} tile={tile} />
          ))}
          {asking.length % 2 ? <div className="hidden bg-surface md:block" /> : null}
        </div>
      ) : (
        <div className="flex items-center gap-2 px-3 py-3 text-small text-ink-soft">
          <CheckCircle2 className="size-4 text-good" />
          Hammasi joyida — kutayotgan ish yo'q.
        </div>
      )}

      {quiet.length ? <Clear tiles={quiet} /> : null}
    </Panel>
  )
}

function Task({ tile }: { tile: DashboardTile }) {
  const Face = FACES[tile.key] ?? Boxes
  return (
    <Link
      to={tile.href || "#"}
      className="group flex items-center gap-3 bg-surface px-3 py-2.5 transition-colors hover:bg-line-soft">
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-control transition-colors",
          tile.urgent
            ? "bg-danger-soft text-danger"
            : "bg-line-soft text-ink-soft group-hover:bg-brand-soft group-hover:text-brand-deep",
        )}
      >
        <Face className="size-4" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-small font-medium text-ink">
          {tile.label}
        </span>
        {tile.hint ? (
          <span className="block truncate text-micro text-ink-faint">{tile.hint}</span>
        ) : null}
      </span>

      <span
        className={cn(
          "tabular text-figure font-semibold",
          tile.urgent ? "text-danger" : "text-ink",
        )}
      >
        {groups(tile.value)}
      </span>
      <ChevronRight className="size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
    </Link>
  )
}

/** The counters that are asking for nothing, in one line. Still links. */
function Clear({ tiles }: { tiles: DashboardTile[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-line px-3 py-2">
      <span className="caption">Joyida</span>
      {tiles.map((tile) => (
        <Link
          key={tile.key}
          to={tile.href || "#"}
          className="rounded-full border border-line px-2 py-0.5 text-micro text-ink-soft transition-colors hover:border-brand hover:text-ink">
          {tile.label.toLowerCase()} <span className="tabular font-medium">0</span>
        </Link>
      ))}
    </div>
  )
}

/**
 * What actually left the building, and in what proportion.
 *
 * The bar is the same figure a second time. A column of 6, 2, 1 tells you the
 * order; the bar tells you that the first one is the shop — which is the
 * thing worth going to the market about.
 */
function Movers({ rows }: { rows: Mover[] }) {
  if (rows.length === 0) {
    return (
      <Empty bare what="Hali hech narsa yetkazilmagan." />
    )
  }
  const top = Math.max(...rows.map((one) => one.qty), 1)

  return (
    <ol className="divide-y divide-line">
      {rows.map((mover, index) => (
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
            <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-line-soft">
              <div
                className="h-full rounded-full bg-brand/60"
                style={{ width: `${Math.max(4, (mover.qty / top) * 100)}%` }}
              />
            </div>
          </div>
          <span className="tabular text-small font-semibold">{groups(mover.qty)}</span>
        </li>
      ))}
    </ol>
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
 *
 * Today's bar is the solid one and the thirteen behind it are the same blue
 * at a quarter strength, so "where are we against the fortnight" is answered
 * by the picture rather than by counting columns from the right. The axis was
 * also being clipped — a negative left margin against a 44px gutter cut
 * `1.5M` down to `.5M`, which is a different number.
 */
function Sales({ points }: { points: SalesPoint[] }) {
  const data = points.map((point) => ({
    day: date(point.day).slice(0, 5),
    orders: point.orders,
    total: point.total,
  }))

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--color-line-soft)" vertical={false} />
          <XAxis
            dataKey="day"
            interval={1}
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            width={52}
            tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
            // Abbreviated, because a day's takings are seven digits and an
            // axis that prints them all is an axis that clips them instead.
            tickFormatter={short}
          />
          <Tooltip
            cursor={{ fill: "var(--color-brand-soft)" }}
            content={<Tip />}
            // The library's own box prints `summa : 0 so'm` with the spaces of
            // a debug dump. A tooltip is read more often than the axis is.
          />
          <Bar
            dataKey="total"
            radius={[5, 5, 0, 0]}
            maxBarSize={44}
            // The panel refetches while somebody is looking at it, and a bar
            // that grows up from the floor every time is a page that will not
            // sit still.
            isAnimationActive={false}>
            {data.map((row, index) => (
              <Cell
                key={row.day}
                fill="var(--color-brand)"
                fillOpacity={index === data.length - 1 ? 1 : 0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

type Point = { day: string; orders: number; total: number }

function Tip({
  active,
  payload,
}: {
  active?: boolean
  payload?: { payload: Point }[]
}) {
  const point = payload?.[0]?.payload
  if (!active || !point) return null
  return (
    <div className="rounded-control border border-line bg-surface px-2.5 py-2 shadow-raised">
      <div className="caption">{point.day}</div>
      <div className="tabular text-small font-semibold">{money(point.total)}</div>
      <div className="tabular text-micro text-ink-faint">
        {groups(point.orders)} buyurtma
      </div>
    </div>
  )
}
