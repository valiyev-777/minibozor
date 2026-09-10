/**
 * Buyurtmalar — one queue, read by the office and worked from the front.
 *
 * **A queue is worked from the front; a history is read from the top.** Asking
 * for `placed` is a bench queue and comes back oldest first — serving the
 * newest order first is how the first one waits all day. Asking for everything
 * is reading, and comes back newest first.
 *
 * **The buttons come from `next_statuses`.** The server says which moves are
 * open from where the order actually is, so a client cannot offer one it will
 * then be refused for. The one move that is not here is `shipped`: the
 * handover is a courier picking the parcel up, at their own door.
 */

import { PackageCheck } from "lucide-react"
import { useState } from "react"

import { Empty, PageHeader, Pill, Problem, Waiting } from "@/components/page"
import type { Tone } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { age, dateTime, minutesSince, money } from "@/lib/format"
import { useBuildPickTask, useMoveOrder, useOrders } from "@/lib/queries"
import { useSession } from "@/lib/session"
import type { OrderStatus, StaffOrder } from "@/lib/types"

const TABS: { key: string; label: string }[] = [
  { key: "placed", label: "Yangi" },
  { key: "packing", label: "Yig'ilmoqda" },
  { key: "shipped", label: "Yo'lda" },
  { key: "delivered", label: "Yetkazilgan" },
  { key: "", label: "Hammasi" },
]

const WORD: Record<OrderStatus, string> = {
  placed: "Yangi",
  packing: "Yig'ilmoqda",
  shipped: "Yo'lda",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilindi",
  returned: "Qaytarildi",
}

/** A button says what it *does*; the chip beside it says where the order is.
 *
 * They used to share a word — a filter tab reading "Yig'ilmoqda" beside a
 * button reading "Yig'ilmoqda" — and one of them changes the order while the
 * other changes the list. */
/** Where the order is, as a colour: amber not yet, blue on its way, green
 *  arrived, grey over. The same three meanings as everywhere else. */
const TONE: Record<OrderStatus, Tone> = {
  placed: "warn",
  packing: "brand",
  shipped: "brand",
  delivered: "good",
  cancelled: "neutral",
  returned: "neutral",
}

const MOVE: Record<OrderStatus, string> = {
  placed: "Yangi qilish",
  packing: "Yig'ishga o'tkazish",
  shipped: "Kuryerga berish",
  delivered: "Yetkazildi deb belgilash",
  cancelled: "Bekor qilish",
  returned: "Qaytarildi deb belgilash",
}

export function OrdersPage() {
  const [status, setStatus] = useState("placed")
  const orders = useOrders(status)

  return (
    <div className="space-y-4">
      <PageHeader title="Buyurtmalar" subtitle="Navbat oldindan ishlanadi" />

      {/* One segmented control, not five outlined boxes with one of them
          tinted. Five bordered rectangles in a row read as five things to
          decide; a segment reads as one thing with a position. */}
      <div
        role="tablist"
        aria-label="Holat"
        className="inline-flex flex-wrap gap-0.5 rounded-control border border-line bg-line-soft p-0.5">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={tab.key === status}
            onClick={() => setStatus(tab.key)}
            className={cn(
              "h-control-sm rounded-[calc(var(--radius-control)-2px)] px-3 text-small transition-colors",
              tab.key === status
                ? "bg-surface font-medium text-ink shadow-panel"
                : "text-ink-soft hover:text-ink",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Problem error={orders.error} />
      {orders.isLoading ? <Waiting what="Buyurtmalar" /> : null}
      {orders.data?.items.length === 0 ? <Empty what="Bu yerda hech narsa yo'q." /> : null}

      <ul className="space-y-2">
        {(orders.data?.items ?? []).map((order) => (
          <li key={order.id}>
            <Row order={order} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function Row({ order }: { order: StaffOrder }) {
  const { staff } = useSession()
  const move = useMoveOrder(order.id)
  const build = useBuildPickTask()

  // Putting an order on the pick board is the bench's own act, behind the
  // warehouse's door. The assistant on the telephone reads this queue and
  // moves an order along; they do not decide what a picker walks to next.
  const benched = staff?.role === "admin" || staff?.role === "warehouse"

  return (
    <div className="rounded-panel border border-line bg-surface p-3 shadow-panel transition-colors hover:border-brand/40">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-body font-semibold tabular">{order.code}</span>
            <Pill tone={TONE[order.status]}>{WORD[order.status]}</Pill>
            {!order.paid ? <Pill>naqd</Pill> : null}
          </div>
          {/* What to fetch, in one line: a picker recognises an order by the
              thing in it. */}
          <div className="truncate text-small">{order.items_summary}</div>
          <div className="text-micro text-ink-faint">
            {order.customer_name || order.customer_phone} · {order.address_line}
          </div>
          <div className="text-micro text-ink-faint">
            {dateTime(order.created_at)}
            {order.courier_name ? ` · ${order.courier_name}` : ""}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <div className="tabular text-body font-semibold">{money(order.total)}</div>
          <div className="text-micro text-ink-faint">{order.items_count} dona</div>
        </div>
      </div>

      <Problem error={move.error || build.error} />

      <div className="mt-3 flex flex-wrap gap-2">
        {order.status === "placed" && benched ? (
          <Button variant="secondary" disabled={build.isPending} onClick={() => build.mutate(order.id)}
          >
            <PackageCheck />
            Terishga qo'yish
          </Button>
        ) : null}

        {order.next_statuses
          // The handover is the courier's own act, at a door. An office button
          // that marked a parcel shipped would be the office claiming somebody
          // else picked it up.
          .filter((next) => next !== "shipped")
          .map((next) => (
            <Button key={next} variant={next ==="cancelled" ?"ghost" :"primary"} className={cn(next ==="cancelled" &&"text-danger hover:text-danger")} disabled={move.isPending} onClick={() => {
                if (next === "cancelled") {
                  const note = window.prompt("Nega bekor qilinyapti?")
                  if (!note) return
                  move.mutate({ status: next, note })
                } else {
                  move.mutate({ status: next })
                }
              }}
            >
              {MOVE[next]}
            </Button>
          ))}

        {order.status === "placed" ? (
          <span className="self-center text-micro text-ink-faint">
            {age(minutesSince(order.created_at))} kutmoqda
          </span>
        ) : null}
      </div>
    </div>
  )
}

