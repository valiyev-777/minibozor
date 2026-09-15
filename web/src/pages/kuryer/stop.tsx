/**
 * 2d — Bekat tafsiloti. One door, before knocking on it.
 *
 * A short map at the top with the pin on it, then a sheet with everything the
 * courier needs while standing outside: who to ask for, what the entry note
 * says, what the parcel comes to, and whether money changes hands.
 *
 * ----------------------------------------------------------------- departures
 *
 * **The line items are not drawn, because the courier's door does not carry
 * them.** `GET /courier/orders` answers with `items_count` and `total` and
 * nothing else about the contents — deliberately, per its own docstring: "a
 * courier at a door needs the address, the phone, how much cash to ask for and
 * how many times this door has already been tried — and none of the catalogue
 * detail". `GET /orders/{id}` is the customer's own order and a courier is
 * refused it. So where the artboard lists four products, this prints the two
 * figures that exist and says plainly that the contents are sealed. Inventing
 * rows would be worse than the gap; a courier reading a list that does not
 * match the box is a courier arguing on a doorstep.
 *
 * **`MIJOZ IZOHI` is real** and is `address_meta` — the floor, the flat, the
 * entry code and whatever the customer typed. That is exactly the artboard's
 * "Domofon 15K, 4-qavat", so the block is kept as drawn.
 *
 * **`Bo'lmadi` is added.** The artboard has one button and the round has two
 * outcomes: a door that opened and a door that did not. `POST
 * /courier/orders/{id}/failed` records the attempt and leaves the order where
 * it is, and without it the only way to record nobody answering is to not
 * press anything — which loses the fact entirely. It is deliberately quiet
 * next to the blue slab: it is the rarer answer, and it is not a decision to
 * give up, which belongs to the office.
 */

import { ArrowLeft, Phone } from "lucide-react"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { Cap, Chip, Loading, Notice, Refusal, Slab } from "@/components/kuryer/bits"
import { RouteMap, type Trouble } from "@/components/kuryer/map"
import { groups, money } from "@/lib/format"
import { pinned } from "@/lib/geo"
import { useFailed, useMyRound } from "@/lib/queries"

export function KuryerStop() {
  const { id } = useParams()
  const go = useNavigate()
  const round = useMyRound()
  const orderId = Number(id)
  const stop = (round.data ?? []).find((one) => one.id === orderId)
  const failed = useFailed(orderId)
  const [asking, setAsking] = useState(false)
  const [reason, setReason] = useState("")
  const [, setTrouble] = useState<Trouble | null>(null)

  if (round.isLoading) {
    return (
      <div className="grid h-full place-items-center bg-kuryer-ground">
        <Loading what="Bekat" />
      </div>
    )
  }

  if (!stop) {
    return (
      <div className="flex h-full flex-col justify-center gap-4 bg-kuryer-ground px-4">
        <Notice tone="halt" title="Bu bekat marshrutda yo'q">
          Yetkazilgan yoki boshqa kuryerga o'tgan bo'lishi mumkin.
        </Notice>
        <Slab onClick={() => go("/kuryer/marshrut")}>Marshrutga qaytish</Slab>
      </div>
    )
  }

  const point = pinned(stop)

  return (
    <div className="relative h-full overflow-hidden bg-kuryer-ground">
      <RouteMap
        pins={
          point
            ? [{ id: stop.id, n: 1, lat: point.lat, lng: point.lng, state: "now" }]
            : []
        }
        onTrouble={setTrouble}
        className="absolute inset-x-0 top-0 h-[34%]"
      />

      <div className="pointer-events-none absolute inset-x-4 top-0 z-[600] flex items-start justify-between gap-2 pt-[calc(1rem+env(safe-area-inset-top))]">
        <button
          type="button"
          onClick={() => go("/kuryer/marshrut")}
          aria-label="Orqaga"
          className="kuryer-glass pointer-events-auto grid size-11 place-items-center rounded-full text-kuryer-ink shadow-kuryer-float"
        >
          <ArrowLeft className="size-5" />
        </button>
        {stop.recipient_phone ? (
          <a
            href={`tel:${stop.recipient_phone}`}
            aria-label="Mijozga qo'ng'iroq"
            className="kuryer-glass pointer-events-auto grid size-11 place-items-center rounded-full text-kuryer-act shadow-kuryer-float"
          >
            <Phone className="size-5" />
          </a>
        ) : null}
      </div>

      <section className="kuryer-sheet absolute inset-x-0 bottom-0 top-[29%] z-[400] flex flex-col rounded-t-sheet shadow-kuryer-sheet">
        <div className="flex shrink-0 justify-center py-2.5">
          <span aria-hidden className="h-[5px] w-10 rounded-full bg-kuryer-grab" />
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-4 pb-[calc(var(--kuryer-tabs)+1rem)]">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <Cap className="text-kuryer-act-deep">Buyurtma {stop.code}</Cap>
              <p className="mt-1 text-kuryer-title font-bold tracking-tight text-kuryer-ink [overflow-wrap:anywhere]">
                {stop.recipient_name || "Mijoz"}
              </p>
              <p className="mt-0.5 text-small text-kuryer-ink-soft [overflow-wrap:anywhere]">
                {stop.address_line || "Manzil ko'rsatilmagan"}
              </p>
            </div>
            <Chip tone={stop.cash_due ? "cash" : "act"}>
              {stop.cash_due ? "Naqd" : "Onlayn"}
            </Chip>
          </div>

          {/* What is in the box, as far as this door is told. */}
          <div className="overflow-hidden rounded-tile bg-kuryer-card shadow-kuryer-card">
            <div className="flex items-center gap-3 border-b-[0.5px] border-kuryer-hair p-3.5">
              <span className="grid size-10 shrink-0 place-items-center rounded-slab bg-kuryer-quiet text-small font-bold tabular text-kuryer-ink-soft">
                {groups(stop.items_count)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-small font-semibold text-kuryer-ink">
                  Buyurtma tarkibi
                </span>
                <span className="block text-micro text-kuryer-ink-soft">
                  Ro'yxat kuryerga ko'rsatilmaydi — qadoq yopiq
                </span>
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-3 p-3.5">
              <span className="text-small font-semibold text-kuryer-ink-soft">
                Jami · yetkazish bilan
              </span>
              <span className="text-body font-bold tabular text-kuryer-ink">
                {money(stop.total)}
              </span>
            </div>
          </div>

          {stop.address_meta ? (
            <div className="rounded-tile bg-kuryer-act-soft p-3.5">
              <Cap className="text-kuryer-act-deep">Mijoz izohi</Cap>
              <p className="mt-1 text-small text-kuryer-ink [overflow-wrap:anywhere]">
                {stop.address_meta}
              </p>
            </div>
          ) : null}

          {stop.attempts ? (
            <Notice
              tone="halt"
              title={`${groups(stop.attempts)} marta urinilgan`}
            >
              {stop.last_failure || "Sabab yozilmagan"}
            </Notice>
          ) : null}

          <Refusal error={failed.error} />

          <Slab onClick={() => go(`/kuryer/marshrut/${stop.id}/tasdiq`)}>
            Yetkazishni tasdiqlash
          </Slab>

          {/* The other outcome. Two taps — the second one is the sentence,
              because an attempt with no reason is a row an operator cannot
              act on. */}
          {asking ? (
            <div className="flex flex-col gap-2.5 rounded-tile border border-kuryer-halt-edge bg-kuryer-halt-soft p-3.5">
              <label className="block">
                <span className="mb-1.5 block text-micro font-semibold text-kuryer-halt-ink">
                  Nima bo'ldi?
                </span>
                <input
                  autoFocus
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Eshikni ochmadi"
                  className="h-control-sm w-full rounded-nub border-0 bg-kuryer-card px-3.5 text-small text-kuryer-ink outline-none placeholder:text-kuryer-ink-faint focus:ring-2 focus:ring-kuryer-halt-edge"
                />
              </label>
              <div className="flex gap-2.5">
                <Slab
                  tone="quiet"
                  className="h-control-sm flex-1 rounded-nub text-small"
                  onClick={() => setAsking(false)}
                >
                  Bekor
                </Slab>
                <Slab
                  tone="halt"
                  className="h-control-sm flex-1 rounded-nub text-small"
                  disabled={!reason.trim() || failed.isPending}
                  onClick={() =>
                    failed.mutate(reason.trim(), {
                      onSuccess: () => go("/kuryer/marshrut"),
                    })
                  }
                >
                  Yozib qo'y
                </Slab>
              </div>
              <p className="text-micro text-kuryer-ink-soft">
                Buyurtma sizda qoladi. Bekor qilishni dispetcher hal qiladi.
              </p>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setAsking(true)}
              className="h-control-sm w-full rounded-nub text-small font-semibold text-kuryer-halt-ink"
            >
              Bo'lmadi — hech kim chiqmadi
            </button>
          )}
        </div>
      </section>
    </div>
  )
}
