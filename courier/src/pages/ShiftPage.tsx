import * as React from "react"
import { toast } from "sonner"
import { Button, Empty, Field, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { cash as cashView, shiftState } from "@/offline/derive"
import { pendingFor } from "@/offline/outbox"
import { useCourier } from "@/auth/session"
import { grouped, signedSum, stamp, sum } from "@/lib/format"

/**
 * The round, and the money that came back from it.
 *
 * Three cash figures, kept apart because they are three separate claims and
 * the whole value is in where they differ: what the doors add up to (ours),
 * what the courier says they are handing over (theirs), and what the office
 * counts later. This screen shows the first two and never quietly reconciles
 * them — a difference is a fact to record, not an argument to win, and a
 * courier who is told their figure is "wrong" and cannot submit it has been
 * given no way to be honest about a shortfall.
 *
 * The expected figure includes cash from deliveries still sitting in the queue.
 * That money is in the courier's pocket whether or not the server has heard
 * about it, and showing only the confirmed figure would ask them to hand over
 * less than they are holding.
 */
export function ShiftPage() {
  const courier = useCourier()
  const { shift, rows, record, reachable, refresh } = useOffline()
  const state = shiftState(shift.data, rows)
  const money = cashView(shift.data, rows)

  const [declared, setDeclared] = React.useState("")
  const [note, setNote] = React.useState("")
  const [busy, setBusy] = React.useState(false)
  const [closing, setClosing] = React.useState(false)

  // Pre-filled with what we expect, so the common case — the money is right —
  // is one tap rather than eight digits typed on a doorstep.
  React.useEffect(() => {
    if (closing) setDeclared(String(money.total))
  }, [closing, money.total])

  const declaredNumber = Number(declared.replace(/\D/g, "") || 0)
  const difference = declaredNumber - money.total
  const queueWaiting = rows.filter((row) => !row.blocked).length

  async function openShift() {
    if (pendingFor(rows, "shift-open", 0)) {
      toast.error("Smena ochish allaqachon navbatda.")
      return
    }
    setBusy(true)
    try {
      // The endpoint takes no body; the key is the whole request. An empty
      // object is what its `digest(None)` hashes against consistently.
      await record({ kind: "shift-open", targetId: 0, body: {}, label: "Smena ochish" })
    } finally {
      setBusy(false)
    }
  }

  async function closeShift(event: React.FormEvent) {
    event.preventDefault()
    const id = shift.data?.id ?? 0
    if (pendingFor(rows, "shift-close", id)) {
      toast.error("Smenani yopish allaqachon navbatda.")
      return
    }
    setBusy(true)
    try {
      await record({
        kind: "shift-close",
        // Zero when the shift itself has not reached the server yet: the path
        // is resolved at send time, after the open lands. The body — which is
        // what the key is issued against — does not change.
        targetId: id,
        body: { cash_declared: declaredNumber, note: note.trim() },
        label: "Smenani yopish",
      })
      setClosing(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4 pb-safe">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-3xl font-bold">Smena</h1>
        <span className="text-base text-muted">{courier.full_name || courier.phone}</span>
      </div>

      {state === "none" || state === "closed" ? (
        <>
          <Panel>
            <p className="text-xl font-bold">
              {state === "closed" ? "Smena yopilgan" : "Smena ochilmagan"}
            </p>
            <p className="mt-1 text-base text-muted">
              Yetkazishni belgilash uchun smena ochiq bo'lishi shart — naqd pul shu smenaga
              yoziladi.
            </p>
          </Panel>
          {state === "closed" && shift.data ? <ClosedSummary shift={shift.data} /> : null}
          <Button onClick={() => void openShift()} busy={busy}>
            Smenani ochish
          </Button>
        </>
      ) : null}

      {state === "opening" ? (
        <Panel tone="pending">
          <p className="text-xl font-bold text-pending">Smena ochilmoqda · yuborilmagan</p>
          <p className="mt-1 text-base">
            Telefoningizda saqlandi. Yetkazishlarni hozircha belgilayverishingiz mumkin — ular ham
            navbatda turadi va smenadan keyin yuboriladi.
          </p>
        </Panel>
      ) : null}

      {state === "closing" ? (
        <Panel tone="pending">
          <p className="text-xl font-bold text-pending">Smena yopilmoqda · yuborilmagan</p>
          <p className="mt-1 text-base">
            Topshirilayotgan summa telefoningizda saqlandi va tarmoq qaytganda yuboriladi.
          </p>
        </Panel>
      ) : null}

      {state === "open" || state === "opening" || state === "closing" ? (
        <>
          <Panel tone="cash">
            <p className="text-lg font-semibold text-muted">Kutilgan summa</p>
            <p className="text-5xl font-bold tabular-nums">{sum(money.total)}</p>
            <p className="mt-1 text-base text-muted">Yetkazilgan naqd buyurtmalar yig'indisi.</p>
            {money.unsent > 0 ? (
              <p className="mt-2 text-base font-semibold text-pending">
                Shundan {grouped(money.unsent)} so'm hali yuborilmagan amallardan.
              </p>
            ) : null}
          </Panel>

          {shift.data ? (
            <div className="grid grid-cols-2 gap-3">
              <Panel>
                <p className="text-base text-muted">Yetkazilgan</p>
                <p className="text-3xl font-bold">{shift.data.orders_delivered}</p>
              </Panel>
              <Panel>
                <p className="text-base text-muted">Muvaffaqiyatsiz</p>
                <p className="text-3xl font-bold">{shift.data.orders_failed}</p>
              </Panel>
            </div>
          ) : null}

          {shift.data?.opened_at ? (
            <p className="text-base text-muted">Ochilgan: {stamp(shift.data.opened_at)}</p>
          ) : null}

          {state !== "closing" ? (
            !closing ? (
              <Button tone="ghost" onClick={() => setClosing(true)}>
                Smenani yopish
              </Button>
            ) : (
              <form onSubmit={closeShift} className="space-y-4">
                <h2 className="text-2xl font-bold">Smenani yopish</h2>

                {queueWaiting > 0 ? (
                  <Panel tone="pending">
                    <p className="text-base">
                      Navbatda {queueWaiting} ta yuborilmagan amal bor. Ular yuborilgach kutilgan
                      summa oshishi mumkin — iloji bo'lsa avval navbatni yuboring.
                    </p>
                  </Panel>
                ) : null}

                <Field
                  label="Topshirilayotgan summa"
                  inputMode="numeric"
                  value={declared}
                  onChange={(e) => setDeclared(e.target.value.replace(/\D/g, ""))}
                  hint="Siz topshirayotgan pul. Kassa keyin sanaydi."
                />

                <Panel tone={difference === 0 ? "good" : "pending"}>
                  {difference === 0 ? (
                    <p className="text-lg font-bold text-good">Summalar to'g'ri keldi.</p>
                  ) : (
                    <>
                      <p className="text-lg font-bold text-pending">
                        Farq: {signedSum(difference)}
                      </p>
                      <p className="mt-1 text-base">
                        {difference < 0
                          ? "Kutilganidan kam. Farq yashirilmaydi — izoh bilan yoziladi."
                          : "Kutilganidan ortiq. Farq yashirilmaydi — izoh bilan yoziladi."}
                      </p>
                    </>
                  )}
                </Panel>

                <Field
                  label="Izoh (ixtiyoriy)"
                  value={note}
                  maxLength={200}
                  onChange={(e) => setNote(e.target.value)}
                />

                <Button type="submit" busy={busy}>
                  Smenani yopish
                </Button>
                <Button type="button" tone="ghost" onClick={() => setClosing(false)}>
                  Bekor qilish
                </Button>
              </form>
            )
          ) : null}
        </>
      ) : null}

      {shift.data && shift.data.attempts.length > 0 ? (
        <>
          <h2 className="pt-2 text-xl font-bold text-muted">Shu smenadagi urinishlar</h2>
          <ul className="space-y-2">
            {shift.data.attempts
              .slice()
              .reverse()
              .map((attempt) => (
                <li key={attempt.id}>
                  <Panel>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{attempt.order_code}</span>
                      <Pill tone={attempt.result === "delivered" ? "good" : "bad"}>
                        {attempt.result === "delivered" ? "Yetkazildi" : "Urinish"}
                      </Pill>
                    </div>
                    <p className="mt-1 text-base text-muted">
                      {stamp(attempt.happened_at)}
                      {attempt.recipient_name ? ` · ${attempt.recipient_name}` : ""}
                      {attempt.reason ? ` · ${attempt.reason}` : ""}
                    </p>
                    {attempt.cash_collected > 0 ? (
                      <p className="text-lg font-semibold">{sum(attempt.cash_collected)}</p>
                    ) : null}
                  </Panel>
                </li>
              ))}
          </ul>
        </>
      ) : null}

      {!reachable ? (
        <p className="text-center text-base text-muted">
          Oflayn ko'rinish. <button onClick={() => void refresh()} className="underline">Yangilash</button>
        </p>
      ) : null}
    </div>
  )
}

function ClosedSummary({ shift }: { shift: NonNullable<ReturnType<typeof useOffline>["shift"]["data"]> }) {
  if (!shift) return <Empty>Yopilgan smena topilmadi.</Empty>
  return (
    <Panel>
      <p className="text-base text-muted">Oxirgi smena</p>
      <div className="mt-1 space-y-1 text-lg">
        <p>Kutilgan: {sum(shift.cash_expected)}</p>
        {shift.cash_declared !== null && shift.cash_declared !== undefined ? (
          <p>Topshirilgan: {sum(shift.cash_declared)}</p>
        ) : null}
        {/* Null until somebody at a desk has counted. A nought here would be a
            claim nobody has made. */}
        {shift.cash_counted !== null && shift.cash_counted !== undefined ? (
          <p>
            Kassa sanagan: {sum(shift.cash_counted)}
            {shift.difference !== null && shift.difference !== undefined
              ? ` · farq ${signedSum(shift.difference)}`
              : ""}
          </p>
        ) : (
          <p className="text-muted">Kassa hali sanamagan.</p>
        )}
      </div>
    </Panel>
  )
}
