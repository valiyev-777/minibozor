/**
 * The furniture the six reports share: the period, the figure, and the chart.
 *
 * ------------------------------------------------------------- the period
 *
 * One control, above everything it scopes, and it lives in the **address
 * bar**. Not a preference and not component state: a report is a thing one
 * person sends another ("look at last week's returns"), and a period held in
 * `useState` makes that a sentence describing where to click. `from`, `to`,
 * `bucket` and `report` are all query parameters, so every view of every
 * report has an address.
 *
 * ------------------------------------------------------------- the figure
 *
 * A `Figure` off the wire already carries the period before it, the
 * difference and the percentage. This file draws them and does **no
 * arithmetic** — the two nulls in that type are the whole point and each one
 * means something different:
 *
 * * `previous === null` — the shop cannot answer. What is standing on the
 *   shelf today is a fact; what was standing there a month ago was never
 *   recorded. So: **no arrow**, and a line saying it is today's state.
 * * `percent === null` with a real `delta` — the period before was nought.
 *   Something did happen and it has no percentage, so the arrow is drawn and
 *   the percentage is simply absent.
 *
 * Colour is a judgement and is therefore separate from the arrow, which is a
 * fact. More cancellations is a red rise; more market runs is neither, and
 * painting it green would be the screen having an opinion it cannot support.
 *
 * ------------------------------------------------------------- the chart
 *
 * Every colour is a theme token, so both modes come for free. The palette is
 * deliberately tiny and it is **not a categorical one**:
 *
 * * one series — the brand hue, no legend, the title names it;
 * * two series where one is the subject — brand against `ink-soft`, which is
 *   the de-emphasis grey and is *supposed* to read as grey;
 * * three series that are states — `good` / `danger` / `warn`, the same three
 *   meanings the pills use, never borrowed for anything that is not a state.
 *
 * Two shades of the brand were tried for the two-series case and dropped: a
 * lighter step of one hue either drops under 3:1 on the surface or lands too
 * close to its own parent to tell apart, and a reader who has to squint at
 * two blues is a reader who reads the table instead.
 *
 * Which is why **every chart has a table**. The toggle is not decoration: a
 * chart answers "what shape", a table answers "how much", and several of
 * these series sit below 3:1 against a white card, where the numbers have to
 * be reachable some other way.
 */

import { ArrowDown, ArrowRight, ArrowUp, BarChart3 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Empty, Panel, Problem, Segmented, Waiting } from "@/components/page"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { date, groups, money } from "@/lib/format"
import type { Bucket, Figure, ReportPeriod } from "@/lib/types"

/* ------------------------------------------------------------- the period */

/** The presets an owner actually asks for, and the grouping each implies. */
const PRESETS: Array<{ key: string; label: string; days: number; bucket: Bucket }> = [
  { key: "7", label: "7 kun", days: 7, bucket: "day" },
  { key: "30", label: "30 kun", days: 30, bucket: "day" },
  { key: "90", label: "90 kun", days: 90, bucket: "week" },
  { key: "365", label: "1 yil", days: 365, bucket: "month" },
]

const BUCKETS: Array<{ key: Bucket; label: string }> = [
  { key: "day", label: "Kunlar" },
  { key: "week", label: "Haftalar" },
  { key: "month", label: "Oylar" },
]

export type Period = {
  from: string
  to: string
  bucket: Bucket
  /** Which preset this is, or `null` when the dates were typed by hand. */
  preset: string | null
  setPreset: (key: string) => void
  setFrom: (day: string) => void
  setTo: (day: string) => void
  setBucket: (bucket: Bucket) => void
}

/** `2026-09-11` — the wire's own spelling of a day, which is not the one a
 *  person reads. `date()` handles the reading. */
function iso(when: Date): string {
  return [
    when.getFullYear(),
    String(when.getMonth() + 1).padStart(2, "0"),
    String(when.getDate()).padStart(2, "0"),
  ].join("-")
}

function shift(from: string, days: number): string {
  const when = new Date(`${from}T00:00:00`)
  when.setDate(when.getDate() + days)
  return iso(when)
}

export function usePeriod(): Period {
  const [params, setParams] = useSearchParams()

  const patch = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [name, value] of Object.entries(changes)) {
      if (value === null) next.delete(name)
      else next.set(name, value)
    }
    setParams(next, { replace: true })
  }

  const today = iso(new Date())
  const to = params.get("to") || today
  // The server's own default, spelled here as well, because the control has
  // to show the period it is asking for even before anybody has touched it.
  const from = params.get("from") || shift(to, -29)
  const raw = params.get("bucket")
  const bucket: Bucket =
    raw === "week" || raw === "month" || raw === "day" ? raw : "day"

  const span = Math.round(
    (new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) /
      86_400_000,
  )
  const preset =
    to === today
      ? (PRESETS.find((one) => one.days - 1 === span)?.key ?? null)
      : null

  return {
    from,
    to,
    bucket,
    preset,
    setPreset: (key) => {
      const found = PRESETS.find((one) => one.key === key)
      if (!found) return
      const end = iso(new Date())
      // The grouping moves with the preset: a year in daily buckets is 365
      // columns in a card 700px wide, which is a grey smear and not a shape.
      patch({ to: end, from: shift(end, -(found.days - 1)), bucket: found.bucket })
    },
    setFrom: (day) => patch({ from: day }),
    setTo: (day) => patch({ to: day }),
    setBucket: (next) => patch({ bucket: next }),
  }
}

/**
 * The control, and the sentence saying what is being compared with what.
 *
 * The sentence is not a caption — the previous period is **the server's
 * choice** (the same number of days, ending the day before this one begins),
 * and every arrow on the screen is against it. A screen that drew arrows
 * without naming the period behind them is asking to be misread.
 */
export function PeriodControls({
  period,
  span,
}: {
  period: Period
  /** The period the server echoed back. Absent until the first answer. */
  span?: ReportPeriod
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          label="Davr"
          value={period.preset}
          onChange={period.setPreset}
          options={PRESETS.map((one) => ({ key: one.key, label: one.label }))}
        />
        <div className="flex items-center gap-1">
          <Input
            type="date"
            aria-label="Boshlanishi"
            value={period.from}
            max={period.to}
            onChange={(event) => period.setFrom(event.target.value)}
            className="w-36"
          />
          <span className="text-small text-ink-faint">–</span>
          <Input
            type="date"
            aria-label="Tugashi"
            value={period.to}
            min={period.from}
            onChange={(event) => period.setTo(event.target.value)}
            className="w-36"
          />
        </div>
        <Segmented
          label="Guruhlash"
          value={period.bucket}
          onChange={period.setBucket}
          options={BUCKETS}
        />
      </div>
      {span ? (
        <p className="text-micro text-ink-faint">
          {date(span.from_day)} – {date(span.to_day)} ({span.days} kun) ·
          taqqoslanmoqda: {date(span.previous_from_day)} –{" "}
          {date(span.previous_to_day)}
        </p>
      ) : null}
    </div>
  )
}

/* -------------------------------------------------------------- the figure */

/**
 * Where a rise is bad news.
 *
 * Sorted into three because two is a lie. Cancellations up is red, revenue up
 * is green, and market runs up is **neither** — a shop that went to the bazaar
 * more often this month did not thereby do better or worse, and a green arrow
 * would be the screen claiming otherwise.
 */
const UP_IS_BAD = new Set([
  "cancelled",
  "returned",
  "cancel_rate",
  "refunds",
  "discount",
  "money_out",
  "written_off",
  "damaged_units",
  "returns_opened",
  "returns_rate",
  "returns_rejected",
  "inspected_damaged",
])

const UP_IS_NEITHER = new Set([
  "runs",
  "units_bought",
  "average_run",
  "transport",
  "attempts",
  "signups",
])

/**
 * The wire is integers all the way through, and three of them mean different
 * things.
 *
 * So'm, a plain count, hundredths of a per cent — and one figure that is
 * hundredths of *an order*, which carries no flag because there is no flag
 * for it. `orders_per_customer` printed as the integer it arrives as reads
 * "650 buyurtma har xaridorga", which is the kind of number somebody repeats
 * in a meeting.
 */
export function figureText(figure: Figure): string {
  if (figure.money) return money(figure.value)
  if (figure.percent_value) return percentText(figure.value)
  if (figure.key === "orders_per_customer") return hundredths(figure.value)
  return groups(figure.value)
}

/** `90,9%` from 9091. The comma is the decimal point here. */
export function percentText(hundredthsOfPercent: number | null): string {
  if (hundredthsOfPercent === null) return "—"
  return `${hundredths(hundredthsOfPercent)}%`
}

function hundredths(value: number): string {
  const whole = Math.trunc(value / 100)
  const rest = Math.abs(value % 100)
  if (rest === 0) return groups(whole)
  const decimal = Math.round(rest / 10)
  return decimal === 0
    ? groups(whole)
    : `${value < 0 && whole === 0 ? "-" : ""}${groups(whole)},${decimal}`
}

/** The same value, without its unit — for a delta, where the unit is already
 *  on the figure above it. */
function deltaText(figure: Figure, delta: number): string {
  const sign = delta > 0 ? "+" : ""
  if (figure.money) return `${sign}${money(delta)}`
  if (figure.percent_value) return `${sign}${percentText(delta)}`
  if (figure.key === "orders_per_customer") return `${sign}${hundredths(delta)}`
  return `${sign}${groups(delta)}`
}

/**
 * The arrow — or, where the shop cannot answer, no arrow at all.
 *
 * Three states and they are all different. A null previous is a figure about
 * *now* with no history behind it. A nought delta is a period that did the
 * same as the one before. A real delta with a null percentage is a rise from
 * nothing, which has a direction and no ratio.
 */
export function Delta({ figure }: { figure: Figure }) {
  if (figure.previous === null || figure.delta === null) {
    return (
      <span className="text-micro text-ink-faint">bugungi holat · taqqoslanmaydi</span>
    )
  }

  const delta = figure.delta
  const rising = delta > 0
  const tone = UP_IS_NEITHER.has(figure.key)
    ? "quiet"
    : UP_IS_BAD.has(figure.key) === rising
      ? "bad"
      : "good"

  const Glyph = delta === 0 ? ArrowRight : rising ? ArrowUp : ArrowDown

  return (
    <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5">
      <span
        className={cn(
          "inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-micro font-medium",
          delta === 0 && "bg-line-soft text-ink-soft",
          delta !== 0 && tone === "good" && "bg-good-soft text-good",
          delta !== 0 && tone === "bad" && "bg-danger-soft text-danger",
          delta !== 0 && tone === "quiet" && "bg-line-soft text-ink-soft",
        )}
      >
        <Glyph className="size-3" />
        {/* The percentage where there is one, the difference itself where
            there is not — "up from nothing" has a direction and no ratio. */}
        {delta === 0
          ? "o'zgarmadi"
          : figure.percent !== null
            ? `${figure.percent > 0 ? "+" : ""}${String(figure.percent).replace(".", ",")}%`
            : deltaText(figure, delta)}
      </span>
      <span className="truncate text-micro text-ink-faint">
        oldin{" "}
        {figureText({ ...figure, value: figure.previous })}
      </span>
    </span>
  )
}

/** One headline: its name, its number, and what the period before said. */
export function FigureTile({
  figure,
  hint,
  lead = false,
}: {
  figure: Figure
  /** A sentence this particular figure cannot be read without. */
  hint?: React.ReactNode
  /** The one figure the report exists to show — at most one per report. */
  lead?: boolean
}) {
  return (
    <div className="flex min-w-0 flex-col justify-between gap-2 p-4">
      <span className="caption truncate">{figure.label}</span>
      <div>
        <div className={cn("truncate", lead ? "display" : "figure")}>
          {figureText(figure)}
        </div>
        <div className="mt-1.5 flex min-h-4 flex-wrap items-center gap-x-2">
          <Delta figure={figure} />
        </div>
        {hint ? (
          <p className="mt-1 text-micro text-ink-faint">{hint}</p>
        ) : null}
      </div>
    </div>
  )
}

/**
 * The headline row.
 *
 * A hairline grid rather than free-standing cards: eleven cards in a wrap
 * find eleven different left edges, and the point of a row of figures is that
 * the eye reads *down* the column of numbers. `lead` sets the one figure the
 * report is about a size larger and gives it the width of two.
 */
export function Figures({
  figures,
  lead,
  hints = {},
}: {
  figures: Figure[]
  /** The key of the headline figure, drawn large across two cells. */
  lead?: string
  hints?: Record<string, React.ReactNode>
}) {
  if (!figures.length) return null
  // The lead takes two cells, so eleven headlines is twelve cells and one
  // hole — and the hole shows the grid's own hairline colour as a block of
  // grey the size of a card. An odd count is the normal case here, so the
  // trailing cells are filled, and filled **per breakpoint**: three blanks
  // added for a four-column row become an entire empty row at two columns.
  const cells = figures.length + (figures.some((one) => one.key === lead) ? 1 : 0)
  const wide = (4 - (cells % 4)) % 4
  const half = (2 - (cells % 2)) % 2

  return (
    <Panel bare>
      <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-4 [&>*]:bg-surface">
        {figures.map((figure) =>
          figure.key === lead ? (
            // Two cells wide, because the figure a report exists to show is
            // seven digits and a unit, and a quarter of a card truncates it.
            <div key={figure.key} className="sm:col-span-2">
              <FigureTile figure={figure} hint={hints[figure.key]} lead />
            </div>
          ) : (
            <FigureTile
              key={figure.key}
              figure={figure}
              hint={hints[figure.key]}
            />
          ),
        )}
        {Array.from({ length: wide }).map((_, at) => (
          <div
            key={`gap-${at}`}
            className={at < half ? "hidden sm:block" : "hidden lg:block"}
            aria-hidden
          />
        ))}
      </div>
    </Panel>
  )
}

/* --------------------------------------------------------------- the chart */

/**
 * The whole chart palette. Four entries, every one a theme token.
 *
 * `lead` is the accent and means "this is the series the panel is about".
 * `quiet` is the de-emphasis grey — it is meant to read as grey and is what
 * the second series of a two-series chart wears. The remaining three are the
 * *state* colours this app already uses on every pill, and they are never
 * borrowed to mean "series four".
 */
export const PAINT = {
  lead: "var(--color-brand)",
  quiet: "var(--color-ink-soft)",
  good: "var(--color-good)",
  warn: "var(--color-warn)",
  danger: "var(--color-danger)",
} as const

export type Paint = keyof typeof PAINT

export type Line = {
  /** The field on the row. */
  key: string
  label: string
  paint: Paint
  /** Segments of one column rather than columns side by side. */
  stack?: boolean
}

/**
 * `2M`, `13,5M`, `500k`, `0` — an axis tick, not a price.
 *
 * The comma is the decimal point here, as it is everywhere else on these
 * screens. A tick reading `13.5M` beside a figure reading `13 500 000 so'm`
 * is two conventions on one card.
 */
function short(value: number): string {
  const size = Math.abs(value)
  if (size >= 1_000_000)
    return `${String(Math.round((value / 1_000_000) * 10) / 10).replace(".", ",")}M`
  if (size >= 1_000) return `${Math.round(value / 1_000)}k`
  return String(value)
}

type Row = { label: string } & Record<string, number | string>

/**
 * A series over the period, as a shape and as a table.
 *
 * **One unit per chart.** So'm and counts never share an axis — two scales on
 * one plot invent a correlation that is not in the data, and the two here are
 * genuinely two questions ("what did we take" and "how many parcels"). Where
 * both matter they are two panels.
 *
 * The table is not a fallback for a broken chart; it is the other half of the
 * same panel. Three of the five paints sit below 3:1 against a white card,
 * and the numbers have to be readable without relying on the fill.
 */
export function Trend({
  title,
  note,
  rows,
  lines,
  unit,
  kind = "bar",
  aside,
  empty = "Bu davrda hech narsa bo'lmagan.",
}: {
  title: string
  /** Which day a bucket is counted under — the one thing about these series
   *  a reader cannot work out and must not guess. */
  note?: string
  rows: Row[]
  lines: Line[]
  unit: "money" | "count"
  kind?: "bar" | "area"
  aside?: React.ReactNode
  empty?: string
}) {
  const [view, setView] = useState<"chart" | "table">("chart")

  const total = useMemo(
    () =>
      rows.reduce(
        (sum, row) =>
          sum + lines.reduce((part, line) => part + Number(row[line.key] ?? 0), 0),
        0,
      ),
    [rows, lines],
  )

  const print = (value: number) => (unit === "money" ? money(value) : groups(value))


  return (
    <Panel
      title={title}
      aside={
        <div className="flex items-center gap-2">
          {aside}
          <Segmented
            label="Ko'rinish"
            value={view}
            onChange={setView}
            options={[
              { key: "chart" as const, label: "Grafik" },
              { key: "table" as const, label: "Jadval" },
            ]}
          />
        </div>
      }
    >
      {note ? <p className="mb-3 text-micro text-ink-faint">{note}</p> : null}

      {lines.length > 1 ? (
        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1">
          {lines.map((line) => (
            <span
              key={line.key}
              className="inline-flex items-center gap-1.5 text-micro text-ink-soft"
            >
              <span
                aria-hidden
                className="size-2.5 rounded-[2px]"
                style={{ background: PAINT[line.paint] }}
              />
              {line.label}
            </span>
          ))}
        </div>
      ) : null}

      {total === 0 ? (
        <Empty bare icon={BarChart3} title="Hali ma'lumot yo'q" what={empty} />
      ) : view === "table" ? (
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-small">
            <thead className="sticky top-0 bg-line-soft">
              <tr>
                <th className="px-3 py-2 text-start text-micro font-medium text-ink-soft">
                  Davr
                </th>
                {lines.map((line) => (
                  <th
                    key={line.key}
                    className="px-3 py-2 text-end text-micro font-medium text-ink-soft"
                  >
                    {line.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.label} className={index % 2 ? "bg-line-soft/60" : ""}>
                  <td className="px-3 py-2 whitespace-nowrap">{row.label}</td>
                  {lines.map((line) => (
                    <td key={line.key} className="px-3 py-2 text-end tabular">
                      {print(Number(row[line.key] ?? 0))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            {kind === "area" ? (
              <AreaChart data={rows} margin={{ top: 8, right: 28, bottom: 0, left: 0 }}>
                {chrome({ unit, print, lines })}
                {lines.map((line) => (
                  <Area
                    key={line.key}
                    dataKey={line.key}
                    name={line.label}
                    stroke={PAINT[line.paint]}
                    strokeWidth={2}
                    fill={PAINT[line.paint]}
                    fillOpacity={0.1}
                    isAnimationActive={false}
                  />
                ))}
              </AreaChart>
            ) : (
              <BarChart data={rows} margin={{ top: 8, right: 28, bottom: 0, left: 0 }}>
                {chrome({ unit, print, lines })}
                {lines.map((line) => (
                  <Bar
                    key={line.key}
                    dataKey={line.key}
                    name={line.label}
                    stackId={line.stack ? "one" : undefined}
                    fill={PAINT[line.paint]}
                    maxBarSize={24}
                    radius={line.stack ? 0 : [3, 3, 0, 0]}
                    // The 2px separator between touching fills, drawn in the
                    // card's own colour — the gap is what separates two
                    // segments of a stack, never a rule around each of them.
                    stroke={line.stack ? "var(--color-surface)" : undefined}
                    strokeWidth={line.stack ? 2 : 0}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  )
}

/**
 * Grid, axes and tooltip — the same on every chart in the app.
 *
 * **An array, deliberately, and not a component.** Recharts finds its axes by
 * walking the plot's own children and matching their element type, so an
 * `<Chrome/>` wrapper is a child it does not recognise: the first drawing of
 * these panels came out as marks floating in a white box with no axis, no
 * ticks and no grid, because all three had been hidden inside a component of
 * ours. `Children.toArray` flattens an array, so a keyed array is the one
 * shape that can be shared *and* still be seen.
 *
 * Horizontal hairlines only and no axis rules: the marks are the data and
 * everything else is scaffolding that should be almost invisible.
 */
function chrome({
  unit,
  print,
  lines,
}: {
  unit: "money" | "count"
  print: (value: number) => string
  lines: Line[]
}) {
  return [
      <CartesianGrid key="grid" stroke="var(--color-line)" vertical={false} />,
      <XAxis
        key="x"
        dataKey="label"
        // Recharts drops whatever will not fit rather than a fixed every-nth:
        // "13-avgust" is fifty pixels wide, and eight of them across a phone
        // are a grey smear where an axis should be.
        interval="preserveStartEnd"
        minTickGap={28}
        tickLine={false}
        axisLine={false}
        tickMargin={8}
        tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
      />,
      <YAxis
        key="y"
        // Half a parcel is not a quantity. A count axis whose top is 2 was
        // drawing 0 / 0,5 / 1 / 1,5 / 2.
        allowDecimals={unit === "money"}
        tickLine={false}
        axisLine={false}
        width={unit === "money" ? 56 : 44}
        tick={{ fontSize: 11, fill: "var(--color-ink-faint)" }}
        tickFormatter={short}
      />,
      <Tooltip
        key="tip"
        cursor={{ fill: "var(--color-brand)", fillOpacity: 0.08 }}
        content={<Tip print={print} lines={lines} />}
      />,
  ]
}

function Tip({
  active,
  label,
  payload,
  print,
  lines,
}: {
  active?: boolean
  label?: string
  payload?: Array<{ dataKey?: string | number; value?: number }>
  print: (value: number) => string
  lines: Line[]
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-control border border-line bg-surface px-2.5 py-2 shadow-raised">
      <div className="caption">{label}</div>
      {lines.map((line) => {
        const found = payload.find((one) => one.dataKey === line.key)
        if (!found) return null
        return (
          <div
            key={line.key}
            className="flex items-center gap-2 text-small whitespace-nowrap"
          >
            <span
              aria-hidden
              className="size-2 shrink-0 rounded-[2px]"
              style={{ background: PAINT[line.paint] }}
            />
            <span className="text-ink-soft">{line.label}</span>
            <span className="ms-auto tabular font-semibold">
              {print(Number(found.value ?? 0))}
            </span>
          </div>
        )
      })}
    </div>
  )
}

/* ---------------------------------------------------------------- the rest */

/**
 * A sentence the figures above cannot be read without.
 *
 * Not an error and not a warning — the amber one is for a series that is
 * knowingly understating itself, and the plain one for a definition somebody
 * would otherwise assume wrongly.
 */
export function Note({
  children,
  tone = "quiet",
}: {
  children: React.ReactNode
  tone?: "quiet" | "warn"
}) {
  return (
    <p
      className={cn(
        "rounded-control px-3 py-2 text-small",
        tone === "warn"
          ? "bg-warn-soft text-warn-ink"
          : "bg-line-soft text-ink-soft",
      )}
    >
      {children}
    </p>
  )
}

/**
 * A share of a total, as a width and as a number.
 *
 * Never the width alone: a bar in a ranked list is the same information a
 * second time, and the figure beside it is the one somebody quotes.
 */
export function Share({ percent }: { percent: number }) {
  return (
    <div className="h-1.5 w-full min-w-16 overflow-hidden rounded-full bg-line-soft">
      <div
        className="h-full rounded-full bg-brand"
        style={{ width: `${Math.min(100, Math.max(percent > 0 ? 4 : 0, percent))}%` }}
      />
    </div>
  )
}

/** A change against the period before, inside a table cell. */
export function Move({
  delta,
  money: asMoney = false,
  goodWhenUp = true,
}: {
  delta: number
  money?: boolean
  goodWhenUp?: boolean
}) {
  if (delta === 0) return <span className="text-ink-faint">—</span>
  const good = delta > 0 === goodWhenUp
  return (
    <span
      className={cn(
        "tabular whitespace-nowrap",
        good ? "text-good" : "text-danger",
      )}
    >
      {delta > 0 ? "+" : ""}
      {asMoney ? money(delta) : groups(delta)}
    </span>
  )
}

/* ------------------------------------------------------------- the wrapper */

/**
 * What every report is handed and what it hands back.
 *
 * The period comes down from the one control on the screen; the *server's*
 * period goes back up, because the comparison sentence beside that control
 * names a stretch of days the server chose and the client must not guess at.
 */
export type ReportProps = {
  period: Period
  onSpan: (span: ReportPeriod | undefined) => void
}

/**
 * The three states every report has, once.
 *
 * `waiting` is only the *first* answer. A refetch after the period moved
 * holds the previous render — a skeleton that flashes on every date change
 * makes the page jump and loses the reader's place.
 */
export function ReportBody({
  query,
  span,
  onSpan,
  children,
}: {
  query: { isLoading: boolean; error: unknown; data?: unknown }
  span: ReportPeriod | undefined
  onSpan: (span: ReportPeriod | undefined) => void
  children: React.ReactNode
}) {
  useEffect(() => onSpan(span), [span, onSpan])

  if (query.error) return <Problem error={query.error} />
  if (!query.data) return <Waiting what="Hisobot" />
  return (
    <div
      className={cn(
        "space-y-(--gap-page) transition-opacity",
        query.isLoading && "opacity-60",
      )}
    >
      {children}
    </div>
  )
}
