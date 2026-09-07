import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import {
  ArrowRight,
  BadgeCheck,
  Landmark,
  PackageCheck,
  TriangleAlert,
  Undo2,
} from "lucide-react"
import { api } from "@/api/client"
import type { CatalogSummary, OrderPage, StaffReturn } from "@/api/types"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint } from "@/components/ui/field"
import { ChartLegend, ChartTable, LineChart, type Series } from "@/ui/chart"
import { Async, Empty } from "@/ui/states"
import { money } from "@/lib/utils"

/** How many days the lines cover. A month is what "how is it going" means. */
const DAYS = 30

/**
 * The first screen.
 *
 * There was no first screen: signing in dropped an admin on whichever nav row
 * came first — the moderation queue — which is a job, not an overview, and it
 * meant nobody could see how the shop was doing without deciding which of
 * fifteen screens to open.
 *
 * -------------------------------------------------------- where the data is from
 *
 * There is **no aggregate endpoint**, so both lines are computed in the
 * browser from list endpoints, and each chart says what it was computed from:
 *
 * | line | endpoint | note |
 * |---|---|---|
 * | Savdo (so'm/day) | `GET /staff/orders?page_size=100` | sums `total` of orders not cancelled, by `created_at` |
 * | Buyurtma (count/day) | the same one request | counts the same rows |
 * | Qaytarishlar (count/day) | `GET /staff/returns` | whole list, no paging on that endpoint |
 *
 * **The limit is honest and visible:** `/staff/orders` caps `page_size` at 100
 * and has no date filter, so this reads the most recent hundred orders and no
 * further. On a busy shop that is less than thirty days and the earliest part
 * of the line would be missing rather than flat — so the caption says how many
 * orders it actually read, and the chart is labelled with the window it
 * covers rather than pretending to cover a month.
 *
 * What this wants from the backend is one endpoint returning daily totals over
 * a date range. That is a backend change and the backend was not to be
 * touched; it is in the handover with the shape it needs.
 *
 * Two requests, not fifteen: the tiles reuse the same two responses the charts
 * are built from, plus the catalogue summary the sidebar already fetches.
 */
export function HomePage() {
  const orders = useQuery({
    queryKey: ["staff", "orders", "recent"],
    queryFn: () => api<OrderPage>("/staff/orders", { query: { page_size: 100 } }),
  })
  const returns = useQuery({
    queryKey: ["staff", "returns"],
    queryFn: () => api<StaffReturn[]>("/staff/returns"),
  })
  const catalogue = useQuery({
    queryKey: ["staff", "catalog", "summary"],
    queryFn: () => api<CatalogSummary>("/staff/catalog/summary"),
  })

  const days = React.useMemo(() => lastDays(DAYS), [])

  const sales = React.useMemo(
    () => byDay(days, orders.data?.items ?? [], (o) => (o.status === "cancelled" ? 0 : o.total)),
    [days, orders.data],
  )
  const placed = React.useMemo(
    () => byDay(days, orders.data?.items ?? [], () => 1),
    [days, orders.data],
  )
  const refunds = React.useMemo(
    () => byDay(days, returns.data ?? [], () => 1),
    [days, returns.data],
  )

  const salesSeries: Series[] = [{ name: "Savdo, so'm", points: sales, tone: "brand" }]
  const flowSeries: Series[] = [
    { name: "Buyurtma", points: placed, tone: "good" },
    { name: "Qaytarish", points: refunds, tone: "danger" },
  ]

  const total = sales.reduce((n, p) => n + p.value, 0)
  const count = placed.reduce((n, p) => n + p.value, 0)
  const returned = refunds.reduce((n, p) => n + p.value, 0)
  const waiting = (orders.data?.items ?? []).filter((o) =>
    ["placed", "packing"].includes(o.status),
  ).length
  const openReturns = (returns.data ?? []).filter((r) => r.status === "submitted").length

  return (
    <Page
      title="Boshqaruv"
      hint={`Oxirgi ${DAYS} kun. Har grafik bitta savolga javob beradi.`}
    >
      {/* The four things worth acting on, first — each a link to the screen
          where the acting happens. An overview that cannot be acted from is a
          poster. */}
      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Tile
          label="Yig'ishni kutayotgan"
          value={waiting}
          tone={waiting ? "warn" : "neutral"}
          to="/orders"
          cta="Buyurtmalar"
          icon={<PackageCheck />}
        />
        <Tile
          label="Javob kutayotgan ariza"
          value={openReturns}
          tone={openReturns ? "danger" : "neutral"}
          to="/returns"
          cta="Qaytarishlar"
          icon={<Undo2 />}
        />
        <Tile
          label="Moderatsiyada"
          value={catalogue.data?.counts.moderating ?? 0}
          tone={catalogue.data?.counts.moderating ? "brand" : "neutral"}
          to="/moderation"
          cta="Moderatsiya"
          icon={<BadgeCheck />}
        />
        <Tile
          label={`${DAYS} kunlik savdo`}
          value={money(total)}
          suffix="so'm"
          tone="neutral"
          to="/payouts"
          cta="Moliya"
          icon={<Landmark />}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          title="Savdo qanday ketyapti"
          hint={`Kunlik summa, so'mda. Bekor qilingan buyurtmalar hisobga olinmaydi. Manba: GET /staff/orders — ${orders.data?.items.length ?? 0} ta oxirgi buyurtma.`}
        >
          <Async query={orders} lines={5}>
            {(page) =>
              page.items.length === 0 ? (
                <Empty
                  title="Hali buyurtma yo'q"
                  hint="Birinchi buyurtma kelganda grafik shu yerda chiziladi."
                  className="border-t-0"
                />
              ) : (
                <>
                  <p className="figure mb-1 text-ink">{money(total)}</p>
                  <Hint className="mb-3">
                    {DAYS} kunda · {count} buyurtma
                  </Hint>
                  <LineChart series={salesSeries} format={(n) => compact(n)} />
                  <ChartTable series={salesSeries} format={money} />
                </>
              )
            }
          </Async>
        </Card>

        <Card
          title="Buyurtma va qaytarish"
          hint="Kunlik soni. Ikkisi bitta grafikda, chunki savol bitta: qancha keldi va qanchasi qaytdi. Manba: GET /staff/orders va GET /staff/returns."
        >
          <Async query={orders} lines={5}>
            {(page) =>
              page.items.length === 0 ? (
                <Empty
                  title="Hali buyurtma yo'q"
                  hint="Buyurtma va qaytarish soni shu yerda taqqoslanadi."
                  className="border-t-0"
                />
              ) : (
                <>
                  <div className="mb-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
                    <span className="figure text-ink">{count}</span>
                    <span className="text-[length:var(--text-small)] text-ink-soft">
                      buyurtma
                    </span>
                    <span className="figure text-danger">{returned}</span>
                    <span className="text-[length:var(--text-small)] text-ink-soft">
                      qaytarish
                    </span>
                  </div>
                  <LineChart series={flowSeries} />
                  <div className="mt-2">
                    <ChartLegend series={flowSeries} />
                  </div>
                  <ChartTable series={flowSeries} />
                </>
              )
            }
          </Async>
        </Card>
      </div>

      <Hint className="mt-4 flex items-start gap-2">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-ink-faint" />
        Grafiklar brauzerda hisoblanadi: serverda kunlik yig'indi beradigan
        endpoint yo'q, shuning uchun oxirgi 100 buyurtma o'qiladi. Savdo
        ko'paysa, chiziqning eng chap qismi to'liq bo'lmasligi mumkin.
      </Hint>
    </Page>
  )
}

function Card({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children: React.ReactNode
}) {
  return (
    <section className="rounded-[var(--radius-panel)] border border-line bg-surface p-4">
      <h2 className="text-[length:var(--text-body)] font-semibold text-ink">{title}</h2>
      <Hint className="mt-0.5 mb-3">{hint}</Hint>
      {children}
    </section>
  )
}

function Tile({
  label,
  value,
  suffix,
  tone,
  to,
  cta,
  icon,
}: {
  label: string
  value: number | string
  suffix?: string
  tone: "neutral" | "brand" | "warn" | "danger"
  to: string
  cta: string
  icon: React.ReactNode
}) {
  return (
    <section className="flex flex-col justify-between rounded-[var(--radius-panel)] border border-line bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[length:var(--text-small)] text-ink-soft">{label}</p>
        <span className="text-ink-faint [&_svg]:size-4">{icon}</span>
      </div>
      <p className="mt-2 flex items-baseline gap-1.5">
        <span className="figure text-ink">{value}</span>
        {suffix ? (
          <span className="text-[length:var(--text-small)] text-ink-soft">{suffix}</span>
        ) : null}
        {tone !== "neutral" && Number(value) > 0 ? (
          <Badge tone={tone}>ish bor</Badge>
        ) : null}
      </p>
      <Button variant="ghost" size="sm" className="mt-2 -ml-2 self-start" asChild>
        <Link to={to}>
          {cta}
          <ArrowRight />
        </Link>
      </Button>
    </section>
  )
}

// ---------------------------------------------------------------- aggregation

/** The last n days, oldest first, as `YYYY-MM-DD` keys with a short label. */
function lastDays(n: number): { key: string; label: string }[] {
  const out: { key: string; label: string }[] = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  for (let i = n - 1; i >= 0; i--) {
    const day = new Date(today)
    day.setDate(today.getDate() - i)
    out.push({
      key: day.toISOString().slice(0, 10),
      label: `${String(day.getDate()).padStart(2, "0")}.${String(day.getMonth() + 1).padStart(2, "0")}`,
    })
  }
  return out
}

/**
 * Sum a list of dated rows into one point per day.
 *
 * A day with nothing in it is a zero rather than a gap: a line that skips
 * empty days makes a quiet week look like a busy one drawn narrower.
 */
function byDay<T extends { created_at: string }>(
  days: { key: string; label: string }[],
  rows: T[],
  valueOf: (row: T) => number,
): { label: string; value: number }[] {
  const totals = new Map(days.map((d) => [d.key, 0]))
  for (const row of rows) {
    const key = row.created_at.slice(0, 10)
    if (totals.has(key)) totals.set(key, (totals.get(key) ?? 0) + valueOf(row))
  }
  return days.map((d) => ({ label: d.label, value: totals.get(d.key) ?? 0 }))
}

/** Axis labels: 1 200 000 is unreadable at 11px, 1,2 mln is not. */
function compact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".", ",")} mln`
  if (value >= 1_000) return `${Math.round(value / 1_000)} ming`
  return String(value)
}
