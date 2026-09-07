import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Check, Circle } from "lucide-react"
import { api } from "@/api/client"
import type { OrderDetail, OrderPage, OrderStatus, StaffOrder } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Label, Select, Textarea } from "@/components/ui/field"
import { ORDER_ACTION, ORDER_STATUS, ORDER_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { day, money, when } from "@/lib/utils"

const KEY = ["staff", "orders"]
const PAGE_SIZE = 25
const FILTERS: { value: "" | OrderStatus; label: string }[] = [
  { value: "", label: "Hammasi" },
  { value: "placed", label: "Qabul qilindi" },
  { value: "packing", label: "Yig'ilmoqda" },
  { value: "shipped", label: "Yo'lda" },
  { value: "delivered", label: "Yetkazildi" },
  { value: "cancelled", label: "Bekor qilindi" },
  { value: "returned", label: "Qaytarildi" },
]

export function OrdersPage() {
  const [status, setStatus] = React.useState<"" | OrderStatus>("")
  const [page, setPage] = React.useState(1)
  // The clicked row, not its id: it already carries `next_statuses`, and
  // re-fetching the queue to recover them would be a second request for
  // something we are holding.
  const [open, setOpen] = React.useState<StaffOrder | null>(null)

  const query = useQuery({
    queryKey: [...KEY, status, page],
    queryFn: () =>
      api<OrderPage>("/staff/orders", {
        query: { status, page, page_size: PAGE_SIZE },
      }),
  })

  const columns: Column<StaffOrder>[] = [
    {
      key: "code",
      header: "Kod",
      sortValue: (row) => row.code,
      cell: (row) => <span className="tabular font-medium text-ink">{row.code}</span>,
    },
    {
      key: "customer",
      header: "Mijoz",
      sortValue: (row) => row.customer_name,
      cell: (row) => (
        <>
          <span className="block truncate text-ink">{row.customer_name || "—"}</span>
          <span className="tabular block text-[12px] text-ink-faint">{row.customer_phone}</span>
        </>
      ),
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => <Badge tone={ORDER_TONE[row.status]}>{ORDER_STATUS[row.status]}</Badge>,
    },
    {
      key: "delivery",
      header: "Yetkazish",
      cell: (row) => (
        <div className="max-w-64">
          <p className="truncate text-ink">{row.address_line || "—"}</p>
          <p className="tabular text-[12px] text-ink-faint">
            {[day(row.delivery_day), row.delivery_window].filter(Boolean).join(" · ")}
          </p>
        </div>
      ),
    },
    {
      key: "items",
      header: "Dona",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.items_count,
      cell: (row) => row.items_count,
    },
    {
      key: "total",
      header: "Summa",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.total,
      cell: (row) => (
        <>
          {money(row.total)}
          {row.paid ? null : (
            <span className="block text-[11px] font-medium text-warn">to'lanmagan</span>
          )}
        </>
      ),
    },
    {
      key: "created",
      header: "Berilgan",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
  ]

  return (
    <Page title="Buyurtmalar" hint="Navbat eng eskisidan boshlanadi.">
      <DataTable
        rows={query.data?.items}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={setOpen}
        emptyTitle="Buyurtma yo'q"
        server={{
          page,
          pageSize: PAGE_SIZE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
        }}
        toolbar={
          <>
            <Label htmlFor="order-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="order-status"
              className="w-44"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as "" | OrderStatus)
                setPage(1)
              }}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.total ?? 0} ta buyurtma</Hint>
          </>
        }
      />

      {open ? <OrderDetailDialog row={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

function OrderDetailDialog({ row, onClose }: { row: StaffOrder; onClose: () => void }) {
  const [target, setTarget] = React.useState<OrderStatus | null>(null)
  const [note, setNote] = React.useState("")

  // The detail response is the customer's own shape — the items and the
  // timeline they see — reused deliberately rather than rendered a second way.
  const query = useQuery({
    queryKey: [...KEY, "detail", row.id],
    queryFn: () => api<OrderDetail>(`/staff/orders/${row.id}`),
  })

  const move = useAction<OrderStatus, OrderDetail>({
    run: (status) =>
      api<OrderDetail>(`/staff/orders/${row.id}/status`, {
        method: "POST",
        json: { status, note },
      }),
    invalidate: [KEY],
    success: (order) => `${order.code} — ${ORDER_STATUS[order.status]}`,
    onDone: () => {
      setTarget(null)
      setNote("")
      onClose()
    },
  })

  const order = query.data
  // Straight from the API. Which moves are legal is decided in
  // `app/transitions.py` and nowhere else; an illegal one comes back 409 with
  // a sentence, and the toast shows it.
  const moves = row.next_statuses

  return (
    <>
      <Dialog open onOpenChange={(next) => !next && onClose()}>
        <DialogPanel
          className="w-[min(94vw,52rem)]"
          title={row.code}
          description={`${row.customer_name || "Mijoz"} · ${row.customer_phone}`}
          footer={
            moves.length ? (
              moves.map((status) => (
                <Button
                  key={status}
                  size="sm"
                  variant={status === "cancelled" ? "quiet" : "primary"}
                  onClick={() => setTarget(status)}
                >
                  {ORDER_ACTION[status]}
                </Button>
              ))
            ) : (
              <Hint>Bu buyurtma tugagan — siljitadigan holat qolmagan.</Hint>
            )
          }
        >
          {!order ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }, (_, i) => (
                <span key={i} className="block h-3 animate-pulse rounded bg-line" />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={ORDER_TONE[order.status]}>{ORDER_STATUS[order.status]}</Badge>
                <Hint>{order.payment_label}</Hint>
              </div>

              <dl className="grid grid-cols-[9rem_1fr] gap-y-1.5 text-[13px]">
                <dt className="text-ink-soft">Manzil</dt>
                <dd className="text-ink">
                  {order.address_line || "—"}
                  {order.address_meta ? (
                    <span className="block text-[12px] text-ink-faint">{order.address_meta}</span>
                  ) : null}
                </dd>
                <dt className="text-ink-soft">Oyna</dt>
                <dd className="tabular text-ink">
                  {[day(order.delivery_day), order.delivery_start && order.delivery_end
                    ? `${order.delivery_start}–${order.delivery_end}`
                    : null]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt className="text-ink-soft">Jami</dt>
                <dd className="tabular text-ink">
                  {money(order.total)} so'm
                  <span className="text-[12px] text-ink-faint">
                    {" "}
                    ({money(order.subtotal)} + {money(order.delivery_fee)} yetkazish
                    {order.discount ? ` − ${money(order.discount)} chegirma` : ""})
                  </span>
                </dd>
              </dl>

              <section>
                <h2 className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-soft">
                  Tovarlar
                </h2>
                <ul className="divide-y divide-line-soft rounded border border-line">
                  {order.items.map((item) => (
                    <li key={item.id} className="flex items-center gap-2.5 px-2.5 py-2">
                      {item.image_url ? (
                        <img
                          src={item.image_url}
                          alt=""
                          className="size-9 rounded border border-line object-cover"
                        />
                      ) : (
                        <span className="size-9 rounded bg-line-soft" />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-ink">{item.title}</p>
                        <p className="text-[12px] text-ink-faint">{item.variant_label || "—"}</p>
                      </div>
                      <p className="tabular shrink-0 text-right text-ink">
                        {item.quantity} × {money(item.unit_price)}
                        <span className="block text-[12px] text-ink-faint">
                          {money(item.line_total)}
                        </span>
                      </p>
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h2 className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-soft">
                  Timeline
                </h2>
                <ol className="space-y-1.5">
                  {order.events.map((event, index) => (
                    <li key={`${event.status}-${index}`} className="flex items-start gap-2">
                      {event.done ? (
                        <Check className="mt-0.5 size-3.5 shrink-0 text-good" />
                      ) : (
                        <Circle className="mt-0.5 size-3.5 shrink-0 text-ink-faint" />
                      )}
                      <div className="min-w-0">
                        <p className={event.done ? "text-ink" : "text-ink-faint"}>
                          {event.title}
                        </p>
                        {event.happened_at || event.note ? (
                          <p className="tabular text-[12px] text-ink-faint">
                            {[when(event.happened_at), event.note].filter(Boolean).join(" · ")}
                          </p>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ol>
              </section>
            </div>
          )}
        </DialogPanel>
      </Dialog>

      {target ? (
        <ConfirmDialog
          open
          onOpenChange={(next) => !next && setTarget(null)}
          title={ORDER_ACTION[target]}
          description={
            order ? `${order.code} · ${ORDER_STATUS[order.status]} → ${ORDER_STATUS[target]}` : ""
          }
          confirmLabel={ORDER_ACTION[target]}
          {...(target === "cancelled" ? { destructive: true } : {})}
          pending={move.isPending}
          onConfirm={() => move.mutate(target)}
        >
          <div className="space-y-1">
            <Label htmlFor="move-note">Izoh (ixtiyoriy)</Label>
            <Textarea
              id="move-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder={
                target === "cancelled" ? "Mijoz telefonda bekor qildi" : "3-qatordan yig'ildi"
              }
            />
            <Hint>
              Timeline'ga va audit jurnaliga tushadi.
              {target === "cancelled"
                ? " Bekor qilinganda tovar javonga qaytadi va oyna bo'shaydi."
                : ""}
            </Hint>
          </div>
        </ConfirmDialog>
      ) : null}
    </>
  )
}
