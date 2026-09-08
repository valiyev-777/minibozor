import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Supply } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { moment, num } from "@/lib/format"
import { supplyStatus, t } from "@/lib/labels"

/**
 * Every batch this seller declared, and what the warehouse found in it.
 *
 * Declared and received side by side, per line, because the gap between them
 * is the only thing either party will want to talk about afterwards — and a
 * refusal shows the sentence the warehouse wrote, which is the same field the
 * product screen reads.
 *
 * Read-only. Declaring is done from a product (the quantity boxes there) and
 * receiving is the warehouse's; this screen answers "has my box been counted
 * yet" and nothing else.
 */
const TONE = {
  declared: "warn",
  received: "good",
  cancelled: "danger",
} as const

export function SuppliesPage() {
  const supplies = useQuery({
    queryKey: ["supplies"],
    queryFn: () => api<Supply[]>("/staff/supplies"),
  })

  return (
    <>
      <PageTitle>{t.supplies}</PageTitle>

      <Async
        query={supplies}
        lines={4}
        empty={
          <Panel>
            <Empty title={t.suppliesEmpty} hint={t.suppliesEmptyHint} />
          </Panel>
        }
      >
        {(rows) => (
          <div className="space-y-[var(--gap-page)]">
            {rows.map((batch) => (
              <Panel
                key={batch.id}
                title={
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="tabular">{batch.code}</span>
                    <Badge tone={TONE[batch.status]}>
                      {supplyStatus[batch.status] ?? batch.status}
                    </Badge>
                  </span>
                }
                action={
                  <span className="text-[length:var(--text-small)] text-ink-soft">
                    {batch.status === "received"
                      ? `${t.receivedAt}: ${moment(batch.received_at)}`
                      : `${t.declaredAt}: ${moment(batch.declared_at)}`}
                  </span>
                }
              >
                {batch.note ? (
                  <p className="border-t border-line-soft px-5 py-2 text-[length:var(--text-small)] text-ink-soft">
                    {batch.note}
                  </p>
                ) : null}

                <div className="hidden border-t border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
                  <span className="flex-1">{t.title}</span>
                  <span className="w-20 text-right">{t.declared}</span>
                  <span className="w-20 text-right">{t.received}</span>
                  <span className="w-20 text-right">{t.difference}</span>
                </div>

                {batch.lines.map((line) => (
                  <Row key={line.id} className="sm:flex-nowrap">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[length:var(--text-body)] text-ink">
                        {line.product_title}
                      </p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {line.variant_label || line.sku}
                      </p>
                    </div>
                    <span className="tabular w-20 text-right text-[length:var(--text-body)] text-ink-soft">
                      {num(line.declared_quantity)}
                    </span>
                    <span className="tabular w-20 text-right text-[length:var(--text-body)] text-ink">
                      {line.received_quantity === null ? "—" : num(line.received_quantity)}
                    </span>
                    {/* Nought is not "no difference" until somebody has
                        counted: an uncounted line has no difference to show,
                        and a dash says that where a nought would lie. */}
                    <span
                      className={
                        "tabular w-20 text-right text-[length:var(--text-body)] " +
                        (line.difference && line.difference < 0
                          ? "text-danger"
                          : "text-ink-soft")
                      }
                    >
                      {line.difference === null
                        ? "—"
                        : line.difference > 0
                          ? `+${num(line.difference)}`
                          : num(line.difference)}
                    </span>
                  </Row>
                ))}
              </Panel>
            ))}
          </div>
        )}
      </Async>
    </>
  )
}
