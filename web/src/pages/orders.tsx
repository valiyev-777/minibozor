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

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { age, dateTime, money } from "@/lib/format"
import { useBuildPickTask, useMoveOrder, useOrders } from "@/lib/queries"
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

      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setStatus(tab.key)}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              tab.key === status && "border-brand bg-brand-soft text-brand-deep",
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
  const move = useMoveOrder(order.id)
  const build = useBuildPickTask()

  return (
    <div className="rounded-panel border bg-surface p-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-body font-semibold tabular">{order.code}</span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-micro",
                order.status === "placed" && "bg-warn-soft text-warn-ink",
                order.status === "packing" && "bg-brand-soft text-brand-deep",
                order.status === "shipped" && "bg-brand-soft text-brand-deep",
                order.status === "delivered" && "bg-good-soft text-good",
                (order.status === "cancelled" || order.status === "returned") &&
                  "bg-line-soft text-ink-soft",
              )}
            >
              {WORD[order.status]}
            </span>
            {!order.paid ? (
              <span className="rounded-full bg-line-soft px-2 py-0.5 text-micro text-ink-soft">
                naqd
              </span>
            ) : null}
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
        {order.status === "placed" ? (
          <Button
            variant="secondary"
            className="h-control gap-2"
            disabled={build.isPending}
            onClick={() => build.mutate(order.id)}
          >
            <PackageCheck className="size-4" />
            Terishga qo'yish
          </Button>
        ) : null}

        {order.next_statuses
          // The handover is the courier's own act, at a door. An office button
          // that marked a parcel shipped would be the office claiming somebody
          // else picked it up.
          .filter((next) => next !== "shipped")
          .map((next) => (
            <Button
              key={next}
              variant={next === "cancelled" ? "ghost" : "secondary"}
              className={cn("h-control", next === "cancelled" && "text-danger")}
              disabled={move.isPending}
              onClick={() => {
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

function minutesSince(when: string): number {
  const then = new Date(when.endsWith("Z") || when.includes("+") ? when : `${when}Z`)
  return Math.max(0, Math.round((Date.now() - then.getTime()) / 60_000))
}
