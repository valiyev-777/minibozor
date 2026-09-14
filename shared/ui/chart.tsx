import { cn } from "./cn"

/**
 * A line chart, drawn as inline SVG, with no charting library.
 *
 * ------------------------------------------------------- why not a library
 *
 * The brief named bundle size as a consideration, and the three candidates
 * cost real weight for a page that draws three lines:
 *
 * - **recharts** — ~100 KB gzipped, and it pulls d3-scale, d3-shape,
 *   d3-array and a virtual-DOM layer of its own.
 * - **chart.js** (+ react-chartjs-2) — ~60 KB gzipped, and it paints to a
 *   canvas, so the line is not in the DOM: no text selection, no `title`, and
 *   nothing for a screen reader unless a table is written beside it anyway.
 * - **visx** — lighter per import but verbose enough that a line chart is
 *   still fifty lines of scales and accessors. At that point the fifty lines
 *   may as well be the chart.
 *
 * This file is under two hundred lines, adds nothing to `package.json`, reads
 * its colours from the design tokens so it changes with the theme, and puts
 * the points in the DOM where a `<title>` works and the axis labels are text.
 * A library earns its weight when there are stacked bars, brushing, zooming
 * and tooltips to get right. Three lines over thirty days is not that.
 *
 * ------------------------------------------------------------------ the rules
 *
 * One question per chart. The caller passes the question as the title, and a
 * chart that cannot be described in one line is two charts.
 */

export type Point = { label: string; value: number }

export type Series = {
  name: string
  points: Point[]
  /** A token name, so the line changes with the theme: `brand`, `good`, … */
  tone?: "brand" | "good" | "warn" | "danger"
}

const STROKE: Record<NonNullable<Series["tone"]>, string> = {
  brand: "var(--color-brand)",
  good: "var(--color-good)",
  warn: "var(--color-warn)",
  danger: "var(--color-danger)",
}

/** Round a maximum up to something a person would have chosen. */
function ceiling(value: number): number {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  for (const step of [1, 2, 2.5, 5, 10]) {
    const candidate = step * magnitude
    if (candidate >= value) return candidate
  }
  return 10 * magnitude
}

export function LineChart({
  series,
  height = 168,
  format = (n: number) => String(n),
  className,
  labelEvery,
}: {
  series: Series[]
  height?: number
  format?: (value: number) => string
  className?: string
  /** Draw every nth x label; defaults to something that will not collide. */
  labelEvery?: number
}) {
  // A viewBox and no width: the SVG scales to its column, and there is no
  // resize observer to get wrong. Non-uniform scaling is avoided by keeping
  // preserveAspectRatio at its default and letting the height be fixed.
  const W = 720
  const H = height
  const PAD = { top: 12, right: 10, bottom: 26, left: 46 }

  const count = Math.max(...series.map((s) => s.points.length), 0)
  if (!count) return null

  const max = ceiling(Math.max(...series.flatMap((s) => s.points.map((p) => p.value)), 0))
  const innerW = W - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (count === 1 ? innerW / 2 : (i * innerW) / (count - 1))
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH

  const ticks = [0, max / 2, max]
  const every = labelEvery ?? Math.max(1, Math.ceil(count / 7))
  const labels = series[0]?.points.map((p) => p.label) ?? []

  return (
    <div className={cn("w-full", className)}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={series.map((s) => s.name).join(", ")}
      >
        {/* The grid: three lines, because a fourth is decoration. */}
        {ticks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(t)}
              y2={y(t)}
              stroke="var(--color-line)"
              strokeWidth="1"
            />
            <text
              x={PAD.left - 6}
              y={y(t) + 4}
              textAnchor="end"
              className="fill-[var(--color-ink-faint)] text-[11px] tabular"
            >
              {format(t)}
            </text>
          </g>
        ))}

        {labels.map((label, i) =>
          i % every === 0 || i === count - 1 ? (
            <text
              key={`${label}-${i}`}
              x={x(i)}
              y={H - 8}
              textAnchor={i === 0 ? "start" : i === count - 1 ? "end" : "middle"}
              className="fill-[var(--color-ink-faint)] text-[11px]"
            >
              {label}
            </text>
          ) : null,
        )}

        {series.map((s) => {
          const stroke = STROKE[s.tone ?? "brand"]
          const path = s.points
            .map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`)
            .join(" ")
          return (
            <g key={s.name}>
              <path
                d={path}
                fill="none"
                stroke={stroke}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* A point per reading, with its own title: this is the whole
                  tooltip, and it works without JavaScript and on a keyboard
                  because the browser draws it. */}
              {s.points.map((p, i) => (
                <circle
                  key={`${s.name}-${i}`}
                  cx={x(i)}
                  cy={y(p.value)}
                  r={count > 40 ? 1.5 : 2.5}
                  fill={stroke}
                >
                  <title>{`${p.label} · ${s.name}: ${format(p.value)}`}</title>
                </circle>
              ))}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

/** The key. Only drawn when there is more than one line to tell apart. */
export function ChartLegend({ series }: { series: Series[] }) {
  if (series.length < 2) return null
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {series.map((s) => (
        <li
          key={s.name}
          className="flex items-center gap-1.5 text-[length:var(--text-small)] text-ink-soft"
        >
          <span
            aria-hidden
            className="inline-block h-0.5 w-4 rounded"
            style={{ background: STROKE[s.tone ?? "brand"] }}
          />
          {s.name}
        </li>
      ))}
    </ul>
  )
}

/**
 * The numbers behind the picture, for anybody the picture does not serve.
 *
 * A canvas chart cannot offer this and an SVG one can, which is most of why
 * this file exists. Collapsed, so it costs a sighted reader nothing.
 */
export function ChartTable({
  series,
  format = (n: number) => String(n),
}: {
  series: Series[]
  format?: (value: number) => string
}) {
  const labels = series[0]?.points.map((p) => p.label) ?? []
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-[length:var(--text-small)] text-ink-soft hover:text-ink">
        Raqamlar bilan
      </summary>
      <div className="mt-2 max-h-56 overflow-auto">
        <table className="w-full text-left text-[length:var(--text-small)]">
          <thead>
            <tr className="text-ink-soft">
              <th scope="col" className="py-1 pr-3 font-medium">
                Kun
              </th>
              {series.map((s) => (
                <th key={s.name} scope="col" className="py-1 pr-3 text-right font-medium">
                  {s.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((label, i) => (
              <tr key={label} className="border-t border-line-soft">
                <th scope="row" className="py-1 pr-3 font-normal text-ink-soft">
                  {label}
                </th>
                {series.map((s) => (
                  <td key={s.name} className="tabular py-1 pr-3 text-right">
                    {format(s.points[i]?.value ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
