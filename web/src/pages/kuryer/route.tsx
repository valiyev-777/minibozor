/**
 * 2c — Marshrut. The main screen: a map, and a sheet of stops over it.
 *
 * Tapping a stop selects it — the pin is panned to and the card at the top of
 * the sheet becomes that stop. `Yetkazildi` on the card does not mark anything
 * delivered from here: it opens the proof screen, because a delivery needs a
 * name and the server refuses one without it. What it *does* do is what the
 * design asks — it moves the round on, since the confirmed stop leaves the
 * list and the next one becomes current.
 *
 * ------------------------------------------------------------ the map is a luxury
 *
 * The sheet is the screen and the map is behind it. When the tiles cannot
 * load, or nothing on the round has a pin, the map area says which of those it
 * is and the sheet takes the whole window — the stop list, the addresses, the
 * phone numbers and the button that finishes a delivery are all still there,
 * because a courier in a basement still has to finish the round.
 *
 * ----------------------------------------------------------------- departures
 *
 * The artboard prints an ETA per stop (`12 daq`, `26 daq`). There is no
 * routing service and no promised window on an order any more — `delivery_day`
 * and the two window columns are unwritten since the shop stopped offering
 * slots — so a per-stop time would be a number with nothing behind it. The
 * slot is kept and filled with the distance from the stop before it, which is
 * derived from the pins that do exist and is what the courier is comparing
 * stops by anyway.
 */

import { ArrowLeft, Phone } from "lucide-react"
import { useCallback, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { Chip, Loading, Nothing, Refusal, Slab } from "@/components/kuryer/bits"
import { RouteMap, TROUBLE_WORD, type Pin, type Trouble } from "@/components/kuryer/map"
import { cn } from "@/lib/cn"
import { distance, groups, money } from "@/lib/format"
import { between, pinned } from "@/lib/geo"
import { useMyRound } from "@/lib/queries"
import type { CourierOrder } from "@/lib/types"
import { Truck } from "lucide-react"

export function KuryerRoute() {
  const go = useNavigate()
  const round = useMyRound()
  const [at, setAt] = useState<number | null>(null)
  const [trouble, setTrouble] = useState<Trouble | null>(null)

  const stops = useMemo(
    () => (round.data ?? []).filter((one) => one.status === "shipped"),
    [round.data],
  )

  // The selection follows the round when the round changes under it — a
  // delivered stop leaves the list, and holding its id would leave the card at
  // the top of the sheet showing a door that is finished.
  const current = stops.find((one) => one.id === at) ?? stops[0]
  const index = current ? stops.indexOf(current) : -1

  const pins = useMemo<Pin[]>(
    () =>
      stops.flatMap((stop, n) => {
        const point = pinned(stop)
        if (!point) return []
        return [
          {
            id: stop.id,
            n: n + 1,
            lat: point.lat,
            lng: point.lng,
            state: stop.id === current?.id ? "now" : n < index ? "past" : "next",
          },
        ]
      }),
    [stops, current, index],
  )

  const onTrouble = useCallback((what: Trouble | null) => setTrouble(what), [])

  if (round.isLoading) {
    return (
      <div className="grid h-full place-items-center bg-kuryer-ground">
        <Loading what="Marshrut" />
      </div>
    )
  }

  if (!stops.length) {
    return (
      <div className="flex h-full flex-col justify-center gap-4 bg-kuryer-ground px-4 pb-[calc(var(--kuryer-tabs)+1rem)]">
        <Refusal error={round.error} />
        <Nothing
          icon={Truck}
          title="Qo'lingizda buyurtma yo'q"
          what="Omborga o'tib, tayyor buyurtmani o'zingiz oling."
        />
        <Slab onClick={() => go("/kuryer/olish")}>Yukni olish</Slab>
      </div>
    )
  }

  // With no map to look at, the sheet is the screen. Otherwise it sits over
  // the bottom half and the map keeps the top.
  const mapDown = trouble !== null

  return (
    <div className="relative h-full overflow-hidden bg-kuryer-ground">
      <RouteMap
        pins={pins}
        activeId={current?.id}
        onPick={setAt}
        onTrouble={onTrouble}
        className="absolute inset-x-0 top-0 h-[58%]"
      />

      {/* ------------------------------------------------- floating over the map */}
      <div className="pointer-events-none absolute inset-x-4 top-0 z-[600] flex items-start justify-between gap-2 pt-[calc(1rem+env(safe-area-inset-top))]">
        <Link
          to="/kuryer"
          className="kuryer-glass pointer-events-auto flex h-11 items-center gap-2 rounded-full px-3.5 text-small font-semibold text-kuryer-ink shadow-kuryer-float"
        >
          <ArrowLeft className="size-4" />
          Ombor · {groups(stops.length)} manzil
        </Link>
        {current?.recipient_phone ? (
          <a
            href={`tel:${current.recipient_phone}`}
            aria-label="Mijozga qo'ng'iroq"
            className="kuryer-glass pointer-events-auto grid size-11 shrink-0 place-items-center rounded-full text-kuryer-act shadow-kuryer-float"
          >
            <Phone className="size-5" />
          </a>
        ) : null}
      </div>

      {!mapDown && current ? (
        <div className="kuryer-afloat pointer-events-none absolute left-1/2 top-[calc(4.5rem+env(safe-area-inset-top))] z-[600] flex h-10 items-center gap-2 rounded-full px-3.5 shadow-kuryer-float kuryer-glass">
          <span className="size-2 rounded-full bg-kuryer-act" />
          <span className="text-small font-semibold tabular text-kuryer-ink">
            {index + 1} / {stops.length} bekat
          </span>
        </div>
      ) : null}

      {/* -------------------------------------------------------- the bottom sheet */}
      <section
        className={cn(
          "kuryer-sheet absolute inset-x-0 bottom-0 z-[400] flex flex-col rounded-t-sheet px-4 shadow-kuryer-sheet",
          mapDown ? "top-[calc(3.5rem+env(safe-area-inset-top))]" : "top-[46%]",
        )}
      >
        <div className="flex justify-center py-2.5">
          <span aria-hidden className="h-[5px] w-10 rounded-full bg-kuryer-grab" />
        </div>

        {mapDown ? (
          <p className="pb-2.5 text-center text-micro text-kuryer-ink-faint">
            {TROUBLE_WORD[trouble]} — ro'yxat bo'yicha ishlayvering
          </p>
        ) : null}

        {current ? (
          <article className="shrink-0 rounded-tile bg-kuryer-card p-3.5 shadow-kuryer-card">
            <div className="flex items-baseline justify-between gap-2">
              <span className="caption font-bold text-kuryer-act-deep">
                Joriy bekat · {index + 1} / {stops.length}
              </span>
              <span className="text-micro font-semibold tabular text-kuryer-ink-soft">
                {current.code}
              </span>
            </div>
            <p className="mt-2 text-body font-semibold text-kuryer-ink [overflow-wrap:anywhere]">
              {current.address_line || "Manzil ko'rsatilmagan"}
            </p>
            <p className="text-small tabular text-kuryer-ink-soft">
              {groups(current.items_count)} dona ·{" "}
              {current.cash_due ? `${money(current.cash_due)} naqd` : "onlayn to'langan"}
            </p>

            <div className="mt-3 flex gap-2.5">
              <Link
                to={`/kuryer/marshrut/${current.id}`}
                className="grid h-control-sm shrink-0 place-items-center rounded-nub bg-kuryer-act-soft px-4 text-small font-semibold text-kuryer-act-deep"
              >
                Tafsilot
              </Link>
              <Slab
                className="h-control-sm flex-1 rounded-nub text-small"
                onClick={() => go(`/kuryer/marshrut/${current.id}/tasdiq`)}
              >
                Yetkazildi
              </Slab>
            </div>
          </article>
        ) : null}

        <p className="caption shrink-0 px-1 pb-2 pt-3.5 font-bold text-kuryer-ink-soft">
          Bekatlar
        </p>
        <div className="-mx-1 flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto overscroll-contain px-1 pb-[calc(var(--kuryer-tabs)+0.5rem)]">
          {stops.map((stop, n) => (
            <Stop
              key={stop.id}
              stop={stop}
              n={n + 1}
              on={stop.id === current?.id}
              from={n > 0 ? stops[n - 1] : undefined}
              onPick={() => setAt(stop.id)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

/**
 * One line in the sheet.
 *
 * A stop with no pin says so, plainly, and keeps its number and its place: it
 * is the same door whether or not anybody recorded where it is, and dropping
 * it from the list to keep the map tidy is how a parcel goes undelivered.
 */
function Stop({
  stop,
  n,
  on,
  from,
  onPick,
}: {
  stop: CourierOrder
  n: number
  on: boolean
  from?: CourierOrder
  onPick: () => void
}) {
  const here = pinned(stop)
  const there = from ? pinned(from) : null
  const leg = here && there ? between(there, here) : null

  return (
    <button
      type="button"
      onClick={onPick}
      aria-current={on ? "true" : undefined}
      className={cn(
        "flex w-full items-center gap-3 rounded-slab p-3 text-left transition-colors",
        on
          ? "border-[1.5px] border-kuryer-act-edge bg-kuryer-act-soft"
          : "border-[0.5px] border-kuryer-hair bg-kuryer-card",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-full text-small font-bold tabular",
          on
            ? "bg-kuryer-act text-kuryer-act-ink"
            : "bg-kuryer-quiet text-kuryer-ink-soft",
        )}
      >
        {n}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-small font-semibold text-kuryer-ink [overflow-wrap:anywhere]">
          {stop.address_line || "Manzil ko'rsatilmagan"}
        </span>
        <span className="block text-micro tabular text-kuryer-ink-soft">
          {leg !== null ? `${distance(leg)} · ` : ""}
          {stop.cash_due ? `${money(stop.cash_due)} naqd` : "onlayn to'langan"}
        </span>
        {!here ? (
          <span className="mt-1 block text-micro text-kuryer-ink-faint">
            xaritada belgilanmagan
          </span>
        ) : null}
      </span>
      <Chip tone={on ? "act" : "quiet"}>{on ? "Joriy" : "Navbatda"}</Chip>
    </button>
  )
}
