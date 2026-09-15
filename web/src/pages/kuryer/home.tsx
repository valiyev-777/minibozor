/**
 * 2a — Bosh ekran. What is waiting at the warehouse, and what is already in
 * the bag.
 *
 * The screen a courier opens first, so it answers the two questions they open
 * it to ask: is there work, and what does the round I am holding come to. One
 * action at the foot, and which action it is depends on the answer.
 *
 * ----------------------------------------------------------------- departures
 *
 * The artboard's queue tile reads `2 / 3 · 3 kuryer onlayn`. **There is no
 * such figure.** Nobody queues at this warehouse — the board is open and the
 * first courier to press "take" gets the parcel — and the server does not
 * record who is available, because it has no shift (see `lib/shift`). Printing
 * a position in a queue that does not exist would be the screen telling a lie
 * about how the work is handed out, so the tile shows what is true instead:
 * how many parcels this courier is already carrying.
 *
 * The artboard also names a warehouse, `Ombor #2 · Chilonzor`. There is one
 * warehouse. The header says so rather than inventing a number.
 *
 * `BUGUNGI MARSHRUT` keeps its shape and loses its certainty: the distance is
 * the sum of the straight lines between pinned stops (`lib/geo`), labelled
 * `taxminiy`, and it is **not drawn at all** when the round has fewer than two
 * pins — which is every round until the shop starts recording coordinates. A
 * `0,0 km` under a heading is a worse answer than a sentence saying the stops
 * are not on the map yet.
 */

import { Boxes, PackageCheck, Truck } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Cap, Glass, Loading, Notice, Page, Refusal, Slab, Tile, Title } from "@/components/kuryer/bits"
import { along, pinned } from "@/lib/geo"
import { age, dayLine, distance, groups } from "@/lib/format"
import { minutesFor } from "@/lib/geo"
import { useAvailableOrders, useMyRound } from "@/lib/queries"
import { useOnShift } from "@/lib/shift"

export function KuryerHome() {
  const go = useNavigate()
  const [onShift, setOnShift] = useOnShift()
  // Off shift, the board stops polling. That is the whole of what the switch
  // does to the machine, and it is a real saving on a phone in a pocket.
  const board = useAvailableOrders(onShift)
  const round = useMyRound()

  const waiting = board.data ?? []
  const carrying = (round.data ?? []).filter((one) => one.status === "shipped")

  const pins = carrying.map(pinned).filter((one) => one !== null)
  const kilometres = along(pins)
  const cash = carrying.reduce((sum, one) => sum + one.cash_due, 0)
  const ready = waiting.reduce((sum, one) => sum + one.items_count, 0)

  return (
    <Page>
      <Title over={dayLine(new Date())}>Bugun</Title>

      <Refusal error={round.error || board.error} />

      {/* ------------------------------------------------- the loading point */}
      <Glass className="p-4.5">
        <div className="flex items-center gap-3">
          <span className="grid size-12 shrink-0 place-items-center rounded-slab bg-kuryer-act-soft text-kuryer-act">
            <Boxes className="size-6" />
          </span>
          <div className="min-w-0 flex-1">
            <Cap>Yuklab olish nuqtasi</Cap>
            <p className="text-body font-semibold text-kuryer-ink">Ombor</p>
          </div>
        </div>
        <p className="mt-3 text-small text-kuryer-ink-soft">
          Tovar faqat shu ombordan olinadi. Tayyor buyurtmani o'zingiz
          belgilaysiz — qolgani boshqa kuryerga qoladi.
        </p>

        <div className="mt-3.5 flex gap-2.5">
          <div className="min-w-0 flex-1 rounded-slab bg-kuryer-act-soft p-3">
            <Cap>Qo'lingizda</Cap>
            <p className="figure mt-1 text-kuryer-ink">{groups(carrying.length)}</p>
            <p className="text-micro text-kuryer-ink-soft">
              {carrying.length ? "yetkazilmagan" : "bo'sh"}
            </p>
          </div>
          <div className="min-w-0 flex-1 rounded-slab bg-kuryer-done-soft p-3">
            <Cap>Yuk tayyor</Cap>
            <p className="figure mt-1 text-kuryer-done-deep">
              {onShift ? groups(waiting.length) : "—"}
            </p>
            <p className="text-micro text-kuryer-ink-soft">
              {onShift ? `${groups(ready)} dona` : "oflayn"}
            </p>
          </div>
        </div>
      </Glass>

      {/* ------------------------------------------------------- today's round */}
      <Tile>
        <Cap>Bugungi marshrut</Cap>
        {carrying.length === 0 ? (
          <p className="mt-2 text-small text-kuryer-ink-soft">
            Hali hech narsa olmadingiz.
          </p>
        ) : (
          <>
            {/* The figure is the number; the unit and the count are the line
                beside it. `1,2 km · 4 manzil` set entirely at display size
                reads as three numbers of equal weight, and only the first one
                is the answer. */}
            <p className="mt-2 flex flex-wrap items-baseline gap-2">
              <span className="display text-kuryer-ink [overflow-wrap:anywhere]">
                {pins.length > 1
                  ? distance(kilometres).replace(" km", "")
                  : groups(carrying.length)}
              </span>
              <span className="text-small font-semibold text-kuryer-ink-soft">
                {pins.length > 1
                  ? `km · ${groups(carrying.length)} manzil`
                  : "manzil"}
              </span>
            </p>
            <div className="mt-3.5 flex flex-wrap gap-x-6 gap-y-2">
              {/* Shown only when there is a distance to base it on — see the
                  file comment. A time estimate over an unknown distance is a
                  guess wearing a number. */}
              {pins.length > 1 ? (
                <div>
                  <p className="text-micro text-kuryer-ink-soft">Taxminiy vaqt</p>
                  <p className="text-body font-semibold tabular text-kuryer-ink">
                    {age(minutesFor(kilometres, carrying.length))}
                  </p>
                </div>
              ) : null}
              <div>
                <p className="text-micro text-kuryer-ink-soft">Naqd olinadi</p>
                <p className="text-body font-semibold tabular text-kuryer-cash-ink">
                  {groups(cash)}
                </p>
              </div>
            </div>
            {pins.length < 2 ? (
              <p className="mt-3 text-micro text-kuryer-ink-faint">
                Masofa hisoblanmadi — bu buyurtmalar xaritada belgilanmagan.
              </p>
            ) : null}
          </>
        )}
      </Tile>

      {round.isLoading ? <Loading what="Marshrut" /> : null}

      {!onShift ? (
        <Notice tone="halt" title="Oflaynsiz">
          Ombor navbati ko'rinmaydi va yangilanmaydi. Bu faqat shu telefondagi
          belgi — ombor sizni baribir ko'radi.
        </Notice>
      ) : null}

      {/* ------------------------------------------------------- the one action
          Which act it is depends on what the person is holding: come back on,
          then load up, then drive. One filled slab, whichever it turns out to
          be. */}
      {!onShift ? (
        <Slab onClick={() => setOnShift(true)}>
          <span className="size-2.5 rounded-full bg-kuryer-act-ink" />
          Onlayn bo'lish
        </Slab>
      ) : carrying.length ? (
        <Slab onClick={() => go("/kuryer/marshrut")}>
          <Truck className="size-5" />
          Marshrutga o'tish
        </Slab>
      ) : (
        <Slab disabled={!waiting.length} onClick={() => go("/kuryer/olish")}>
          <PackageCheck className="size-5" />
          Yukni olish
        </Slab>
      )}

      <p className="text-center text-micro text-kuryer-ink-faint">
        {!onShift
          ? "Onlayn bo'lgach ombor navbati ochiladi"
          : carrying.length
            ? `${groups(carrying.length)} ta buyurtma yetkazilishi kerak`
            : waiting.length
              ? `Omborda ${groups(waiting.length)} ta tayyor buyurtma bor`
              : "Ombor yig'ib bo'lgach shu yerda ko'rinadi"}
      </p>
    </Page>
  )
}
