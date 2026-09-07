import * as React from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { ArrowLeft, PhoneCall } from "lucide-react"
import clsx from "clsx"
import { Button, ButtonLink, Empty, Field, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { pickupQueued } from "@/offline/derive"
import { prettyPhone } from "@/lib/format"
import { statusWord } from "./PickupsPage"

/**
 * One collection run, door by door.
 *
 * Line by line rather than all-or-nothing, because a round rarely is: one
 * customer is in and hands the shirt over, the next is not answering. Each
 * line is one of three states and starts in none of them — an untouched line
 * is "nobody has been", which is a different thing from "we went and got
 * nothing", and the server keeps them apart too (`collected` is nullable).
 *
 * A line that was not collected needs a reason, for the same purpose a failed
 * delivery does: somebody has to decide what happens to that return, and they
 * decide from this sentence. The submit button stays disabled until every line
 * that says "no" has one, rather than letting the courier walk away and
 * discover it from a 400 inside the queue an hour later.
 */
type Mark = { collected: boolean | null; reason: string }

export function PickupRunPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { pickups, rows, record, reachable } = useOffline()

  const runId = Number(id)
  const run = pickups.data.find((r) => r.id === runId)

  const [marks, setMarks] = React.useState<Record<number, Mark>>({})
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)

  if (!run) return <Empty>Bu yig'uv reysi ro'yxatda yo'q.</Empty>

  const queued = pickupQueued(run, rows)
  const editable = run.status === "open" && !queued

  const markFor = (lineId: number, line: { collected: boolean | null }): Mark =>
    marks[lineId] ?? { collected: line.collected ?? null, reason: "" }

  const decided = run.lines.every((line) => markFor(line.return_request_id, line).collected !== null)
  const reasonsGiven = run.lines.every((line) => {
    const mark = markFor(line.return_request_id, line)
    return mark.collected !== false || mark.reason.trim().length > 0
  })

  function set(lineId: number, change: Partial<Mark>) {
    setMarks((current) => ({
      ...current,
      [lineId]: { ...(current[lineId] ?? { collected: null, reason: "" }), ...change },
    }))
  }

  async function submit() {
    if (!decided) {
      toast.error("Har bir tovarni belgilang.")
      return
    }
    if (!reasonsGiven) {
      toast.error("Olinmagan tovar uchun sabab yozing.")
      return
    }
    setBusy(true)
    try {
      await record({
        kind: "pickup-collect",
        targetId: run!.id,
        body: {
          lines: run!.lines.map((line) => {
            const mark = markFor(line.return_request_id, line)
            return {
              return_request_id: line.return_request_id,
              collected: mark.collected === true,
              reason: mark.collected === true ? "" : mark.reason.trim(),
              photo_url: "",
            }
          }),
          note: note.trim(),
        },
        label: `${run!.code} · Yig'uv`,
      })
      navigate("/pickups", { replace: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4 pb-safe">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-lg font-semibold text-muted"
      >
        <ArrowLeft className="size-6" />
        Yig'uv
      </button>

      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-3xl font-bold">{run.code}</h1>
        <Pill tone={run.status === "open" ? "brand" : "plain"}>{statusWord(run.status)}</Pill>
      </div>

      {queued ? (
        <Panel tone="pending">
          <p className="text-lg font-bold text-pending">Topshirildi · yuborilmagan</p>
          <p className="mt-1 text-base text-muted">
            Telefoningizda saqlandi. Tarmoq qaytganda o'zi yuboriladi.
          </p>
        </Panel>
      ) : null}

      <ul className="space-y-3">
        {run.lines.map((line) => {
          const mark = markFor(line.return_request_id, line)
          return (
            <li key={line.id}>
              <Panel
                tone={mark.collected === true ? "good" : mark.collected === false ? "bad" : "plain"}
              >
                <p className="text-xl font-semibold">{line.product_title || line.order_code}</p>
                <p className="text-base text-muted">{line.order_code}</p>
                <p className="selectable mt-2 text-lg">{line.address_line}</p>
                <p className="text-lg text-muted">{line.customer_name}</p>
                {line.reason ? (
                  <p className="mt-1 text-base text-muted">
                    Qaytarish sababi: <span className="text-ink">{line.reason}</span>
                  </p>
                ) : null}

                {line.customer_phone ? (
                  <ButtonLink href={`tel:${line.customer_phone}`} tone="ghost" className="mt-3">
                    <PhoneCall className="size-6" />
                    {prettyPhone(line.customer_phone)}
                  </ButtonLink>
                ) : null}

                {editable ? (
                  <>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <Choice
                        active={mark.collected === true}
                        tone="good"
                        onClick={() => set(line.return_request_id, { collected: true, reason: "" })}
                      >
                        Olindi
                      </Choice>
                      <Choice
                        active={mark.collected === false}
                        tone="bad"
                        onClick={() => set(line.return_request_id, { collected: false })}
                      >
                        Olinmadi
                      </Choice>
                    </div>
                    {mark.collected === false ? (
                      <Field
                        className="mt-3"
                        label="Nega olinmadi"
                        value={mark.reason}
                        maxLength={200}
                        onChange={(e) => set(line.return_request_id, { reason: e.target.value })}
                      />
                    ) : null}
                  </>
                ) : (
                  <p className="mt-2 text-lg font-semibold">
                    {line.collected === true
                      ? "Olindi"
                      : line.collected === false
                        ? `Olinmadi${line.note ? ` — ${line.note}` : ""}`
                        : "Belgilanmagan"}
                  </p>
                )}
              </Panel>
            </li>
          )
        })}
      </ul>

      {editable ? (
        <>
          <Field
            label="Izoh (ixtiyoriy)"
            value={note}
            maxLength={200}
            onChange={(e) => setNote(e.target.value)}
          />
          <Button onClick={() => void submit()} busy={busy} disabled={!decided || !reasonsGiven}>
            Yig'uvni topshirish
          </Button>
          {!reachable ? (
            <p className="text-center text-base text-pending">
              Tarmoq yo'q — telefoningizda saqlanadi va o'zi yuboriladi.
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  )
}

function Choice({
  active,
  tone,
  onClick,
  children,
}: {
  active: boolean
  tone: "good" | "bad"
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "h-16 rounded-[var(--radius-work)] border-2 text-xl font-bold",
        active && tone === "good" && "border-good bg-good text-good-ink",
        active && tone === "bad" && "border-bad bg-bad text-bad-ink",
        !active && "border-line",
      )}
    >
      {children}
    </button>
  )
}
