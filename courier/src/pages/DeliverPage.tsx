import * as React from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { ArrowLeft, Camera, X } from "lucide-react"
import { ApiError, uploadMedia } from "@/api/client"
import { Button, Empty, Field, Panel } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { canDeliver, shiftState, stops } from "@/offline/derive"
import { pendingFor } from "@/offline/outbox"
import { sum } from "@/lib/format"

/**
 * Handing the goods over.
 *
 * Two fields and a confirmation, in the order they happen at the door.
 *
 * **The name is required** because the server requires it — an empty one is a
 * 422 — and the server requires it because it is the one field a courier can
 * always fill in while standing in front of the person who took the parcel,
 * and it is what answers "I never received it" three weeks later.
 *
 * **The photo is optional** and is only offered when there is signal. It needs
 * an upload, an upload needs a network, and requiring one would strand a
 * courier in a basement who has already handed over the goods.
 *
 * **The cash is not typed.** The server refuses any figure that is not exactly
 * what is owed, so a keypad here would only produce typos that get refused
 * hours later from inside a queue. What the courier confirms is that they took
 * the amount on the screen.
 */
export function DeliverPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { orders, shift, rows, record, reachable } = useOffline()

  const orderId = Number(id)
  const stop = stops(orders.data, rows).find((s) => s.order.id === orderId)

  const [name, setName] = React.useState("")
  const [note, setNote] = React.useState("")
  const [photo, setPhoto] = React.useState<{ url: string; name: string } | null>(null)
  const [uploading, setUploading] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [took, setTook] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const fileInput = React.useRef<HTMLInputElement>(null)

  if (!stop) return <Empty>Bu buyurtma ro'yxatda yo'q. Reysni yangilang.</Empty>
  const { order } = stop

  const already = pendingFor(rows, "deliver", order.id)
  const state = shiftState(shift.data, rows)
  const cashDue = order.cash_due
  const needsCash = cashDue > 0

  async function pickPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    setUploading(true)
    try {
      const media = await uploadMedia(file)
      setPhoto({ url: media.media_url, name: file.name })
    } catch (e) {
      toast.error(
        e instanceof ApiError && e.isOffline
          ? "Tarmoq yo'q — surat yuborilmadi. Ism yetarli, shusiz davom eting."
          : e instanceof ApiError
            ? e.message
            : "Surat yuborilmadi.",
      )
    } finally {
      setUploading(false)
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim()) {
      setError("Ism majburiy — kim qabul qilganini yozing.")
      return
    }
    if (needsCash && !took) {
      setError("Naqd pul olinganini tasdiqlang.")
      return
    }
    if (already) {
      toast.error("Bu buyurtma allaqachon navbatda turibdi.")
      navigate(`/order/${order.id}`, { replace: true })
      return
    }
    if (!canDeliver(state)) {
      setError("Smena ochilmagan.")
      return
    }

    setBusy(true)
    try {
      await record({
        kind: "deliver",
        targetId: order.id,
        // The exact shape of `DeliverIn`. Encoded once, here, and sent
        // unchanged however many times it takes to land.
        body: {
          recipient_name: name.trim(),
          photo_url: photo?.url ?? "",
          cash_collected: cashDue,
          note: note.trim(),
        },
        label: `${order.code} · Yetkazildi`,
        cash: cashDue,
      })
      navigate("/", { replace: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-xl space-y-4 p-4 pb-safe">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-lg font-semibold text-muted"
      >
        <ArrowLeft className="size-6" />
        {order.code}
      </button>

      <h1 className="text-3xl font-bold">Yetkazildi deb belgilash</h1>

      {needsCash ? (
        <Panel tone="cash">
          <p className="text-lg font-semibold text-muted">Olinadigan naqd pul</p>
          <p className="text-5xl font-bold tabular-nums">{sum(cashDue)}</p>
          <label className="mt-3 flex items-center gap-3 text-lg font-semibold">
            <input
              type="checkbox"
              checked={took}
              onChange={(e) => setTook(e.target.checked)}
              className="size-7 accent-[var(--color-good)]"
            />
            Naqd pul to'liq olindi
          </label>
          <p className="mt-1 text-base text-muted">
            Summa aynan shu bo'lishi kerak — server boshqasini qabul qilmaydi.
          </p>
        </Panel>
      ) : (
        <Panel>
          <p className="text-lg font-semibold text-good">Karta bilan to'langan — pul olinmaydi</p>
        </Panel>
      )}

      <Field
        label="Qabul qiluvchining ismi"
        value={name}
        onChange={(e) => {
          setName(e.target.value)
          setError(null)
        }}
        autoComplete="off"
        hint="Tovarni kim qabul qilgani. «Yetkazilmadi» degan da'voga javob shu ism bo'ladi."
        error={error && !name.trim() ? error : null}
      />

      <div>
        <p className="mb-1.5 text-base font-semibold text-muted">Surat — ixtiyoriy</p>
        {photo ? (
          <Panel tone="good">
            <div className="flex items-center justify-between gap-3">
              <span className="min-w-0 truncate text-lg font-semibold">Surat qo'shildi</span>
              <button
                type="button"
                onClick={() => setPhoto(null)}
                className="flex items-center gap-1 text-lg font-semibold text-bad"
              >
                <X className="size-5" />
                Olib tashlash
              </button>
            </div>
          </Panel>
        ) : reachable ? (
          <>
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              // `environment` opens the back camera straight away on a phone
              // rather than a file browser.
              capture="environment"
              className="hidden"
              onChange={pickPhoto}
            />
            <Button
              type="button"
              tone="ghost"
              busy={uploading}
              onClick={() => fileInput.current?.click()}
            >
              <Camera className="size-6" />
              Surat olish
            </Button>
          </>
        ) : (
          <Panel tone="pending">
            <p className="text-base">
              Tarmoq yo'q — surat yuborib bo'lmaydi. Ism yetarli, yetkazishni shusiz yakunlang.
            </p>
          </Panel>
        )}
      </div>

      <Field
        label="Izoh (ixtiyoriy)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        maxLength={200}
      />

      {error && name.trim() ? (
        <p className="text-lg font-semibold text-bad">{error}</p>
      ) : null}

      <Button type="submit" tone="good" busy={busy}>
        Yetkazildi deb yozish
      </Button>
      {!reachable ? (
        <p className="text-center text-base text-pending">
          Tarmoq yo'q — telefoningizda saqlanadi va o'zi yuboriladi.
        </p>
      ) : null}
    </form>
  )
}
