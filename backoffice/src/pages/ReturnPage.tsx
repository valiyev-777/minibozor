import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, Check, PackageCheck, PackageX, Wallet, X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Return } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Label, Textarea } from "@/ui/field"
import { Async } from "@/ui/states"
import { Detail, Panel } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { useRole } from "@/auth/session"
import { useAction } from "@/lib/mutate"
import { date, moment, som } from "@/lib/format"
import { returnStatus, t } from "@/lib/labels"

/**
 * One return, and every answer it is waiting for — each shown to the person
 * whose answer it is.
 *
 * Three decisions live here and they belong to two different roles:
 *
 * * **the money**, the operator's: approve, refuse with a reason the customer
 *   is given, then pay it back and say whether the goods went on the shelf;
 * * **the parcel**, the warehouse's: whole, or damaged, once.
 *
 * The seller's decision is the fourth and is not here at all — it is theirs,
 * in their own cabinet. It is *shown* here, because "the seller has not
 * answered yet" is what an operator is asked about.
 *
 * `next_statuses` decides the money buttons and `inspection` decides whether
 * there is a verdict button left, so neither the transition table nor the
 * once-only rule is copied into this client.
 */
export function ReturnPage() {
  const { id } = useParams()
  const row = useQuery({
    queryKey: ["return", id],
    queryFn: () => api<Return>(`/staff/returns/${id}`),
    enabled: Boolean(id),
  })

  return (
    <>
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/returns">
            <ArrowLeft />
            {t.returns}
          </Link>
        </Button>
      </div>
      <Async query={row} lines={6}>
        {(request) => <Detailed request={request} />}
      </Async>
    </>
  )
}

function Detailed({ request }: { request: Return }) {
  const role = useRole()
  const keys = [["returns"], ["return", String(request.id)], ["summary"]]

  return (
    <div className="space-y-[var(--gap-page)]">
      <Panel
        title={
          <span className="flex flex-wrap items-center gap-2">
            <span className="tabular">{request.order_code}</span>
            <Badge tone={request.status === "refunded" ? "good" : "brand"}>
              {returnStatus[request.status] ?? request.status}
            </Badge>
            {request.inspection ? (
              <Badge tone={request.inspection === "ok" ? "good" : "danger"}>
                {request.inspection_label}
              </Badge>
            ) : null}
            {request.seller_decision ? (
              <Badge tone="brand">{request.seller_decision_label}</Badge>
            ) : null}
          </span>
        }
        action={
          <span className="text-[length:var(--text-small)] text-ink-soft">
            {moment(request.created_at)}
          </span>
        }
      >
        <div className="grid gap-4 border-t border-line-soft px-5 py-4 sm:grid-cols-3">
          <Detail label={t.customer}>
            {request.customer_name}
            <a
              href={`tel:${request.customer_phone}`}
              className="block text-brand-deep underline"
            >
              {request.customer_phone}
            </a>
          </Detail>
          <Detail label={t.product}>{request.product_title || "—"}</Detail>
          <Detail label={t.seller}>{request.seller_name || "—"}</Detail>
          <Detail label={t.reason} className="sm:col-span-2">
            {request.reason}
            {request.comment ? (
              <span className="text-ink-soft"> · {request.comment}</span>
            ) : null}
          </Detail>
          {/* Only once it has actually been paid. `refund_amount` is nought
              until somebody refunds, and a money field reading "0 so'm" on a
              return nobody has decided says the customer is getting nothing
              — which is a different sentence from "not yet". */}
          <Detail label={t.refund}>
            {request.status === "refunded" ? (
              <span className="tabular">{som(request.refund_amount)}</span>
            ) : (
              <span className="text-ink-faint">—</span>
            )}
          </Detail>
          {request.resolution ? (
            <Detail label={t.note} className="sm:col-span-3">
              {request.resolution}
            </Detail>
          ) : null}
          {request.inspection ? (
            <Detail label={t.inspection}>
              {request.inspection_label}
              {request.inspection_note ? ` · ${request.inspection_note}` : ""}
              <span className="block text-[length:var(--text-micro)] text-ink-faint">
                {moment(request.inspected_at)}
              </span>
            </Detail>
          ) : null}
          {request.decision_due_at && !request.seller_decision ? (
            <Detail label={t.awaitingDecision}>{date(request.decision_due_at)}</Detail>
          ) : null}
          {request.seller_decision ? (
            <Detail label={t.sellerDecision}>
              {request.seller_decision_label}
              {request.relisted ? (
                <span className="text-good"> · {t.restock}</span>
              ) : null}
            </Detail>
          ) : null}
        </div>

        {request.photos.length > 0 ? (
          <div className="flex flex-wrap gap-2 border-t border-line-soft px-5 py-4">
            {request.photos.map((url) => (
              <Thumb key={url} src={url} className="size-20" />
            ))}
          </div>
        ) : null}
      </Panel>

      {role === "warehouse" ? null : <Money request={request} keys={keys} />}
      {role === "operator" ? null : <Inspect request={request} keys={keys} />}
    </div>
  )
}

/** The operator's three: approve, refuse, pay back. */
function Money({ request, keys }: { request: Return; keys: string[][] }) {
  const [reason, setReason] = React.useState("")
  const [refusing, setRefusing] = React.useState(false)

  const decide = useAction<{ path: string; body: unknown }, Return>({
    run: ({ path, body }) =>
      api<Return>(`/staff/returns/${request.id}/${path}`, {
        method: "POST",
        json: body,
      }),
    invalidate: keys,
    success: t.saved,
  })

  const can = (status: string) => request.next_statuses.includes(status as never)

  if (request.next_statuses.length === 0) {
    return (
      <Panel title={t.refund}>
        <p className="border-t border-line-soft px-5 py-4 text-[length:var(--text-small)] text-ink-soft">
          {returnStatus[request.status]} — {moment(request.created_at)}
        </p>
      </Panel>
    )
  }

  return (
    <Panel title={t.refund}>
      <div className="space-y-3 border-t border-line-soft px-5 py-4">
        <div className="flex flex-wrap gap-2">
          {can("approved") ? (
            <Button
              variant="primary"
              disabled={decide.isPending}
              onClick={() => decide.mutate({ path: "approve", body: {} })}
            >
              <Check />
              {t.approve}
            </Button>
          ) : null}
          {can("rejected") ? (
            <Button variant="quiet" onClick={() => setRefusing((was) => !was)}>
              <X />
              {t.reject}
            </Button>
          ) : null}
          {can("refunded") ? (
            <>
              {/* `restock` has no default on the server and none here. What
                  came back whole belongs on the shelf and what came back
                  damaged belongs on nobody's count; a default would be a
                  count moving, or failing to move, by omission. */}
              <Button
                variant="primary"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({ path: "refund", body: { restock: true } })
                }
              >
                <Wallet />
                {t.refund} · {t.restockYes}
              </Button>
              <Button
                variant="outline"
                disabled={decide.isPending}
                onClick={() =>
                  decide.mutate({ path: "refund", body: { restock: false } })
                }
              >
                <Wallet />
                {t.refund} · {t.restockNo}
              </Button>
            </>
          ) : null}
        </div>

        {can("refunded") ? <Hint>{t.restockAsk}</Hint> : null}

        {refusing ? (
          <div className="space-y-2 rounded-[var(--radius-control)] border border-danger/40 bg-danger-soft p-4">
            <Label htmlFor="reject-reason">{t.refuseReason}</Label>
            <Textarea
              id="reject-reason"
              rows={2}
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Tovar ishlatilgan holatda qaytdi"
            />
            <Hint>Bu jumla xaridorga yetkaziladi.</Hint>
            <Button
              variant="danger"
              disabled={!reason.trim() || decide.isPending}
              onClick={() =>
                decide.mutate({ path: "reject", body: { reason: reason.trim() } })
              }
            >
              {t.reject}
            </Button>
          </div>
        ) : null}
      </div>
    </Panel>
  )
}

/** The warehouse's one, and only once. */
function Inspect({ request, keys }: { request: Return; keys: string[][] }) {
  const [note, setNote] = React.useState("")

  const inspect = useAction<"ok" | "damaged", Return>({
    run: (result) =>
      api<Return>(`/staff/returns/${request.id}/inspect`, {
        method: "POST",
        json: { result, note: note.trim() },
      }),
    invalidate: keys,
    success: t.inspected,
  })

  // Nothing to look at until the money side has let the parcel through, and
  // nothing to say once somebody has looked: the first verdict is the one the
  // seller was told and the one their deadline runs from.
  const arrived = request.status === "approved" || request.status === "refunded"
  if (!arrived || request.inspection) return null

  return (
    <Panel title={t.inspect}>
      <div className="space-y-3 border-t border-line-soft px-5 py-4">
        <div className="space-y-1.5">
          <Label htmlFor="inspect-note">{t.note}</Label>
          <Textarea
            id="inspect-note"
            rows={2}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Yorliqlari joyida"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="good"
            disabled={inspect.isPending}
            onClick={() => inspect.mutate("ok")}
          >
            <PackageCheck />
            {t.inspectWhole}
          </Button>
          <Button
            variant="danger"
            disabled={inspect.isPending}
            onClick={() => inspect.mutate("damaged")}
          >
            <PackageX />
            {t.inspectDamaged}
          </Button>
        </div>
        <Hint>
          Butun bo'lsa — sotuvchiga qaror uchun muddat beriladi. Buzilgan bo'lsa —
          sotuvga qaytmaydi.
        </Hint>
      </div>
    </Panel>
  )
}
