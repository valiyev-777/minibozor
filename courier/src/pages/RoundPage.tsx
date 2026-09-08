import { Link } from "react-router-dom"
import { ChevronRight, Package, Undo2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Run, Stop } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * The work I took, in one list.
 *
 * Deliveries and collections together, because they are the same thing to the
 * person doing them: a place to go. Two lists would mean deciding which one to
 * look at first, and the answer is "whichever is nearer", which neither list
 * knows. So they are one column, deliveries first because there are more of
 * them, each row a full-width tap target.
 *
 * Nothing arrives here on its own any more. A stop is on this screen because
 * the courier took it off the board, which is why the empty state points at
 * the board rather than at an operator who has not got round to them.
 *
 * The cash due is the loudest thing on a row that has any, because it is the
 * one number the courier has to get exactly right at the door — the server
 * refuses a figure that does not match.
 */
export function RoundPage() {
  const stops = useQuery({
    queryKey: ["round"],
    queryFn: () => api<Stop[]>("/courier/orders"),
  })
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api<Run[]>("/courier/pickups"),
  })

  // Only the runs still to drive. A received one is the warehouse's row now.
  const open = (runs.data ?? []).filter(
    (run) => run.status === "open" || run.status === "collected",
  )
  const nothing = (stops.data ?? []).length === 0 && open.length === 0

  return (
    <div className="space-y-4 px-[var(--gap-page)] py-[var(--gap-page)]">
      <h1 className="text-xl font-semibold text-ink">{t.today}</h1>

      <Async query={stops} lines={3}>
        {(rows) =>
          nothing ? (
            <Empty
              title={t.nothingToday}
              hint={t.nothingTodayHint}
              className="rounded-[var(--radius-panel)] border border-line bg-surface"
            />
          ) : (
            <div className="space-y-3">
              {rows.map((stop) => (
                <Link
                  key={stop.id}
                  to={`/orders/${stop.id}`}
                  className="flex items-center gap-3 rounded-[var(--radius-panel)] border border-line
                             bg-surface px-4 py-4 outline-none transition-colors
                             active:bg-line-soft focus-visible:ring-2 focus-visible:ring-brand/40"
                >
                  <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-deep">
                    <Package className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="tabular font-semibold text-ink">
                        {stop.code}
                      </span>
                      {stop.cash_due > 0 ? (
                        <Badge tone="warn">
                          {t.cashDue}: {som(stop.cash_due)}
                        </Badge>
                      ) : (
                        <Badge tone="good">{t.paidAlready}</Badge>
                      )}
                      {stop.attempts > 0 ? (
                        <Badge tone="danger">
                          {num(stop.attempts)} {t.attempts}
                        </Badge>
                      ) : null}
                    </span>
                    <span className="line-clamp-2 block text-ink">{stop.address_line}</span>
                    <span className="block truncate text-[length:var(--text-small)] text-ink-soft">
                      {stop.recipient_name} · {num(stop.items_count)} {t.items}
                      {stop.delivery_window ? ` · ${stop.delivery_window}` : ""}
                    </span>
                  </span>
                  <ChevronRight className="size-5 shrink-0 text-ink-faint" />
                </Link>
              ))}

              {open.map((run) => (
                <Link
                  key={run.id}
                  to={`/pickups/${run.id}`}
                  className="flex items-center gap-3 rounded-[var(--radius-panel)] border border-line
                             bg-surface px-4 py-4 outline-none transition-colors
                             active:bg-line-soft focus-visible:ring-2 focus-visible:ring-brand/40"
                >
                  <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-warn-soft text-warn-ink">
                    <Undo2 className="size-5" />
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="tabular font-semibold text-ink">{run.code}</span>
                      <Badge tone="warn">{t.pickups}</Badge>
                    </span>
                    <span className="block truncate text-ink">
                      {num(run.lines.length)} manzil
                    </span>
                    <span className="block truncate text-[length:var(--text-small)] text-ink-soft">
                      {run.lines
                        .map((line) => line.customer_name)
                        .filter(Boolean)
                        .join(", ") || run.note}
                    </span>
                  </span>
                  <ChevronRight className="size-5 shrink-0 text-ink-faint" />
                </Link>
              ))}
            </div>
          )
        }
      </Async>
    </div>
  )
}
