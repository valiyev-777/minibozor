import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { OrderPage as Page, OrderStatus } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useRole } from "@/auth/session"
import { useAction } from "@/lib/mutate"
import { useFilter } from "@/lib/useFilter"
import { moment, num, som } from "@/lib/format"
import { orderWord, t } from "@/lib/labels"

/**
 * One queue, two jobs, and the difference is the default filter.
 *
 * The warehouse works the front of it: `placed` and `packing` are the orders
 * with something to do at a bench, so that is where a picker lands. The
 * operator runs the whole thing and lands on everything, because their job is
 * the exceptions — the one that has been `shipped` for three days, the one a
 * customer is on the telephone about.
 *
 * **The buttons come from `next_statuses`.** That is `app.transitions`
 * answering, so a delivered order does not offer "yig'ildi" and this client
 * holds no copy of the rules. A cancel is not offered here at all: it needs a
 * reason and a decision, which is the order's own screen.
 */
const TONE: Record<OrderStatus, "warn" | "brand" | "good" | "neutral" | "danger"> = {
  placed: "warn",
  packing: "brand",
  shipped: "brand",
  delivered: "good",
  cancelled: "neutral",
  returned: "danger",
}

/** The words for the two moves a picker makes, in their own language. */
const MOVE: Partial<Record<OrderStatus, string>> = {
  packing: "Yig'ildi",
  shipped: "Kuryerga berildi",
  delivered: "Yetkazildi",
}

const FILTERS: { key: OrderStatus | ""; label: string }[] = [
  { key: "placed", label: "Yangi" },
  { key: "packing", label: "Yig'ilmoqda" },
  { key: "shipped", label: "Yo'lda" },
  { key: "delivered", label: "Yetkazilgan" },
  { key: "", label: t.all },
]

export function OrdersPage() {
  const role = useRole()
  const [status, setStatus] = useFilter<OrderStatus>(
    "status",
    role === "warehouse" ? "placed" : "",
  )
  // Whether anybody could be carrying these yet. `placed` and `packing` are
  // both still on a shelf, so the courier column would be dashes.
  const onTheRoad = status !== "placed" && status !== "packing"

  const orders = useQuery({
    queryKey: ["orders", status],
    queryFn: () =>
      api<Page>("/staff/orders", {
        query: { page_size: 50, ...(status ? { status } : {}) },
      }),
  })

  const move = useAction<{ id: number; status: OrderStatus }, unknown>({
    run: ({ id, status: next }) =>
      api(`/staff/orders/${id}/status`, { method: "POST", json: { status: next } }),
    invalidate: [["orders"], ["summary"]],
    success: t.statusMoved,
  })

  return (
    <>
      <PageTitle
        action={
          <div className="flex flex-wrap gap-1">
            {FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                onClick={() => setStatus(filter.key)}
                className={
                  "rounded-[var(--radius-control)] px-2.5 py-1 text-[length:var(--text-small)] " +
                  (status === filter.key
                    ? "bg-brand text-brand-ink"
                    : "text-ink-soft hover:bg-line-soft")
                }
              >
                {filter.label}
              </button>
            ))}
          </div>
        }
      >
        {t.orders}
      </PageTitle>

      <Panel>
        {/* Column headings, and every row below reserves the same widths —
            including the action column, which is empty on a delivered order.
            Without that reservation the columns jitter from row to row as the
            buttons come and go, and a screen read by scanning a column is a
            screen where that costs real time. */}
        <div className="hidden border-b border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint lg:flex lg:gap-4">
          <span className="w-28">{t.order}</span>
          <span className="flex-1">{t.whatToPick}</span>
          <span className="w-14 text-right">{t.items}</span>
          <span className="w-28 text-right">{t.total}</span>
          <span className="w-20">{t.paid}</span>
          {onTheRoad ? <span className="w-32">{t.courier}</span> : null}
          <span className="w-28 text-right">{t.when}</span>
          <span className="w-24">{t.status}</span>
          <span className="w-40" />
        </div>
        <Async query={orders} lines={6}>
          {(page) =>
            page.items.length === 0 ? (
              <Empty title={t.ordersEmpty} hint={t.ordersEmptyHint} />
            ) : (
              <>
                {page.items.map((order) => (
                  <Row key={order.id} className="hover:bg-line-soft/60 sm:flex-nowrap">
                    <Link
                      to={`/orders/${order.id}`}
                      className="tabular w-28 shrink-0 font-medium text-ink outline-none focus-visible:underline"
                    >
                      {order.code}
                    </Link>
                    {/* What to fetch, then who for. The row used to lead with
                        the customer's name and their address, which is an
                        operator's business on the telephone and no use at all
                        to somebody at a bench holding an empty box — they had
                        to open every order to find out what was in it. */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-ink">{order.items_summary || "—"}</p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {order.customer_name || "—"}
                        {order.address_line ? ` · ${order.address_line}` : ""}
                      </p>
                    </div>
                    <span className="tabular w-14 text-right text-ink-soft">
                      {num(order.items_count)}
                    </span>
                    <span className="tabular w-28 text-right text-ink">
                      {som(order.total)}
                    </span>
                    <span className="w-20">
                      <Badge tone={order.paid ? "good" : "warn"}>
                        {order.paid ? t.paid : t.unpaid}
                      </Badge>
                    </span>
                    {onTheRoad ? (
                      <span className="w-32 truncate text-[length:var(--text-small)] text-ink-soft">
                        {order.courier_name || "—"}
                      </span>
                    ) : null}
                    <span className="w-28 text-right text-[length:var(--text-small)] text-ink-faint">
                      {moment(order.created_at)}
                    </span>
                    <span className="w-24">
                      <Badge tone={TONE[order.status]}>
                        {orderWord[order.status] ?? order.status_label}
                      </Badge>
                    </span>

                    <div className="flex w-40 justify-end gap-1">
                      {order.next_statuses
                        .filter((next) => MOVE[next])
                        .map((next) => (
                          <Button
                            key={next}
                            size="sm"
                            variant={next === "packing" ? "primary" : "outline"}
                            disabled={move.isPending}
                            onClick={() => move.mutate({ id: order.id, status: next })}
                          >
                            {MOVE[next]}
                          </Button>
                        ))}
                    </div>
                  </Row>
                ))}
              </>
            )
          }
        </Async>
      </Panel>
    </>
  )
}
