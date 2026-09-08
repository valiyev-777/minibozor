import type * as React from "react"
import { RotateCcw, Truck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Return, SellerDecision } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Async, Empty } from "@/ui/states"
import { Detail, Panel } from "@/components/Panel"
import { useAction } from "@/lib/mutate"
import { PageTitle } from "@/components/Shell"
import { daysLeft, date, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * The goods that came back, and the one decision that is the seller's.
 *
 * A refund settles the customer. It settles nothing about the shirt, which is
 * in a box at the warehouse belonging to this seller. Two answers follow, in
 * order: the warehouse says what arrived — whole or damaged — and then the
 * seller says what to do about it.
 *
 * **The buttons come from the server.** `seller_decisions` is the list of
 * moves still open on the row, and it is empty until somebody has looked at
 * the parcel and again once the seller has answered. Damaged goods carry only
 * `take_back`, because they do not go back on sale — that rule is enforced in
 * `POST /staff/returns/{id}/decide` and is deliberately not written again
 * here. A client with its own copy eventually offers a button the server
 * refuses.
 *
 * **The deadline is shown in days.** A date makes the reader do the
 * arithmetic, and the whole point of the deadline is that they notice it in
 * time: nothing decided within it goes back on sale by itself, which is the
 * answer that costs them least but is still not the one they chose.
 */
const ACTION: Record<SellerDecision, { label: string; icon: React.ReactNode; primary: boolean }> = {
  relist: { label: t.relisted, icon: <RotateCcw />, primary: true },
  take_back: { label: t.takeBack, icon: <Truck />, primary: false },
}

export function ReturnsPage() {
  const returns = useQuery({
    queryKey: ["returns"],
    queryFn: () => api<Return[]>("/staff/returns"),
  })

  return (
    <>
      <PageTitle>{t.returns}</PageTitle>

      <Async
        query={returns}
        lines={4}
        empty={
          <Panel>
            <Empty title={t.returnsEmpty} hint={t.returnsEmptyHint} />
          </Panel>
        }
      >
        {(rows) => (
          <div className="space-y-[var(--gap-page)]">
            {rows.map((row) => (
              <ReturnCard key={row.id} row={row} />
            ))}
          </div>
        )}
      </Async>
    </>
  )
}

function ReturnCard({ row }: { row: Return }) {
  const decide = useAction<SellerDecision, Return>({
    run: (decision) =>
      api<Return>(`/staff/returns/${row.id}/decide`, {
        method: "POST",
        json: { decision },
      }),
    invalidate: [["returns"], ["listings"]],
    success: t.decisionSaved,
  })

  const left = daysLeft(row.decision_due_at)

  return (
    <Panel
      title={
        <span className="flex flex-wrap items-center gap-2">
          <span className="tabular">{row.order_code}</span>
          {row.inspection ? (
            <Badge tone={row.inspection === "ok" ? "good" : "danger"}>
              {row.inspection_label}
            </Badge>
          ) : (
            <Badge tone="warn">{t.awaitingInspection}</Badge>
          )}
          {row.seller_decision ? (
            <Badge tone="brand">{row.seller_decision_label}</Badge>
          ) : null}
        </span>
      }
      action={
        <span className="text-[length:var(--text-small)] text-ink-soft">
          {som(row.refund_amount)}
        </span>
      }
    >
      <div className="grid gap-4 border-t border-line-soft px-5 py-4 sm:grid-cols-3">
        <Detail label={t.title}>{row.product_title || "—"}</Detail>
        <Detail label={t.customer}>{row.customer_name || row.customer_phone}</Detail>
        <Detail label={t.refusalReason}>{row.reason || "—"}</Detail>
        {row.inspection ? (
          <Detail label={t.inspection} className="sm:col-span-2">
            {row.inspection_label}
            {row.inspection_note ? (
              <span className="text-ink-soft"> · {row.inspection_note}</span>
            ) : null}
          </Detail>
        ) : null}
        {row.decision_due_at && !row.seller_decision ? (
          <Detail label={t.decideBy}>
            {left !== null && left <= 0 ? (
              <span className="text-danger">{t.decisionOverdue}</span>
            ) : (
              <>
                {date(row.decision_due_at)}
                {left !== null ? (
                  <span className="text-ink-soft"> · {left} kun</span>
                ) : null}
              </>
            )}
          </Detail>
        ) : null}
        {row.seller_decision ? (
          <Detail label={t.decided}>{date(row.decided_at)}</Detail>
        ) : null}
      </div>

      {row.seller_decisions.length > 0 ? (
        <div className="flex flex-wrap gap-2 border-t border-line bg-line-soft/50 px-5 py-3">
          {row.seller_decisions.map((decision) => {
            const action = ACTION[decision]
            return (
              <Button
                key={decision}
                variant={action.primary ? "primary" : "outline"}
                disabled={decide.isPending}
                onClick={() => decide.mutate(decision)}
              >
                {action.icon}
                {action.label}
              </Button>
            )
          })}
        </div>
      ) : null}
    </Panel>
  )
}
