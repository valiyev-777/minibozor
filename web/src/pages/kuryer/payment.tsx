/**
 * 2f — To'lov. The money at the door, and the one write the whole flow exists
 * for.
 *
 * ------------------------------------------------------- the figure is not typed
 *
 * **The change is computed here; the amount owed is what gets sent.** The
 * server refuses a delivery whose `cash_collected` does not equal what it
 * worked out is due, and it is right to: a courier who mistypes the figure is
 * short at the end of the day with nothing to point at, and a mismatch is far
 * more likely to be a slip than a part payment anybody wants recorded. So the
 * box on this screen asks what the **customer handed over** — a number that
 * only ever leaves the phone as arithmetic — and the delivery carries
 * `cash_due` exactly as the server stated it.
 *
 * ------------------------------------------------------- a card order owes nothing
 *
 * `cash_due` is nought on an order already paid by card, and this screen
 * honours that rather than showing a sum with a zero in it: the payment tiles
 * lock to `Onlayn`, the change box does not appear, and the action says
 * `Yakunlash`. Asking a customer who has already paid for money again is the
 * mistake `cash_due` exists to prevent, and a screen that draws a big `0` over
 * the word `OLINADIGAN SUMMA` invites exactly it.
 *
 * ----------------------------------------------------------------- departures
 *
 * The artboard's cash card carries a limit — `612 000` against `Limit
 * 800 000`, with a fill bar. **There is no limit anywhere in this system**,
 * and no policy that produces one. The card keeps the figure, which is real
 * (`GET /courier/earnings` → `cash_on_hand`), drops the invented ceiling and
 * the bar, and links to the screen where the money is actually handed in.
 *
 * `Onlayn` is shown and not offered. Taking a card payment at the door would
 * be a payment flow — a processor, a callback, a reconciliation — and none of
 * it exists; the tile says what the order already is rather than pretending to
 * be a choice the courier gets to make.
 */

import { Banknote, CreditCard } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import {
  Cap,
  Glass,
  Loading,
  Notice,
  Page,
  Refusal,
  Slab,
  Sum,
  Tile,
  Title,
} from "@/components/kuryer/bits"
import { recipientOf } from "@/pages/kuryer/confirm"
import { useDraft } from "@/components/kuryer/shell"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import { useDeliver, useEarnings, useMyRound } from "@/lib/queries"

export function KuryerPayment() {
  const { id } = useParams()
  const go = useNavigate()
  const orderId = Number(id)
  const round = useMyRound()
  const earnings = useEarnings()
  const stop = (round.data ?? []).find((one) => one.id === orderId)
  const deliver = useDeliver(orderId)
  const { draft, set, clear } = useDraft()

  if (round.isLoading) {
    return (
      <div className="grid h-full place-items-center bg-kuryer-ground">
        <Loading what="Bekat" />
      </div>
    )
  }

  if (!stop) {
    return (
      <Page>
        <Notice tone="halt" title="Bu bekat marshrutda yo'q">
          Yetkazilgan yoki boshqa kuryerga o'tgan bo'lishi mumkin.
        </Notice>
        <Slab onClick={() => go("/kuryer/marshrut")}>Marshrutga qaytish</Slab>
      </Page>
    )
  }

  const mine = draft && draft.orderId === stop.id ? draft : null
  const owed = stop.cash_due
  const cash = owed > 0

  // Nothing but arithmetic, and it never leaves the phone.
  const given = Number(mine?.given ?? "") || 0
  const change = given - owed

  // The name is required by the server, and the whole flow is three screens —
  // somebody who deep-linked here has not filled it in.
  const name = recipientOf(mine?.who ?? 0, mine?.recipientName ?? stop.recipient_name)
  // Typing what the customer handed over is **optional**: an exact payment is
  // the ordinary case and there is no change to work out. Only a figure that
  // is short blocks the write — that is somebody saying "they gave me less",
  // which the server would refuse anyway, and saying so here is kinder than a
  // round trip to find out.
  const short = given > 0 && given < owed
  const ready = Boolean(name.trim()) && !(cash && short)

  return (
    <Page>
      <Title over={`Buyurtma ${stop.code}`}>To'lov</Title>

      <Glass className="rounded-glass p-5">
        <Cap>{cash ? "Olinadigan summa" : "To'langan summa"}</Cap>
        <div className="mt-2">
          <Sum value={groups(cash ? owed : stop.total)} tone={cash ? "ink" : "done"} />
        </div>
        <p className="mt-1 text-small tabular text-kuryer-ink-soft">
          {groups(stop.items_count)} dona ·{" "}
          {cash ? "eshikda naqd olinadi" : "onlayn to'langan, eshikda pul olinmaydi"}
        </p>

        <div className="mt-4 flex gap-2.5">
          <Method on={cash} icon={Banknote} label="Naqd" note={cash ? "eshikda" : "—"} />
          <Method
            on={!cash}
            icon={CreditCard}
            label="Onlayn"
            note={cash ? "—" : "to'langan"}
          />
        </div>

        {/* The change, which is the only reason this box exists. */}
        {cash ? (
          <div className="mt-4 rounded-slab bg-kuryer-quiet p-3.5">
            <label className="flex items-baseline justify-between gap-3">
              <span className="text-small text-kuryer-ink-soft">Mijoz beradi</span>
              <input
                value={mine?.given ?? ""}
                onChange={(event) =>
                  set({ given: event.target.value.replace(/\D/g, "") })
                }
                inputMode="numeric"
                aria-label="Mijoz bergan summa"
                placeholder={groups(owed)}
                className="h-control-sm w-36 rounded-nub border-[0.5px] border-kuryer-hair bg-kuryer-card px-3 text-right text-body font-semibold tabular text-kuryer-ink outline-none placeholder:font-normal placeholder:text-kuryer-ink-faint focus:ring-2 focus:ring-kuryer-act-edge"
              />
            </label>
            <div className="mt-3 flex items-baseline justify-between gap-3">
              <span className="text-small text-kuryer-ink-soft">Qaytim</span>
              <span
                className={cn(
                  "text-body font-bold tabular",
                  short ? "text-kuryer-halt-ink" : "text-kuryer-cash-ink",
                )}
              >
                {given ? groups(change) : "—"}
              </span>
            </div>
            {short ? (
              <p className="mt-2 text-micro text-kuryer-halt-ink">
                Yetmayapti — {money(-change)} kam
              </p>
            ) : null}
          </div>
        ) : null}
      </Glass>

      {/* ------------------------------------------------------ what is in the bag */}
      <Tile>
        <Cap>Qo'ldagi naqd</Cap>
        <p className="mt-2 text-kuryer-title font-bold tabular text-kuryer-ink [overflow-wrap:anywhere]">
          {earnings.data ? money(earnings.data.cash_on_hand) : "…"}
        </p>
        <p className="mt-1 text-micro text-kuryer-ink-soft">
          Ombor kassasiga topshiriladi — Profil bo'limida
        </p>
      </Tile>

      {!name.trim() ? (
        <Notice tone="halt" title="Kim qabul qilgani yozilmagan">
          Tasdiqlash ekraniga qaytib ismni yozing — serversiz yakunlab bo'lmaydi.
        </Notice>
      ) : null}

      <Refusal error={deliver.error} />

      <Slab
        tone="done"
        disabled={!ready || deliver.isPending}
        onClick={() =>
          deliver.mutate(
            {
              recipient_name: name,
              // What the server says is owed, not what was typed above. The
              // typed figure was only ever for the change sum.
              cash_collected: owed,
              photo_url: mine?.photoUrl || undefined,
            },
            {
              onSuccess: () => {
                clear()
                go("/kuryer/marshrut")
              },
            },
          )
        }
      >
        {deliver.isPending
          ? "Yakunlanmoqda…"
          : cash
            ? "Naqd olindi — yakunlash"
            : "Yetkazildi — yakunlash"}
      </Slab>

      <p className="text-center text-micro text-kuryer-ink-faint">
        {cash
          ? `Serverga ${money(owed)} yoziladi — qaytim faqat hisob-kitob uchun`
          : "Bu buyurtma allaqachon to'langan"}
      </p>
    </Page>
  )
}

/** One of the two payment tiles. Not a control: it states what the order is.
 *  Drawn as a pair because "cash or card" is the first thing a courier checks
 *  at a door, and one tile alone does not answer "as opposed to what". */
function Method({
  on,
  icon: Icon,
  label,
  note,
}: {
  on: boolean
  icon: typeof Banknote
  label: string
  note: string
}) {
  return (
    <div
      className={cn(
        "min-w-0 flex-1 rounded-slab p-3.5",
        on
          ? "border-[1.5px] border-kuryer-done-edge bg-kuryer-done-soft"
          : "border-[0.5px] border-kuryer-hair bg-kuryer-quiet",
      )}
    >
      <Icon
        className={cn("size-6", on ? "text-kuryer-done-deep" : "text-kuryer-ink-faint")}
      />
      <p
        className={cn(
          "mt-2 text-small font-semibold",
          on ? "text-kuryer-done-deep" : "text-kuryer-ink-soft",
        )}
      >
        {label}
      </p>
      <p className="text-micro tabular text-kuryer-ink-soft">{note}</p>
    </div>
  )
}
