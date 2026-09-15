/**
 * 2h — Daromad. What the work came to, and the doors behind it.
 *
 * ----------------------------------------------------------------- departures
 *
 * Two, and both are the same decision: **a chart of data that does not exist
 * is not a chart.**
 *
 * The artboard's periods are `Bugun / Hafta / Oy` and its centrepiece is a row
 * of seven bars — by hour for a day, by weekday for a week. `GET
 * /courier/earnings` answers with exactly three windows: today, this month,
 * and the lifetime, each as a count and a sum. There is no week, and there is
 * nothing per-hour or per-day: earnings are counted off `DeliveryAttempt` rows
 * on the server and the rows themselves are not exposed. So the segmented
 * control is `Bugun / Shu oy / Jami` — the three the server actually has, with
 * the middle one renamed from the window nobody can compute — and the seven
 * bars are gone rather than fabricated from the one number that is left.
 *
 * What replaces them is a real comparison and a small one: what today is
 * against the month it sits in. That is a bar somebody can check.
 *
 * `OXIRGI YETKAZISHLAR` is kept and is real — `GET /courier/orders?done=true`,
 * newest first. It has no delivery *time* on it (the courier's order shape
 * carries no timestamp), so the row says what it can: the address, the code,
 * and what the parcel came to. The artboard's `14:20 · naqd` becomes
 * `naqd` / `onlayn`, which is the half of that line a courier reads back for.
 */

import { CheckCircle2, ClipboardCheck } from "lucide-react"
import { useMemo, useState } from "react"

import {
  Cap,
  Glass,
  Loading,
  Nothing,
  Page,
  Refusal,
  Tile,
  Title,
} from "@/components/kuryer/bits"
import { cn } from "@/lib/cn"
import { dayMonth, groups, money, percent } from "@/lib/format"
import { useEarnings, useMyHistory } from "@/lib/queries"
import { useSession } from "@/lib/session"

type Window = "today" | "month" | "total"

const WINDOWS: Array<{ key: Window; label: string; head: string }> = [
  { key: "today", label: "Bugun", head: "Bugun" },
  { key: "month", label: "Shu oy", head: "Shu oy" },
  { key: "total", label: "Jami", head: "Boshidan beri" },
]

export function KuryerEarnings() {
  const { staff } = useSession()
  const earnings = useEarnings()
  const history = useMyHistory()
  const [window, setWindow] = useState<Window>("today")

  const done = useMemo(
    () =>
      (history.data ?? [])
        .filter((one) => one.status === "delivered")
        .sort((a, b) => b.id - a.id)
        .slice(0, 12),
    [history.data],
  )

  const data = earnings.data
  const sum = data
    ? window === "today"
      ? data.earned_today
      : window === "month"
        ? data.earned_month
        : data.earned_total
    : 0
  const count = data
    ? window === "today"
      ? data.delivered_today
      : window === "month"
        ? data.delivered_month
        : data.delivered_total
    : 0

  // Today against the month it is part of. The one comparison the three
  // numbers support — and nought stays nought rather than becoming a full bar.
  const share =
    data && data.earned_month > 0 ? (data.earned_today / data.earned_month) * 100 : 0

  return (
    <Page>
      {/* The phone rather than the name: every courier's account has one and
          it is the thing they identify themselves by, where `full_name` is
          often the word `Kuryer` and reads as `Kuryer · Kuryer`. */}
      <Title over={`Kuryer · ${staff?.phone ?? ""}`}>Daromad</Title>

      <Refusal error={earnings.error || history.error} />
      {earnings.isLoading ? <Loading what="Daromad" /> : null}

      <div className="flex gap-1.5 rounded-slab bg-kuryer-quiet p-1">
        {WINDOWS.map((one) => (
          <button
            key={one.key}
            type="button"
            aria-pressed={window === one.key}
            onClick={() => setWindow(one.key)}
            className={cn(
              "h-control-sm min-w-0 flex-1 rounded-nub text-small font-semibold transition-colors",
              window === one.key
                ? "bg-kuryer-card text-kuryer-ink shadow-kuryer-card"
                : "text-kuryer-ink-soft",
            )}
          >
            {one.label}
          </button>
        ))}
      </div>

      <Glass className="p-5">
        <Cap>
          {WINDOWS.find((one) => one.key === window)?.head}
          {window === "today" ? ` · ${dayMonth(new Date())}` : ""}
        </Cap>
        <div className="mt-2">
          <p className="flex flex-wrap items-baseline gap-2">
            <span className="display text-kuryer-ink [overflow-wrap:anywhere]">
              {groups(sum)}
            </span>
            <span className="text-body font-semibold text-kuryer-ink-soft">so'm</span>
          </p>
        </div>
        <p className="mt-1 text-small tabular text-kuryer-ink-soft">
          {groups(count)} yetkazish
          {data ? ` · ${money(data.fee_per_delivery)} har biri` : ""}
        </p>

        {/* The one comparison the data supports, and it is labelled as what it
            is rather than drawn as a chart of a week nobody can compute. */}
        {data && data.earned_month > 0 ? (
          <div className="mt-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-micro text-kuryer-ink-soft">
                Bugun · shu oyning {percent(share)} qismi
              </span>
              <span className="text-micro font-semibold tabular text-kuryer-ink-soft">
                {groups(data.earned_today)} / {groups(data.earned_month)}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-kuryer-quiet">
              <div
                className="h-full rounded-full bg-kuryer-act"
                style={{ width: `${Math.min(100, Math.max(0, share))}%` }}
              />
            </div>
          </div>
        ) : null}
      </Glass>

      {data ? (
        <div className="flex gap-2.5">
          <Figure label="Bugun" value={groups(data.delivered_today)} />
          <Figure label="Shu oy" value={groups(data.delivered_month)} />
          <Figure
            label="Bo'lmagan"
            value={groups(data.failed_attempts)}
            tone={data.failed_attempts ? "halt" : "ink"}
          />
        </div>
      ) : null}

      {data?.cash_on_hand ? (
        <Tile>
          <Cap>Qo'ldagi naqd</Cap>
          <p className="mt-2 text-kuryer-title font-bold tabular text-kuryer-cash-ink [overflow-wrap:anywhere]">
            {money(data.cash_on_hand)}
          </p>
          <p className="mt-1 text-micro text-kuryer-ink-soft">
            Bu daromad emas — ombor kassasiga topshiriladi
          </p>
        </Tile>
      ) : null}

      {/* -------------------------------------------------------- the doors behind it */}
      <div className="overflow-hidden rounded-tile bg-kuryer-card shadow-kuryer-card">
        <p className="caption px-4 pb-2 pt-4 font-bold text-kuryer-ink-soft">
          Oxirgi yetkazishlar
        </p>
        {history.isLoading ? <Loading what="Tarix" /> : null}
        {!history.isLoading && !done.length ? (
          <div className="px-4 pb-4">
            <Nothing
              icon={ClipboardCheck}
              title="Hali yetkazilgan buyurtma yo'q"
              what="Yetkazganlaringiz shu yerda to'planib boradi."
            />
          </div>
        ) : null}
        {done.map((order) => (
          <div
            key={order.id}
            className="flex items-center gap-3 border-t-[0.5px] border-kuryer-hair p-3.5"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-slab bg-kuryer-done-soft text-kuryer-done-deep">
              <CheckCircle2 className="size-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-small font-semibold text-kuryer-ink [overflow-wrap:anywhere]">
                {order.address_line || order.code}
              </span>
              <span className="block text-micro tabular text-kuryer-ink-soft">
                {order.code} · {order.payment_method === "cash" ? "naqd" : "onlayn"}
              </span>
            </span>
            <span className="shrink-0 text-small font-semibold tabular text-kuryer-ink">
              {groups(order.total)}
            </span>
          </div>
        ))}
      </div>
    </Page>
  )
}

function Figure({
  label,
  value,
  tone = "ink",
}: {
  label: string
  value: string
  tone?: "ink" | "halt"
}) {
  return (
    <div className="min-w-0 flex-1 rounded-tile bg-kuryer-card p-3.5 shadow-kuryer-card">
      <Cap>{label}</Cap>
      <p
        className={cn(
          "figure mt-1 [overflow-wrap:anywhere]",
          tone === "halt" ? "text-kuryer-halt-ink" : "text-kuryer-ink",
        )}
      >
        {value}
      </p>
    </div>
  )
}
