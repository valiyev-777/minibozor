import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Ban, Truck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Courier, DeliveryAttempt, Order, OrderDetail } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Input, Label, Select, Textarea } from "@/ui/field"
import { Async } from "@/ui/states"
import { Detail, Panel, Row } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { useRole } from "@/auth/session"
import { useAction } from "@/lib/mutate"
import { date, moment, num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * One order in full, and the two decisions that are the operator's.
 *
 * The body is deliberately the *customer's* own shape — `GET
 * /staff/orders/{id}` answers with `OrderOut`, the same rendering the app
 * shows. An operator on the telephone is being asked about what the customer
 * is looking at, and a second rendering of the same order is a second thing to
 * keep in step.
 *
 * Assigning a courier and calling the order off are both here rather than on
 * the queue, because both need something typed: a courier and a position in
 * their round, or a reason the customer will be told. A one-click cancel on a
 * list row is a cancel somebody makes by accident.
 *
 * The warehouse reads this screen and gets neither action: picking is theirs,
 * routing and refusing are not.
 */
export function OrderPage() {
  const { id } = useParams()
  const role = useRole()
  const order = useQuery({
    queryKey: ["order", id],
    queryFn: () => api<OrderDetail>(`/staff/orders/${id}`),
    enabled: Boolean(id),
  })
  // The queue row carries what the customer's own shape does not: which
  // courier is on it, and what the order may become next.
  const row = useQuery({
    queryKey: ["order-row", id],
    queryFn: async () => {
      const page = await api<{ items: Order[] }>("/staff/orders", {
        query: { page_size: 100 },
      })
      return page.items.find((item) => String(item.id) === id) ?? null
    },
    enabled: Boolean(id),
  })

  return (
    <>
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/orders">
            <ArrowLeft />
            {t.orders}
          </Link>
        </Button>
      </div>

      <Async query={order} lines={6}>
        {(full) => (
          <div className="space-y-[var(--gap-page)]">
            <Panel
              title={
                <span className="flex flex-wrap items-center gap-2">
                  <span className="tabular">{full.code}</span>
                  <Badge tone={full.paid ? "good" : "warn"}>
                    {full.paid ? t.paid : t.unpaid}
                  </Badge>
                  <Badge tone="brand">{full.status_label}</Badge>
                </span>
              }
              action={
                <span className="text-[length:var(--text-small)] text-ink-soft">
                  {moment(full.created_at)}
                </span>
              }
            >
              <div className="grid gap-4 border-t border-line-soft px-5 py-4 sm:grid-cols-3">
                <Detail label={t.customer}>
                  {full.recipient_name}
                  <a
                    href={`tel:${full.recipient_phone}`}
                    className="block text-brand-deep underline"
                  >
                    {full.recipient_phone}
                  </a>
                </Detail>
                <Detail label={t.address} className="sm:col-span-2">
                  {full.address_line}
                  {full.address_meta ? (
                    <span className="text-ink-soft"> · {full.address_meta}</span>
                  ) : null}
                </Detail>
                <Detail label={t.window}>
                  {full.delivery_day ? date(full.delivery_day) : "—"}
                  {full.delivery_start && full.delivery_end
                    ? ` · ${full.delivery_start}–${full.delivery_end}`
                    : ""}
                </Detail>
                <Detail label={t.total}>
                  <span className="tabular">{som(full.total)}</span>
                  <span className="text-ink-soft">
                    {" "}
                    ({som(full.subtotal)} + {som(full.delivery_fee)})
                  </span>
                </Detail>
                <Detail label={t.courier}>{row.data?.courier_name || "—"}</Detail>
              </div>
            </Panel>

            <Panel title={`${t.items} · ${num(full.items_count)}`}>
              {full.items.map((item) => (
                <Row key={item.id} className="sm:flex-nowrap">
                  <Thumb src={item.image_url} className="size-9" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{item.title}</p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {item.variant_label}
                    </p>
                  </div>
                  <span className="tabular w-14 text-right text-ink-soft">
                    ×{num(item.quantity)}
                  </span>
                  <span className="tabular w-28 text-right text-ink">
                    {som(item.line_total)}
                  </span>
                </Row>
              ))}
            </Panel>

            {/* Every knock, when there has been one. Absent rather than an
                empty box on the ordinary order that arrived first time: a
                heading with nothing under it reads as a thing gone missing.

                It sits above the operator's controls on purpose — deciding
                to give up is made from this list, and a decision should be
                below what it is made from. */}
            {full.attempts.length ? <Attempts rows={full.attempts} /> : null}

            {role === "warehouse" ? null : (
              <Operator orderId={full.id} canCancel={Boolean(row.data?.next_statuses.includes("cancelled"))} />
            )}
          </div>
        )}
      </Async>
    </>
  )
}

/**
 * The doors that were knocked on, oldest first.
 *
 * A count would not do. Three attempts at one wrong buzzer and three on three
 * different days are the same number and different decisions, so each row
 * carries who went, when, and the sentence they wrote — which is the whole
 * reason `POST /courier/orders/{id}/failed` makes a reason mandatory.
 */
function Attempts({ rows }: { rows: DeliveryAttempt[] }) {
  return (
    <Panel title={`${t.attempts} · ${num(rows.length)}`}>
      {rows.map((row) => (
        <Row key={row.id} className="sm:flex-nowrap">
          <Badge tone={row.result === "delivered" ? "good" : "danger"}>
            {row.result === "delivered" ? t.attemptDelivered : t.attemptFailed}
          </Badge>
          <div className="min-w-0 flex-1">
            <p className="text-ink">{row.reason || row.recipient_name || "—"}</p>
            <p className="text-[length:var(--text-micro)] text-ink-faint">
              {row.courier_name}
              {row.result === "delivered" && row.recipient_name
                ? ` · ${t.handedTo}: ${row.recipient_name}`
                : ""}
            </p>
          </div>
          <span className="w-40 text-right text-[length:var(--text-small)] text-ink-soft">
            {moment(row.happened_at)}
          </span>
        </Row>
      ))}
    </Panel>
  )
}

function Operator({
  orderId,
  canCancel,
}: {
  orderId: number
  canCancel: boolean
}) {
  const couriers = useQuery({
    queryKey: ["couriers"],
    queryFn: () => api<Courier[]>("/staff/couriers"),
    staleTime: 5 * 60_000,
  })
  const [courierId, setCourierId] = React.useState("")
  const [sequence, setSequence] = React.useState("")
  const [reason, setReason] = React.useState("")

  const assign = useAction<void, unknown>({
    run: () =>
      api(`/staff/orders/${orderId}/courier`, {
        method: "POST",
        json: {
          courier_id: Number(courierId),
          ...(sequence ? { sequence: Number(sequence) } : {}),
        },
      }),
    invalidate: [["order-row", String(orderId)], ["orders"]],
    success: t.courierAssigned,
  })

  const cancel = useAction<void, unknown>({
    run: () =>
      api(`/staff/orders/${orderId}/status`, {
        method: "POST",
        json: { status: "cancelled", note: reason.trim() },
      }),
    invalidate: [["order", String(orderId)], ["order-row", String(orderId)], ["orders"], ["summary"]],
    success: t.statusMoved,
  })

  return (
    <div className="grid gap-[var(--gap-page)] lg:grid-cols-2">
      <Panel title={t.assignCourier}>
        <form
          className="flex flex-wrap items-end gap-3 border-t border-line-soft px-5 py-4"
          onSubmit={(event) => {
            event.preventDefault()
            assign.mutate()
          }}
        >
          <div className="min-w-40 flex-1 space-y-1.5">
            <Label htmlFor="courier">{t.courier}</Label>
            <Select
              id="courier"
              required
              value={courierId}
              onChange={(event) => setCourierId(event.target.value)}
            >
              <option value="">—</option>
              {(couriers.data ?? []).map((courier) => (
                <option key={courier.id} value={courier.id}>
                  {courier.full_name || courier.phone}
                </option>
              ))}
            </Select>
          </div>
          <div className="w-24 space-y-1.5">
            <Label htmlFor="sequence">{t.sequence}</Label>
            <Input
              id="sequence"
              inputMode="numeric"
              value={sequence}
              onChange={(event) => setSequence(event.target.value.replace(/\D/g, ""))}
              placeholder="1"
            />
          </div>
          <Button type="submit" variant="primary" disabled={!courierId || assign.isPending}>
            <Truck />
            {t.assignCourier}
          </Button>
        </form>
      </Panel>

      {canCancel ? (
        <Panel title={t.cancelOrder}>
          <form
            className="space-y-3 border-t border-line-soft px-5 py-4"
            onSubmit={(event) => {
              event.preventDefault()
              cancel.mutate()
            }}
          >
            <div className="space-y-1.5">
              <Label htmlFor="cancel-reason">{t.cancelReason}</Label>
              <Textarea
                id="cancel-reason"
                rows={2}
                required
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Uch urinish — mijoz javob bermadi"
              />
            </div>
            {/* Cancelling puts the counts back — the goods were never sold —
                so it is a real decision and not a tidy-up. The reason is
                required because the customer is told it. */}
            <Button
              type="submit"
              variant="danger"
              disabled={!reason.trim() || cancel.isPending}
            >
              <Ban />
              {t.cancelOrder}
            </Button>
          </form>
        </Panel>
      ) : null}
    </div>
  )
}
