import * as React from "react"
import { useNavigate, useParams } from "react-router-dom"
import { toast } from "sonner"
import { ArrowLeft } from "lucide-react"
import clsx from "clsx"
import { Button, Empty, Field, Panel } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { stops } from "@/offline/derive"
import { pendingFor } from "@/offline/outbox"

/**
 * A door that did not open.
 *
 * The screen exists to record one sentence and to prevent one misunderstanding.
 *
 * The sentence is the reason, and it is required, because it is what an
 * operator decides from: phone the customer, send the van tomorrow, or give up.
 * "Not delivered" with nothing after it is a row nobody can act on.
 *
 * The misunderstanding is that this cancels something. It does not, and the
 * server has no way for a courier to cancel anything — that decision belongs
 * to somebody who can see three failed attempts and ring the customer. The
 * order stays shipped, stays on this round, and can be tried again. Saying so
 * in a panel at the top costs a few lines and stops a courier from taking a
 * parcel back to the depot because they thought the app had closed the job.
 */
const REASONS = [
  "Telefonni ko'tarmadi",
  "Uyda yo'q",
  "Manzil noto'g'ri",
  "Mijoz rad etdi",
  "Naqd pul yetmadi",
  "Kirish mumkin emas",
]

export function FailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { orders, rows, record, reachable } = useOffline()

  const orderId = Number(id)
  const stop = stops(orders.data, rows).find((s) => s.order.id === orderId)

  const [reason, setReason] = React.useState("")
  const [custom, setCustom] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  if (!stop) return <Empty>Bu buyurtma ro'yxatda yo'q. Reysni yangilang.</Empty>
  const { order } = stop

  const chosen = (custom.trim() || reason).trim()

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!chosen) {
      setError("Sababni tanlang yoki yozing — operator shu jumlaga qarab qaror qiladi.")
      return
    }
    if (pendingFor(rows, "failed", order.id)) {
      toast.error("Bu urinish allaqachon navbatda turibdi.")
      navigate(`/order/${order.id}`, { replace: true })
      return
    }
    setBusy(true)
    try {
      await record({
        kind: "failed",
        targetId: order.id,
        body: { reason: chosen, photo_url: "" },
        label: `${order.code} · Urinish`,
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
        className="flex items-center gap-2 text-lg font-semibold text-ink-soft"
      >
        <ArrowLeft className="size-6" />
        {order.code}
      </button>

      <h1 className="text-3xl font-bold">Urinish muvaffaqiyatsiz</h1>

      <Panel tone="pending">
        <p className="text-xl font-bold text-warn">Buyurtma sizda qoladi</p>
        <p className="mt-1 text-base">
          Bu — bekor qilish emas. Buyurtma bekor bo'lmaydi va boshqa kuryerga o'tmaydi: u sizda,
          reysingizda qoladi va yana urinib ko'rish mumkin. Bekor qilish yoki qaytarish haqidagi
          qarorni operator qabul qiladi.
        </p>
      </Panel>

      <div>
        <p className="mb-2 text-base font-semibold text-ink-soft">Sabab</p>
        <div className="grid grid-cols-2 gap-2">
          {REASONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                setReason(option === reason ? "" : option)
                setCustom("")
                setError(null)
              }}
              className={clsx(
                "min-h-16 rounded-[var(--radius-panel)] border-2 px-3 py-2 text-lg font-semibold",
                reason === option ? "border-brand bg-brand text-brand-ink" : "border-line",
              )}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <Field
        label="Yoki o'zingiz yozing"
        value={custom}
        maxLength={200}
        onChange={(e) => {
          setCustom(e.target.value)
          if (e.target.value) setReason("")
          setError(null)
        }}
        error={error}
      />

      <Button type="submit" tone="bad" busy={busy}>
        Urinishni yozish
      </Button>
      {!reachable ? (
        <p className="text-center text-base text-warn">
          Tarmoq yo'q — telefoningizda saqlanadi va o'zi yuboriladi.
        </p>
      ) : null}
    </form>
  )
}
