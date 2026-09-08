import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Return, ReturnStatus } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useRole } from "@/auth/session"
import { useFilter } from "@/lib/useFilter"
import { moment, som } from "@/lib/format"
import { returnStatus, t } from "@/lib/labels"

/**
 * One list of returns, read by two people whose turns alternate.
 *
 * A return is answered four times in order: the operator decides it, a courier
 * collects the parcel, the warehouse says what arrived, the seller says what
 * to do about it. Two of those four are behind this login, and they are not
 * consecutive — so hiding half the row from each of them would leave neither
 * able to see whose turn it is.
 *
 * `awaiting` is the filter that makes the list a queue: `inspection` is
 * "arrived, nobody has looked", `decision` is "looked at, the seller has not
 * answered". The warehouse lands on the first, because that is the one with
 * something to do at a bench.
 */
const TONE: Record<ReturnStatus, "warn" | "brand" | "good" | "danger"> = {
  submitted: "warn",
  approved: "brand",
  rejected: "danger",
  refunded: "good",
}

export function ReturnsPage() {
  const role = useRole()
  const [awaiting, setAwaiting] = useFilter<"inspection" | "decision">(
    "awaiting",
    role === "warehouse" ? "inspection" : "",
  )
  const returns = useQuery({
    queryKey: ["returns", awaiting],
    queryFn: () =>
      api<Return[]>("/staff/returns", { query: awaiting ? { awaiting } : {} }),
  })

  const FILTERS = [
    { key: "" as const, label: t.all },
    { key: "inspection" as const, label: t.awaitingInspection },
    { key: "decision" as const, label: t.awaitingDecision },
  ]

  return (
    <>
      <PageTitle
        action={
          <div className="flex flex-wrap gap-1">
            {FILTERS.map((filter) => (
              <button
                key={filter.key}
                type="button"
                onClick={() => setAwaiting(filter.key)}
                className={
                  "rounded-[var(--radius-control)] px-2.5 py-1 text-[length:var(--text-small)] " +
                  (awaiting === filter.key
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
        {t.returns}
      </PageTitle>

      <Panel>
        <Async
          query={returns}
          lines={5}
          empty={<Empty title={t.returnsEmpty} hint={t.returnsEmptyHint} />}
        >
          {(rows) => (
            <>
              {rows.map((row) => (
                <Row key={row.id} className="hover:bg-line-soft/60 sm:flex-nowrap">
                  <Link
                    to={`/returns/${row.id}`}
                    className="tabular w-28 shrink-0 font-medium text-ink outline-none focus-visible:underline"
                  >
                    {row.order_code}
                  </Link>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{row.product_title || "—"}</p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {row.customer_name || row.customer_phone} · {row.reason}
                    </p>
                  </div>
                  <span className="w-32 truncate text-[length:var(--text-small)] text-ink-soft">
                    {row.seller_name || "—"}
                  </span>
                  <span className="tabular w-28 text-right text-ink">
                    {row.status === "refunded" ? som(row.refund_amount) : "—"}
                  </span>
                  <span className="w-32 text-right text-[length:var(--text-small)] text-ink-faint">
                    {moment(row.created_at)}
                  </span>
                  <Badge tone={TONE[row.status]}>
                    {returnStatus[row.status] ?? row.status}
                  </Badge>
                  {/* Whose turn it is, as one more pill. The two that matter
                      here are "nobody has looked" and "the seller has not
                      answered" — everything else is somebody else's wait. */}
                  {row.inspection ? (
                    <Badge tone={row.inspection === "ok" ? "good" : "danger"}>
                      {row.inspection_label}
                    </Badge>
                  ) : row.status === "approved" || row.status === "refunded" ? (
                    <Badge tone="warn">{t.awaitingInspection}</Badge>
                  ) : (
                    <span className="w-24" />
                  )}
                </Row>
              ))}
            </>
          )}
        </Async>
      </Panel>
    </>
  )
}
