import * as React from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Check, Phone, X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import { actionKey } from "@/api/keys"
import type { Run } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label } from "@/ui/field"
import { Async } from "@/ui/states"
import { useAction } from "@/lib/mutate"
import { num } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * A collection run: several doors, and one send at the end.
 *
 * Unlike a delivery, this is *one* write for the whole round — the endpoint
 * takes every door at once and closes the run. That is the right shape,
 * because the run is what the warehouse is waiting for and a half-sent run is
 * a run they cannot book in. So each door is marked here and the whole thing
 * goes when the courier is back in the van.
 *
 * A door not collected needs a reason. The server requires it and so does the
 * operator reading it: "not collected" with nothing after it is the row
 * nobody can act on.
 */
export function RunPage() {
  const { id } = useParams()
  const run = useQuery({
    queryKey: ["run", id],
    queryFn: async () => {
      const rows = await api<Run[]>("/courier/pickups")
      return rows.find((row) => String(row.id) === id) ?? null
    },
    enabled: Boolean(id),
  })

  return (
    <div className="space-y-4 px-[var(--gap-page)] py-[var(--gap-page)]">
      <Button asChild variant="ghost" size="sm">
        <Link to="/">
          <ArrowLeft />
          {t.today}
        </Link>
      </Button>

      <Async query={run} lines={4}>
        {(row) =>
          row === null ? (
            <p className="rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-6 text-center text-ink-soft">
              Bu vazifa sizga berilmagan.
            </p>
          ) : (
            <Doors run={row} />
          )
        }
      </Async>
    </div>
  )
}

type Mark = { collected: boolean; reason: string }

function Doors({ run }: { run: Run }) {
  const navigate = useNavigate()
  const [marks, setMarks] = React.useState<Record<number, Mark>>({})
  const [attempt, setAttempt] = React.useState(0)

  const open = run.next_statuses.includes("collected")

  const send = useAction<void, Run>({
    run: () =>
      api<Run>(`/courier/pickups/${run.id}/collect`, {
        method: "POST",
        key: actionKey("collect", run.id, attempt),
        json: {
          lines: run.lines.map((line) => {
            const mark = marks[line.return_request_id]
            return {
              return_request_id: line.return_request_id,
              collected: mark?.collected ?? false,
              reason: mark?.collected ? "" : (mark?.reason ?? ""),
            }
          }),
        },
      }),
    invalidate: [["runs"], ["run", String(run.id)], ["round"]],
    success: t.collectDone,
    onDone: () => navigate("/"),
  })

  React.useEffect(() => {
    if (send.isError) setAttempt((was) => was + 1)
  }, [send.isError])

  // Every door has to have been answered one way or the other, and a refusal
  // has to say why — the same rule the server keeps, said before it is hit.
  const ready = run.lines.every((line) => {
    const mark = marks[line.return_request_id]
    if (mark === undefined) return false
    return mark.collected || mark.reason.trim().length > 0
  })

  const set = (id: number, patch: Partial<Mark>) =>
    setMarks((current) => ({
      ...current,
      [id]: { collected: false, reason: "", ...current[id], ...patch },
    }))

  return (
    <div className="space-y-4">
      <section className="space-y-1 rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="tabular font-semibold text-ink">{run.code}</span>
          <Badge tone={open ? "warn" : "good"}>
            {num(run.lines.length)} manzil
          </Badge>
        </div>
        {run.note ? <p className="text-ink-soft">{run.note}</p> : null}
        {open ? <Hint>{t.collectHint}</Hint> : null}
      </section>

      {run.lines.map((line) => {
        const mark = marks[line.return_request_id]
        const answered = mark !== undefined
        return (
          <section
            key={line.id}
            className="space-y-3 rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-4"
          >
            <div className="space-y-0.5">
              <p className="tabular text-[length:var(--text-small)] text-ink-soft">
                {line.order_code}
              </p>
              <p className="selectable text-lg font-medium text-ink">
                {line.address_line}
              </p>
              <p className="text-[length:var(--text-small)] text-ink-soft">
                {line.product_title || "—"} · {line.reason}
              </p>
            </div>

            <Button asChild variant="outline" size="lg" block>
              <a href={`tel:${line.customer_phone}`}>
                <Phone />
                {line.customer_name} · {line.customer_phone}
              </a>
            </Button>

            {open ? (
              <>
                <div className="flex gap-2">
                  <Button
                    variant={mark?.collected ? "good" : "outline"}
                    size="lg"
                    className="flex-1"
                    onClick={() => set(line.return_request_id, { collected: true })}
                  >
                    <Check />
                    {t.collect}
                  </Button>
                  <Button
                    variant={answered && !mark?.collected ? "danger" : "outline"}
                    size="lg"
                    className="flex-1"
                    onClick={() => set(line.return_request_id, { collected: false })}
                  >
                    <X />
                    {t.notCollected}
                  </Button>
                </div>

                {answered && !mark?.collected ? (
                  <div className="space-y-1.5">
                    <Label htmlFor={`reason-${line.id}`}>{t.reason}</Label>
                    <Input
                      id={`reason-${line.id}`}
                      value={mark?.reason ?? ""}
                      onChange={(event) =>
                        set(line.return_request_id, { reason: event.target.value })
                      }
                      placeholder="Uyda hech kim yo'q"
                    />
                    <Hint>{t.reasonRequired}</Hint>
                  </div>
                ) : null}
              </>
            ) : (
              <Badge tone={line.collected ? "good" : "danger"}>
                {line.collected ? t.collectDone : line.note || t.notCollected}
              </Badge>
            )}
          </section>
        )
      })}

      {open ? (
        <Button
          variant="primary"
          size="lg"
          block
          disabled={!ready || send.isPending}
          onClick={() => send.mutate()}
        >
          <Check />
          {t.sendRun}
        </Button>
      ) : null}
    </div>
  )
}
