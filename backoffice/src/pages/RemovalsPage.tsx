import * as React from "react"
import { PackageOpen, Truck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Removal } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label } from "@/ui/field"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { moment, num } from "@/lib/format"
import { removalStatus, t } from "@/lib/labels"

/**
 * Goods leaving, back to the seller who asked for them.
 *
 * Two steps and they are two different facts. **Preparing** picks the goods
 * and sets them aside, which takes them off the sellable count immediately —
 * a shirt in a box by the door is a shirt nobody can buy, and leaving it on
 * the shelf until collection would sell it twice. **Collecting** is the seller
 * actually taking it away.
 *
 * The prepared figure is typed per line rather than assumed, for the same
 * reason a receipt is: what was asked for and what was found are two numbers,
 * and a picker who cannot find all six should be able to say five.
 */
export function RemovalsPage() {
  const removals = useQuery({
    queryKey: ["removals"],
    queryFn: () => api<Removal[]>("/staff/removals"),
  })

  return (
    <>
      <PageTitle>{t.removals}</PageTitle>

      <Async
        query={removals}
        lines={4}
        empty={
          <Panel>
            <Empty title={t.removalsEmpty} hint={t.removalsEmptyHint} />
          </Panel>
        }
      >
        {(rows) => (
          <div className="space-y-[var(--gap-page)]">
            {rows.map((order) => (
              <RemovalCard key={order.id} order={order} />
            ))}
          </div>
        )}
      </Async>
    </>
  )
}

function RemovalCard({ order }: { order: Removal }) {
  const [prepared, setPrepared] = React.useState<Record<number, string>>({})

  const prepare = useAction<void, Removal>({
    run: () =>
      api<Removal>(`/staff/removals/${order.id}/prepare`, {
        method: "POST",
        json: {
          lines: order.lines.map((line) => ({
            line_id: line.id,
            prepared_quantity:
              prepared[line.id] === undefined
                ? line.quantity
                : Number(prepared[line.id]) || 0,
          })),
        },
      }),
    invalidate: [["removals"], ["stock"]],
    success: t.prepared,
  })

  const collect = useAction<void, Removal>({
    run: () =>
      api<Removal>(`/staff/removals/${order.id}/collect`, { method: "POST" }),
    invalidate: [["removals"], ["stock"]],
    success: t.handedOver,
  })

  const requested = order.status === "requested"
  const ready = order.status === "ready"

  return (
    <Panel
      title={
        <span className="flex flex-wrap items-center gap-2">
          <span className="tabular">{order.code}</span>
          <Badge
            tone={
              order.status === "collected"
                ? "good"
                : order.status === "cancelled"
                  ? "neutral"
                  : "warn"
            }
          >
            {removalStatus[order.status] ?? order.status}
          </Badge>
          <span className="text-[length:var(--text-small)] font-normal text-ink-soft">
            {order.seller.name}
          </span>
        </span>
      }
      action={
        <span className="text-[length:var(--text-small)] text-ink-faint">
          {moment(order.collected_at ?? order.ready_at ?? order.requested_at)}
        </span>
      }
    >
      {order.note ? (
        <p className="border-t border-line-soft px-5 py-2 text-[length:var(--text-small)] text-ink-soft">
          {order.note}
        </p>
      ) : null}

      <div className="hidden border-t border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
        <span className="flex-1">{t.product}</span>
        <span className="w-24 text-right">{t.quantity}</span>
        <span className="w-28 text-right">{t.prepare}</span>
      </div>

      {order.lines.map((line) => (
        <Row key={line.id} className="sm:flex-nowrap">
          <div className="min-w-0 flex-1">
            <p className="truncate text-ink">{line.product_title}</p>
            <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
              {line.variant_label} · {line.sku}
            </p>
          </div>
          <span className="tabular w-24 text-right text-ink-soft">
            {num(line.quantity)}
          </span>
          <div className="w-28 text-right">
            {requested ? (
              <>
                <Label htmlFor={`prep-${line.id}`} className="sr-only">
                  {line.variant_label} {t.prepare}
                </Label>
                <Input
                  id={`prep-${line.id}`}
                  inputMode="numeric"
                  className="tabular w-24 text-right"
                  placeholder={String(line.quantity)}
                  value={prepared[line.id] ?? ""}
                  onChange={(event) =>
                    setPrepared({
                      ...prepared,
                      [line.id]: event.target.value.replace(/\D/g, ""),
                    })
                  }
                />
              </>
            ) : (
              <span className="tabular text-ink">
                {line.prepared_quantity === null ? "—" : num(line.prepared_quantity)}
              </span>
            )}
          </div>
        </Row>
      ))}

      {requested || ready ? (
        <div className="space-y-2 border-t border-line px-5 py-4">
          {requested ? (
            <>
              <Hint>
                Yig'ib qo'yilgan tovar shu zahoti sotuvdan chiqadi — eshik yonidagi
                qutida turgan ko'ylakni hech kim sotib olmaydi.
              </Hint>
              <Button
                variant="primary"
                disabled={prepare.isPending}
                onClick={() => prepare.mutate()}
              >
                <PackageOpen />
                {t.prepare}
              </Button>
            </>
          ) : (
            <Button
              variant="primary"
              disabled={collect.isPending}
              onClick={() => collect.mutate()}
            >
              <Truck />
              {t.collect}
            </Button>
          )}
        </div>
      ) : null}
    </Panel>
  )
}
