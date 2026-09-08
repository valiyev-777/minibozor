import { Link } from "react-router-dom"
import { useFilter } from "@/lib/useFilter"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Supply, SupplyStatus } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { moment, num } from "@/lib/format"
import { supplyStatus, t } from "@/lib/labels"

/**
 * The batches waiting to be counted, oldest first.
 *
 * This is the warehouse's first screen of the day, so the default is
 * `status=declared`: everything that has been promised and not yet arrived.
 * The received and refused ones are a click away rather than mixed in, because
 * a list that already holds the answer is a list somebody has to filter with
 * their eyes before they can work it.
 *
 * A row goes to the receive screen; nothing is counted from here. Counting is
 * a decision per line and there is no version of it that fits on a list row.
 */
const TONE: Record<SupplyStatus, "warn" | "good" | "danger"> = {
  declared: "warn",
  received: "good",
  cancelled: "danger",
}

const FILTERS: { key: SupplyStatus | ""; label: string }[] = [
  { key: "declared", label: supplyStatus.declared! },
  { key: "received", label: supplyStatus.received! },
  { key: "cancelled", label: supplyStatus.cancelled! },
  { key: "", label: t.all },
]

export function SuppliesPage() {
  // The default is the day's work: everything promised and not yet counted.
  const [status, setStatus] = useFilter<SupplyStatus>("status", "declared")
  const supplies = useQuery({
    queryKey: ["supplies", status],
    queryFn: () =>
      api<Supply[]>("/staff/supplies", { query: status ? { status } : {} }),
  })

  return (
    <>
      <PageTitle
        action={
          <div className="flex gap-1">
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
        {t.supplies}
      </PageTitle>

      <Panel>
        <div className="hidden border-b border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
          <span className="w-28">{t.supply}</span>
          <span className="flex-1">{t.seller}</span>
          <span className="w-20 text-right">Satr</span>
          <span className="w-24 text-right">{t.declared}</span>
          <span className="w-40 text-right">{t.when}</span>
          <span className="w-28">Holat</span>
        </div>
        <Async
          query={supplies}
          lines={5}
          empty={<Empty title={t.suppliesEmpty} hint={t.suppliesEmptyHint} />}
        >
          {(rows) => (
            <>
              {rows.map((batch) => (
                <Row key={batch.id} className="hover:bg-line-soft/60 sm:flex-nowrap">
                  <Link
                    to={`/supplies/${batch.id}`}
                    className="tabular w-28 shrink-0 font-medium text-ink outline-none focus-visible:underline"
                  >
                    {batch.code}
                  </Link>
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {batch.seller.name}
                  </span>
                  <span className="tabular w-20 text-right text-ink-soft">
                    {num(batch.lines.length)}
                  </span>
                  <span className="tabular w-24 text-right text-ink">
                    {num(batch.lines.reduce((sum, l) => sum + l.declared_quantity, 0))}
                  </span>
                  <span className="w-40 text-right text-[length:var(--text-small)] text-ink-faint">
                    {moment(batch.declared_at)}
                  </span>
                  <span className="w-28">
                    <Badge tone={TONE[batch.status]}>
                      {supplyStatus[batch.status] ?? batch.status}
                    </Badge>
                  </span>
                </Row>
              ))}
            </>
          )}
        </Async>
      </Panel>
    </>
  )
}
