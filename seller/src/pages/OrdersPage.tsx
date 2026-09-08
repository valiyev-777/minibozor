import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { OrderPage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { moment, num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * What has sold, and nothing to press.
 *
 * The queue is the warehouse's to pick and the operator's to run; a seller
 * reads it to know their goods went out. The list is already narrowed to their
 * own orders by the server — that is not a filter offered here, it is the only
 * set of orders that exists for them — so there is nothing to choose on this
 * screen and no buttons on a row.
 *
 * The customer's name and telephone are on the row because a seller ringing
 * the operator about a delivery is asked "which order", and the code alone is
 * not how anybody remembers it.
 */
const TONE = {
  placed: "warn",
  packing: "brand",
  shipped: "brand",
  delivered: "good",
  cancelled: "neutral",
  returned: "danger",
} as const

export function OrdersPage() {
  const orders = useQuery({
    queryKey: ["orders"],
    queryFn: () => api<OrderPage>("/staff/orders", { query: { page_size: 50 } }),
  })

  return (
    <>
      <PageTitle>{t.orders}</PageTitle>

      <Panel>
        <p className="px-5 pb-2 text-[length:var(--text-small)] text-ink-soft">
          {t.ordersReadOnly}
        </p>
        <Async query={orders} lines={4}>
          {(page) =>
            page.items.length === 0 ? (
              <Empty title={t.ordersEmpty} hint={t.ordersEmptyHint} />
            ) : (
              <>
                {page.items.map((order) => (
                  <Row key={order.id} className="sm:flex-nowrap">
                    <div className="min-w-0 flex-1">
                      <p className="tabular text-[length:var(--text-body)] font-medium text-ink">
                        {order.code}
                      </p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {moment(order.created_at)}
                      </p>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[length:var(--text-small)] text-ink">
                        {order.customer_name || "—"}
                      </p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {order.customer_phone}
                      </p>
                    </div>
                    <span className="tabular w-16 text-right text-[length:var(--text-small)] text-ink-soft">
                      {num(order.items_count)} {t.items}
                    </span>
                    <span className="tabular w-32 text-right text-[length:var(--text-body)] text-ink">
                      {som(order.total)}
                    </span>
                    <Badge tone={TONE[order.status]}>{order.status_label}</Badge>
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
