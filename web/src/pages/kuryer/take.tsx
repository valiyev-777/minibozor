/**
 * 2b — Yukni olish. The courier picks what they can carry.
 *
 * **No scanner, and that is the design's own note.** The board is a list of
 * parcels the warehouse has finished packing; the courier ticks the ones they
 * are taking and the total is computed from the ticks. Scanning each parcel
 * would be a second confirmation of a fact the warehouse already stated, done
 * standing up with a phone in one hand and a box in the other.
 *
 * ------------------------------------------------------- one write per parcel
 *
 * `POST /courier/orders/{id}/take` claims one order, and there is no bulk
 * door. So a selection of four is four writes, sent **in sequence** rather
 * than at once: the endpoint's whole job is to settle two couriers reaching
 * for the same parcel, and four parallel claims against a phone on bad signal
 * is four chances to half-fail with nothing to tell the person about. In
 * sequence, a refusal stops the run at the parcel that was refused, and the
 * screen says which one somebody else got — the list behind it has already
 * refreshed, so the tick is simply gone.
 *
 * Each carries its own idempotency key, so a retry replays rather than
 * claiming twice.
 *
 * ----------------------------------------------------------------- departures
 *
 * The artboard's chips — `Sovutgichda`, `Og'ir · 12 kg`, `Mo'rt · ehtiyot` —
 * are handling notes, and nothing on an order records them. The chips are kept
 * and filled with what the courier's door does carry: the delivery note left
 * on the address (`address_meta`, which is the floor and the entry code), and
 * a warning when a door has already been tried. Both change how somebody picks
 * their load, which is what a chip on this screen is for.
 */

import { Check, PackageSearch } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import {
  Chip,
  Glass,
  Loading,
  Notice,
  Nothing,
  Page,
  Refusal,
  Title,
} from "@/components/kuryer/bits"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import { useAvailableOrders, useTakeOrder } from "@/lib/queries"
import type { CourierOrder } from "@/lib/types"

export function KuryerTake() {
  const go = useNavigate()
  const board = useAvailableOrders()
  const take = useTakeOrder()
  const [picked, setPicked] = useState<number[]>([])
  const [refused, setRefused] = useState<unknown>(null)

  const waiting = board.data ?? []
  const chosen = waiting.filter((one) => picked.includes(one.id))
  const pieces = chosen.reduce((sum, one) => sum + one.items_count, 0)
  const cash = chosen.reduce((sum, one) => sum + one.cash_due, 0)

  const toggle = (id: number) =>
    setPicked((was) =>
      was.includes(id) ? was.filter((one) => one !== id) : [...was, id],
    )

  async function claim() {
    setRefused(null)
    for (const order of chosen) {
      try {
        await take.mutateAsync(order.id)
        setPicked((was) => was.filter((one) => one !== order.id))
      } catch (problem) {
        // Stopped at the one that was refused rather than carrying on: the
        // rest are still on the board and still tickable, and a run that
        // limps past a 409 leaves somebody guessing which parcels they got.
        setRefused(problem)
        return
      }
    }
    go("/kuryer/marshrut")
  }

  return (
    /* The extra foot is the pinned summary below — see it. */
    <Page className="pb-[calc(var(--kuryer-tabs)+6.5rem)]">
      <Title
        over={`Ombor · ${groups(waiting.length)} ta tayyor`}
        lede="Qanchasini ko'tarsangiz — o'shanchasini belgilang. Qolgani boshqa kuryerga qoladi."
      >
        Yukni tanlash
      </Title>

      <Refusal error={refused ?? board.error} />
      {board.isLoading ? <Loading what="Ombor navbati" /> : null}

      {waiting.length ? (
        <div className="flex gap-2.5">
          <button
            type="button"
            onClick={() => setPicked(waiting.map((one) => one.id))}
            className="kuryer-glass h-control-sm flex-1 rounded-nub text-small font-semibold text-kuryer-act-deep"
          >
            Hammasini olaman
          </button>
          <button
            type="button"
            onClick={() => setPicked([])}
            className="kuryer-glass h-control-sm flex-1 rounded-nub text-small font-semibold text-kuryer-ink-soft"
          >
            Tozalash
          </button>
        </div>
      ) : null}

      {!board.isLoading && !waiting.length ? (
        <Nothing
          icon={PackageSearch}
          title="Tayyor buyurtma yo'q"
          what="Ombor yig'ib bo'lgach shu yerda ko'rinadi."
        />
      ) : null}

      <div className="flex flex-col gap-2.5">
        {waiting.map((order) => (
          <Parcel
            key={order.id}
            order={order}
            on={picked.includes(order.id)}
            onToggle={() => toggle(order.id)}
          />
        ))}
      </div>

      {cash ? (
        <Notice title={`Naqd yig'iladi: ${money(cash)}`}>
          Qaytim uchun mayda pulni oldindan oling
        </Notice>
      ) : chosen.length ? (
        <Notice tone="act" title="Tanlanganlar orasida naqd to'lov yo'q">
          Hammasi onlayn to'langan — eshikda pul olinmaydi
        </Notice>
      ) : null}

      {/* -------------------------------------------------- the running total
          Pinned above the tab bar rather than scrolling with the list: what is
          selected and what it comes to has to be readable while the ticking is
          happening, and a summary that scrolls away is a summary somebody
          scrolls back for. `fixed` against the shell, which is the viewport —
          and the `Page` is given the extra padding so the last parcel in the
          list is not underneath it. */}
      <Glass strong className="fixed inset-x-4 bottom-[calc(var(--kuryer-tabs)+0.5rem)] z-[800] mx-auto flex max-w-[26rem] items-center gap-3 rounded-tile shadow-kuryer-float">
        <div className="min-w-0 flex-1">
          <p className="text-body font-bold tabular text-kuryer-ink">
            {chosen.length
              ? `${groups(chosen.length)} buyurtma · ${groups(pieces)} dona`
              : "Hech narsa tanlanmadi"}
          </p>
          <p className="text-micro tabular text-kuryer-ink-soft">
            {chosen.length
              ? cash
                ? `naqd ${money(cash)}`
                : "naqd olinmaydi"
              : "Kamida bittasini belgilang"}
          </p>
        </div>
        <button
          type="button"
          disabled={!chosen.length || take.isPending}
          onClick={claim}
          className={cn(
            "h-control-sm shrink-0 rounded-nub px-4 text-small font-semibold transition-colors",
            !chosen.length || take.isPending
              ? "bg-kuryer-quiet text-kuryer-ink-faint"
              : "bg-kuryer-act text-kuryer-act-ink shadow-kuryer-act",
          )}
        >
          {take.isPending
            ? "Olinmoqda…"
            : chosen.length
              ? `Olaman · ${groups(chosen.length)}`
              : "Tanlang"}
        </button>
      </Glass>
    </Page>
  )
}

/** One parcel on the board, and whether it is coming. The whole card is the
 *  target — a 28px tick box is not something a thumb hits while holding a box,
 *  and the box is drawn as the state rather than as the control. */
function Parcel({
  order,
  on,
  onToggle,
}: {
  order: CourierOrder
  on: boolean
  onToggle: () => void
}) {
  const chips: Array<{ text: string; tone: "quiet" | "halt" }> = []
  if (order.address_meta) chips.push({ text: order.address_meta, tone: "quiet" })
  if (order.attempts) {
    chips.push({
      text: `${groups(order.attempts)} marta urinilgan`,
      tone: "halt",
    })
  }

  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onToggle}
      className={cn(
        "flex w-full gap-3 rounded-tile p-3.5 text-left transition-colors",
        on
          ? "border-[1.5px] border-kuryer-act-edge bg-kuryer-act-soft shadow-kuryer-float"
          : "border-[0.5px] border-kuryer-hair bg-kuryer-card shadow-kuryer-card",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "mt-0.5 grid size-7 shrink-0 place-items-center rounded-[9px] transition-colors",
          on
            ? "bg-kuryer-act text-kuryer-act-ink"
            : "border-[1.5px] border-kuryer-grab bg-transparent",
        )}
      >
        {on ? <Check className="size-4" strokeWidth={3} /> : null}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-baseline justify-between gap-2.5">
          <span className="caption font-bold text-kuryer-ink-soft">{order.code}</span>
          <Chip tone={order.cash_due ? "cash" : "act"}>
            {order.cash_due ? "Naqd" : "Onlayn"}
          </Chip>
        </span>
        {/* Wraps rather than ellipsises. An address cut at the width of a
            phone is an address somebody has to open the stop to read. */}
        <span className="mt-1 block text-body font-semibold text-kuryer-ink [overflow-wrap:anywhere]">
          {order.address_line || "Manzil ko'rsatilmagan"}
        </span>
        <span className="block text-small tabular text-kuryer-ink-soft">
          {groups(order.items_count)} dona · {money(order.total)}
        </span>
        {chips.length ? (
          <span className="mt-2 flex flex-wrap gap-1.5">
            {chips.map((chip) => (
              <Chip key={chip.text} tone={chip.tone}>
                {chip.text}
              </Chip>
            ))}
          </span>
        ) : null}
      </span>
    </button>
  )
}
