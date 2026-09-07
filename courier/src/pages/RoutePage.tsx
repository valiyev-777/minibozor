import { Link } from "react-router-dom"
import { ChevronRight, RefreshCw } from "lucide-react"
import { Button, Empty, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { stops, type Stop } from "@/offline/derive"
import { dayLabel, stamp, sum } from "@/lib/format"

/**
 * Today's round, in the order somebody planned it.
 *
 * The stops that are done drop to the bottom rather than disappearing: a
 * courier looking for the flat they delivered to twenty minutes ago is looking
 * for evidence, and a list that quietly forgets is a list that cannot answer.
 */
export function RoutePage() {
  const { orders, rows, refresh, refreshing, reachable } = useOffline()
  const all = stops(orders.data, rows)
  const open = all.filter((stop) => !stop.done)
  const done = all.filter((stop) => stop.done)

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-3xl font-bold">Bugungi reys</h1>
        <span className="text-base text-ink-soft">{open.length} manzil</span>
      </div>

      {/* When the round was last actually fetched. A round that is quietly six
          hours stale would send a courier to a door cancelled at ten. */}
      {!reachable && orders.at ? (
        <p className="text-base text-warn">
          Oflayn ko'rinish — oxirgi yangilangani {stamp(new Date(orders.at).toISOString())}
        </p>
      ) : null}

      <Button tone="ghost" onClick={() => void refresh()} busy={refreshing}>
        <RefreshCw className="size-6" />
        Yangilash
      </Button>

      {all.length === 0 ? (
        <Empty>Bugun sizga buyurtma biriktirilmagan.</Empty>
      ) : (
        <ul className="space-y-3">
          {open.map((stop) => (
            <StopCard key={stop.order.id} stop={stop} />
          ))}
        </ul>
      )}

      {done.length > 0 ? (
        <>
          <h2 className="pt-4 text-xl font-bold text-ink-soft">Yakunlangan</h2>
          <ul className="space-y-3">
            {done.map((stop) => (
              <StopCard key={stop.order.id} stop={stop} />
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}

function StopCard({ stop }: { stop: Stop }) {
  const { order, queued, done } = stop
  return (
    <li>
      <Link to={`/order/${order.id}`} className="block">
        <Panel tone={queued ? "pending" : done ? "good" : "plain"} className="active:scale-[0.995]">
          <div className="flex items-start gap-3">
            {/* The stop number an operator set. Big, because it is how a
                courier finds their place in a list of eleven. */}
            <span className="min-w-10 text-3xl font-bold tabular-nums">
              {order.sequence > 0 ? order.sequence : "—"}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{order.code}</span>
                {order.delivery_window ? (
                  <Pill>{order.delivery_window}</Pill>
                ) : order.delivery_day ? (
                  <Pill>{dayLabel(order.delivery_day)}</Pill>
                ) : null}
                {order.attempts > 0 ? (
                  <Pill tone="bad">{order.attempts} urinish</Pill>
                ) : null}
              </div>
              <p className="selectable mt-1 text-xl leading-snug font-semibold">
                {order.address_line}
              </p>
              <p className="text-lg text-ink-soft">{order.recipient_name}</p>

              {order.cash_due > 0 ? (
                <p className="mt-2 text-xl font-bold">Naqd: {sum(order.cash_due)}</p>
              ) : (
                <p className="mt-2 text-lg text-ink-soft">Karta bilan to'langan</p>
              )}

              {queued === "deliver" ? (
                <p className="mt-2 font-bold text-warn">Yetkazildi · yuborilmagan</p>
              ) : queued === "failed" ? (
                <p className="mt-2 font-bold text-warn">Urinish yozildi · yuborilmagan</p>
              ) : done ? (
                <p className="mt-2 font-bold text-good">Yetkazildi</p>
              ) : null}
            </div>
            <ChevronRight className="mt-1 size-6 shrink-0 text-ink-soft" />
          </div>
        </Panel>
      </Link>
    </li>
  )
}
