import * as React from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Check, X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Supply } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label, Textarea } from "@/ui/field"
import { Async } from "@/ui/states"
import { Detail, Panel, Row } from "@/components/Panel"
import { useAction } from "@/lib/mutate"
import { moment, num } from "@/lib/format"
import { supplyStatus, t } from "@/lib/labels"

/**
 * The receive screen: what actually turned up, line by line.
 *
 * This is the moment goods reach the shelf and the moment a seller's product
 * goes on sale, so it is the most consequential screen in the panel and it is
 * built around one rule: **the declared figure is never edited.** A
 * declaration is a promise and a receipt is a fact, and the gap between them
 * is the only thing either party will want to talk about afterwards. So the
 * count goes in a box beside the promise and the difference is shown as it is
 * typed.
 *
 * Boxes start empty rather than pre-filled with the declared figure. A
 * pre-filled form is a form somebody accepts without counting, which is
 * exactly the mistake this screen exists to prevent — "Hammasini to'liq" is
 * there for the common case, but it is a button somebody has to press.
 *
 * A line left blank is received as nought, and the screen says so before the
 * button is pressed rather than after.
 */
export function SupplyPage() {
  const { id } = useParams()
  const supply = useQuery({
    queryKey: ["supply", id],
    queryFn: () => api<Supply>(`/staff/supplies/${id}`),
    enabled: Boolean(id),
  })

  return (
    <>
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/supplies">
            <ArrowLeft />
            {t.supplies}
          </Link>
        </Button>
      </div>
      <Async query={supply} lines={6}>
        {(batch) => <Receive batch={batch} />}
      </Async>
    </>
  )
}

function Receive({ batch }: { batch: Supply }) {
  const navigate = useNavigate()
  const [counts, setCounts] = React.useState<Record<number, string>>({})
  const [note, setNote] = React.useState("")
  const [reason, setReason] = React.useState("")
  const [refusing, setRefusing] = React.useState(false)

  const open = batch.status === "declared"

  const receive = useAction<void, Supply>({
    run: () =>
      api<Supply>(`/staff/supplies/${batch.id}/receive`, {
        method: "POST",
        json: {
          lines: batch.lines.map((line) => ({
            line_id: line.id,
            received_quantity: Number(counts[line.id]) || 0,
          })),
          note: note.trim(),
        },
      }),
    invalidate: [["supplies"], ["supply", String(batch.id)], ["summary"], ["stock"]],
    success: t.received_,
    onDone: () => navigate("/supplies"),
  })

  const refuse = useAction<void, Supply>({
    run: () =>
      api<Supply>(`/staff/supplies/${batch.id}/cancel`, {
        method: "POST",
        json: { reason: reason.trim() },
      }),
    invalidate: [["supplies"], ["supply", String(batch.id)], ["summary"]],
    success: t.refused,
    onDone: () => navigate("/supplies"),
  })

  const declaredTotal = batch.lines.reduce((sum, l) => sum + l.declared_quantity, 0)
  const countedTotal = batch.lines.reduce(
    (sum, l) => sum + (Number(counts[l.id]) || 0),
    0,
  )

  return (
    <div className="space-y-[var(--gap-page)]">
      <Panel
        title={
          <span className="flex flex-wrap items-center gap-2">
            <span className="tabular">{batch.code}</span>
            <Badge tone={open ? "warn" : batch.status === "received" ? "good" : "danger"}>
              {supplyStatus[batch.status] ?? batch.status}
            </Badge>
          </span>
        }
      >
        <div className="grid gap-4 border-t border-line-soft px-5 py-4 sm:grid-cols-4">
          <Detail label={t.seller}>{batch.seller.name}</Detail>
          <Detail label={t.declared}>
            <span className="tabular">{num(declaredTotal)}</span>
          </Detail>
          <Detail label={open ? t.counted : t.received}>
            <span className="tabular">
              {open
                ? num(countedTotal)
                : num(
                    batch.lines.reduce((sum, l) => sum + (l.received_quantity ?? 0), 0),
                  )}
            </span>
          </Detail>
          <Detail label={open ? t.supplies : t.received_}>
            {moment(open ? batch.declared_at : batch.received_at)}
          </Detail>
        </div>
        {batch.note ? (
          <p className="border-t border-line-soft px-5 py-2 text-[length:var(--text-small)] text-ink-soft">
            {batch.note}
          </p>
        ) : null}
      </Panel>

      <Panel
        title={t.counted}
        action={
          open ? (
            <div className="flex gap-2">
              <Button
                size="sm"
                onClick={() =>
                  setCounts(
                    Object.fromEntries(
                      batch.lines.map((l) => [l.id, String(l.declared_quantity)]),
                    ),
                  )
                }
              >
                {t.receiveAll}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setCounts({})}>
                {t.clearCounts}
              </Button>
            </div>
          ) : null
        }
      >
        <div className="hidden border-t border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
          <span className="flex-1">{t.product}</span>
          <span className="w-24 text-right">{t.declared}</span>
          <span className="w-24 text-right">{open ? t.counted : t.received}</span>
          <span className="w-20 text-right">{t.difference}</span>
        </div>

        {batch.lines.map((line) => {
          const typed = open
            ? Number(counts[line.id]) || 0
            : (line.received_quantity ?? 0)
          const gap = typed - line.declared_quantity
          return (
            <Row key={line.id} className="sm:flex-nowrap">
              <div className="min-w-0 flex-1">
                <p className="truncate text-ink">{line.product_title}</p>
                <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                  {line.variant_label} · {line.sku}
                </p>
              </div>
              <span className="tabular w-24 text-right text-ink-soft">
                {num(line.declared_quantity)}
              </span>
              <div className="w-24 text-right">
                {open ? (
                  <>
                    <Label htmlFor={`count-${line.id}`} className="sr-only">
                      {line.variant_label} {t.counted}
                    </Label>
                    <Input
                      id={`count-${line.id}`}
                      inputMode="numeric"
                      className="tabular w-24 text-right"
                      placeholder="0"
                      value={counts[line.id] ?? ""}
                      onChange={(event) =>
                        setCounts({
                          ...counts,
                          [line.id]: event.target.value.replace(/\D/g, ""),
                        })
                      }
                    />
                  </>
                ) : (
                  <span className="tabular text-ink">
                    {line.received_quantity === null ? "—" : num(line.received_quantity)}
                  </span>
                )}
              </div>
              <span
                className={
                  "tabular w-20 text-right " + (gap < 0 ? "text-danger" : "text-ink-soft")
                }
              >
                {!open && line.received_quantity === null
                  ? "—"
                  : gap > 0
                    ? `+${num(gap)}`
                    : num(gap)}
              </span>
            </Row>
          )
        })}

        {open ? (
          <div className="space-y-3 border-t border-line px-5 py-4">
            <Hint>{t.qualityHint}</Hint>
            <div className="space-y-1.5">
              <Label htmlFor="note">{t.note}</Label>
              <Textarea
                id="note"
                rows={2}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Bir dona qadoqsiz kelgan"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="lg"
                disabled={receive.isPending}
                onClick={() => receive.mutate()}
              >
                <Check />
                {t.accept}
              </Button>
              <Button
                variant="quiet"
                size="lg"
                onClick={() => setRefusing((was) => !was)}
              >
                <X />
                {t.refuse}
              </Button>
            </div>

            {refusing ? (
              <div className="space-y-2 rounded-[var(--radius-control)] border border-danger/40 bg-danger-soft p-4">
                <Label htmlFor="reason">{t.refuseReason}</Label>
                <Textarea
                  id="reason"
                  rows={2}
                  autoFocus
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Kelgan tovar kartochkadagi rangda emas"
                />
                <Hint>{t.refuseHint}</Hint>
                <Button
                  variant="danger"
                  disabled={!reason.trim() || refuse.isPending}
                  onClick={() => refuse.mutate()}
                >
                  {t.refuse}
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </Panel>
    </div>
  )
}
