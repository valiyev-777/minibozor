import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { RunningTotal } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Figure, Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { moment, num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * One screen, three figures, and the list they add up from.
 *
 * The plan asks for exactly that and it is the right shape: a shopkeeper's
 * question is "what am I owed", and the answer is one number with two others
 * beside it explaining how it got that small. No chart — a running total is
 * not a trend, and a graph of it would be decoration on the screen where
 * somebody reads their own money.
 *
 * `GET /staff/payouts/current` is the period still running, so the numbers
 * move. It says so itself (`is_final`), and that warning is on the screen
 * rather than in a tooltip: a seller who writes down a figure that changes
 * tomorrow has been misled by us.
 *
 * The three deductions — commission, handling, storage — are shown as their
 * own row rather than folded into the total. A fee somebody is charged and
 * cannot see is a fee they can only dispute.
 */
const LINE_TONE: Record<string, "good" | "danger" | "neutral"> = {
  sale: "good",
  commission: "danger",
  fulfilment: "danger",
  storage: "danger",
  refund: "danger",
  adjustment: "neutral",
}

export function AccountPage() {
  const total = useQuery({
    queryKey: ["running-total"],
    queryFn: () => api<RunningTotal>("/staff/payouts/current"),
  })

  return (
    <>
      <PageTitle>{t.account}</PageTitle>

      <Async query={total} lines={5}>
        {(row) => (
          <div className="space-y-[var(--gap-page)]">
            <Panel
              title={row.period_label}
              action={
                row.is_final ? (
                  <Badge tone="brand">{row.period_status}</Badge>
                ) : (
                  <Badge tone="warn">{t.notFinal}</Badge>
                )
              }
            >
              <div className="flex flex-wrap gap-10 border-t border-line-soft px-5 py-5">
                <Figure label={t.gross} value={som(row.gross_sales)} />
                <Figure label={t.refunds} value={som(row.refunds)} tone="danger" />
                {/* Green means "this is yours"; a negative payable is a debt
                    and colouring it green would be telling somebody they are
                    owed money they in fact owe. It goes negative for real —
                    storage on unsold stock in a period with no sales in it —
                    so the tone follows the sign rather than the field. */}
                <Figure
                  label={t.payable}
                  value={som(row.payable)}
                  tone={row.payable < 0 ? "danger" : "good"}
                />
              </div>

              <div className="flex flex-wrap gap-x-8 gap-y-2 border-t border-line-soft px-5 py-3 text-[length:var(--text-small)]">
                <span className="text-ink-soft">
                  {t.commission}: <span className="tabular text-ink">{som(row.commission)}</span>
                </span>
                <span className="text-ink-soft">
                  {t.fulfilment}: <span className="tabular text-ink">{som(row.fulfilment)}</span>
                </span>
                <span className="text-ink-soft">
                  {t.storage}: <span className="tabular text-ink">{som(row.storage)}</span>
                </span>
                <span className="text-ink-faint">
                  {row.starts_on} — {row.ends_on} · {moment(row.as_of)}
                </span>
              </div>
            </Panel>

            <Panel title={`${t.accountLines} · ${num(row.line_count)}`}>
              {row.lines.length === 0 ? (
                <Empty title={t.accountEmpty} hint={t.accountEmptyHint} />
              ) : (
                row.lines.map((line, index) => (
                  // `RunningLineOut` has no id: the running total is
                  // computed from movements rather than read out of a
                  // `statement_lines` table, so a line has no row of its own
                  // to be identified by. The index is stable because the list
                  // is rebuilt whole on every fetch and never reordered.
                  <Row key={index} className="sm:flex-nowrap">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[length:var(--text-body)] text-ink">
                        {line.title}
                      </p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {moment(line.occurred_at)}
                        {line.note ? ` · ${line.note}` : ""}
                      </p>
                    </div>
                    {line.quantity ? (
                      <span className="tabular w-12 text-right text-[length:var(--text-small)] text-ink-soft">
                        {num(line.quantity)}
                      </span>
                    ) : (
                      <span className="w-12" />
                    )}
                    <span
                      className={
                        "tabular w-32 text-right text-[length:var(--text-body)] " +
                        (LINE_TONE[line.kind] === "danger"
                          ? "text-danger"
                          : LINE_TONE[line.kind] === "good"
                            ? "text-good"
                            : "text-ink")
                      }
                    >
                      {som(line.amount)}
                    </span>
                  </Row>
                ))
              )}
            </Panel>
          </div>
        )}
      </Async>
    </>
  )
}
