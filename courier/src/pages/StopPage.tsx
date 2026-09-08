import * as React from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Camera, Check, Phone, X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api, uploadImage } from "@/api/client"
import { actionKey } from "@/api/keys"
import type { Stop } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Hint, Input, Label, Textarea } from "@/ui/field"
import { Async, messageOf } from "@/ui/states"
import { useAction } from "@/lib/mutate"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * One door, and the two things that can happen at it.
 *
 * The address is the largest thing on the screen and the telephone number is a
 * `tel:` link, because those are what the screen is for while walking up to
 * the building. Everything below them is what happens once somebody answers.
 *
 * **Delivered needs a name.** One field a courier can always fill in, standing
 * in front of the person who took the goods, and the answer to "I never
 * received it". A photograph is not required: an upload needs signal, and
 * requiring one would stop a courier in a basement finishing a delivery they
 * have already made.
 *
 * **The cash figure has to match.** The server refuses one that does not, and
 * the box is pre-filled with what is owed for exactly that reason — a courier
 * who mistypes it has nothing to point at afterwards, and a mismatch is far
 * likelier to be a typo than a part payment worth recording.
 *
 * **Giving up is not here.** A courier records what happened at one door; an
 * operator who can see three failures and telephone the customer decides what
 * follows. So the second button records an attempt and keeps the order.
 */
export function StopPage() {
  const { id } = useParams()
  const stop = useQuery({
    queryKey: ["stop", id],
    queryFn: async () => {
      const rows = await api<Stop[]>("/courier/orders")
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

      <Async query={stop} lines={4}>
        {(row) =>
          row === null ? (
            <p className="rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-6 text-center text-ink-soft">
              Bu manzil sizning vazifalaringizda yo'q.
            </p>
          ) : (
            <Door stop={row} />
          )
        }
      </Async>
    </div>
  )
}

function Door({ stop }: { stop: Stop }) {
  const navigate = useNavigate()
  const [name, setName] = React.useState("")
  const [cash, setCash] = React.useState(String(stop.cash_due || ""))
  const [photo, setPhoto] = React.useState("")
  const [reason, setReason] = React.useState("")
  const [failing, setFailing] = React.useState(false)
  const [uploadError, setUploadError] = React.useState<string | null>(null)
  const [uploading, setUploading] = React.useState(false)

  // Bumped on every refusal, so a corrected cash figure is a new request
  // rather than a replay of the answer that refused the last one.
  const [attempt, setAttempt] = React.useState(0)

  const deliver = useAction<void, Stop>({
    run: () =>
      api<Stop>(`/courier/orders/${stop.id}/deliver`, {
        method: "POST",
        key: actionKey("deliver", stop.id, attempt),
        json: {
          recipient_name: name.trim(),
          photo_url: photo,
          cash_collected: Number(cash) || 0,
        },
      }),
    invalidate: [["round"], ["stop", String(stop.id)]],
    success: t.deliveredDone,
    onDone: () => navigate("/"),
  })

  const failed = useAction<void, Stop>({
    run: () =>
      api<Stop>(`/courier/orders/${stop.id}/failed`, {
        method: "POST",
        key: actionKey("failed", stop.id, attempt),
        json: { reason: reason.trim(), photo_url: photo },
      }),
    invalidate: [["round"], ["stop", String(stop.id)]],
    success: t.failedDone,
    onDone: () => navigate("/"),
  })

  // A refusal means the *next* press is a new decision, not a retry of this
  // one — see `actionKey`.
  React.useEffect(() => {
    if (deliver.isError || failed.isError) setAttempt((was) => was + 1)
  }, [deliver.isError, failed.isError])

  const pick = async (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError(null)
    try {
      const uploaded = await uploadImage(file)
      setPhoto(uploaded.media_url)
    } catch (problem) {
      setUploadError(messageOf(problem))
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      <section className="space-y-2 rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="tabular font-semibold text-ink">{stop.code}</span>
          {stop.cash_due > 0 ? (
            <Badge tone="warn">
              {t.cashDue}: {som(stop.cash_due)}
            </Badge>
          ) : (
            <Badge tone="good">{t.paidAlready}</Badge>
          )}
        </div>

        {/* The address is selectable — a courier copies it into a map — while
            the rest of the screen is not, because a long press on a button
            while holding a parcel puts a selection handle over the thing they
            were reaching for. */}
        <p className="selectable text-lg font-medium text-ink">{stop.address_line}</p>
        {stop.address_meta ? (
          <p className="selectable text-ink-soft">{stop.address_meta}</p>
        ) : null}
        {/* Who is expecting it, with the parcel and the money. The name was
            inside the call button and had to be truncated to fit the number
            beside it — "Muha…" over a door buzzer is worse than useless, and
            the button's job is the number. */}
        <p className="text-[length:var(--text-small)] text-ink-soft">
          <span className="text-ink">{stop.recipient_name}</span> ·{" "}
          {num(stop.items_count)} {t.items} · {som(stop.total)}
          {stop.delivery_window ? ` · ${stop.delivery_window}` : ""}
        </p>

        {/* One thing, undiminishable: the number never truncates, because a
            half-dialled number cannot be dialled. */}
        <Button asChild variant="outline" size="lg" block>
          <a href={`tel:${stop.recipient_phone}`}>
            <Phone />
            <span className="tabular">{stop.recipient_phone}</span>
          </a>
        </Button>

        {stop.attempts > 0 ? (
          <p className="rounded-[var(--radius-control)] bg-danger-soft px-3 py-2 text-[length:var(--text-small)] text-danger">
            {num(stop.attempts)} {t.attempts}
            {stop.last_failure ? ` · ${t.lastFailure}: ${stop.last_failure}` : ""}
          </p>
        ) : null}
      </section>

      {failing ? (
        <section className="space-y-3 rounded-[var(--radius-panel)] border border-danger/40 bg-danger-soft px-4 py-4">
          <Label htmlFor="reason">{t.failedReason}</Label>
          <Textarea
            id="reason"
            rows={3}
            autoFocus
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Eshikni ochmadi"
          />
          <Hint>{t.reasonRequired}</Hint>
          <Button
            variant="danger"
            size="lg"
            block
            disabled={!reason.trim() || failed.isPending}
            onClick={() => failed.mutate()}
          >
            <X />
            {t.failed}
          </Button>
          <Button variant="ghost" size="lg" block onClick={() => setFailing(false)}>
            {t.today}
          </Button>
        </section>
      ) : (
        <section className="space-y-3 rounded-[var(--radius-panel)] border border-line bg-surface px-4 py-4">
          <div className="space-y-1.5">
            <Label htmlFor="recipient">{t.recipient}</Label>
            <Input
              id="recipient"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Aziz Toshmatov"
              autoComplete="off"
            />
            <Hint>{t.recipientHint}</Hint>
          </div>

          {stop.cash_due > 0 ? (
            <div className="space-y-1.5">
              <Label htmlFor="cash">{t.cash}</Label>
              <Input
                id="cash"
                inputMode="numeric"
                className="tabular"
                value={cash}
                onChange={(event) => setCash(event.target.value.replace(/\D/g, ""))}
              />
              <Hint>{t.cashMustMatch}</Hint>
            </div>
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor="photo">{t.photo}</Label>
            <label
              className="flex items-center justify-center gap-2 rounded-[var(--radius-control)]
                         border border-dashed border-line px-4 py-4 text-ink-soft
                         active:bg-line-soft"
            >
              <Camera className="size-5" />
              {uploading ? "…" : photo ? "✓" : t.addPhoto}
              <input
                id="photo"
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(event) => void pick(event.target.files)}
              />
            </label>
            {uploadError ? (
              <p role="alert" className="text-[length:var(--text-small)] font-medium text-danger">
                {uploadError}
              </p>
            ) : (
              <Hint>{t.photoOptional}</Hint>
            )}
          </div>

          <Button
            variant="good"
            size="lg"
            block
            disabled={!name.trim() || deliver.isPending}
            onClick={() => deliver.mutate()}
          >
            <Check />
            {t.delivered}
          </Button>
          <Button variant="quiet" size="lg" block onClick={() => setFailing(true)}>
            <X />
            {t.failed}
          </Button>
        </section>
      )}
    </div>
  )
}
