/**
 * The last mile — three screens, read outdoors, one-handed, sometimes in a
 * glove.
 *
 * **A courier takes their own work.** The board shows what is packed and
 * nobody has claimed; taking one is the handover, and it is the moment the
 * parcel moves into that courier's own bag in the ledger. Nobody assigns
 * rounds, so nothing stops on the evening the assigner is not in.
 *
 * **A knock is an event, not a state.** A refusal at a door does not put the
 * order into a new status — it is still on its way — so a failed attempt is
 * recorded with its reason and the order stays where it is. Deciding to give
 * up belongs to the office, which can see three refusals; the courier is at
 * one door with one.
 *
 * Every write carries an idempotency key, because the phone has no signal in
 * lifts and basements: the app sends what it could not send earlier, possibly
 * twice, and a repeat replays the first answer rather than delivering the same
 * parcel again.
 */

import { Banknote, ClipboardCheck, MapPin, PackageSearch, Phone, Truck } from "lucide-react"
import { useMemo, useState } from "react"

import { Empty, PageHeader, Panel, Pill, Problem, Stat, Waiting } from "@/components/page"
import type { Tone } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { groups, money } from "@/lib/format"
import {
  useAvailableOrders,
  useDeliver,
  useEarnings,
  useFailed,
  useMyHistory,
  useMyRound,
  useTakeOrder,
} from "@/lib/queries"
import type { CourierOrder, OrderStatus } from "@/lib/types"

// A finished stop, in the reader's language. The screen printed the server's
// own word for anything that was not `delivered`, so a parcel the customer
// sent back said `returned` to somebody who reads Uzbek.
const STATUS_WORD: Partial<Record<OrderStatus, string>> = {
  delivered: "yetkazildi",
  returned: "qaytarildi",
  cancelled: "bekor qilindi",
}

const STATUS_TONE: Partial<Record<OrderStatus, Tone>> = {
  delivered: "good",
  returned: "warn",
  cancelled: "danger",
}

// ------------------------------------------------------------------- my work

export function MyWorkPage() {
  const round = useMyRound()
  const board = useAvailableOrders()
  const take = useTakeOrder()

  const carrying = (round.data ?? []).filter((order) => order.status === "shipped")

  return (
    <div className="space-y-4">
      <PageHeader title="Mening ishlarim" subtitle="Olingan va olish mumkin bo'lgan" />
      <Problem error={round.error || board.error || take.error} />
      {round.isLoading ? <Waiting what="Ishlar" /> : null}

      {carrying.length ? (
        <section className="space-y-2">
          <h2 className="text-small font-semibold">Qo'lda ({carrying.length})</h2>
          {carrying.map((order) => (
            <Parcel key={order.id} order={order} />
          ))}
        </section>
      ) : (
        <Empty
          icon={Truck}
          title="Qo'lingizda buyurtma yo'q"
          what="Pastdagi ro'yxatdan tayyor buyurtmani o'zingiz oling."
        />
      )}

      <section className="space-y-2">
        <h2 className="text-small font-semibold">Olish mumkin</h2>
        {board.data?.length === 0 ? (
          <Empty
            icon={PackageSearch}
            title="Tayyor buyurtma yo'q"
            what="Ombor yig'ib bo'lgach shu yerda ko'rinadi."
          />
        ) : null}
        {(board.data ?? []).map((order) => (
          <Panel key={order.id}>
            <div className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-body font-semibold tabular">{order.code}</div>
                <div className="truncate text-small text-ink-soft">
                  {order.address_line}
                </div>
                <div className="text-micro text-ink-faint">
                  {order.items_count} dona · {money(order.total)}
                  {order.cash_due ? ` · naqd ${money(order.cash_due)}` : ""}
                </div>
              </div>
              <Button size="lg" disabled={take.isPending} onClick={() => take.mutate(order.id)}
              >
                Olish
              </Button>
            </div>
          </Panel>
        ))}
      </section>
    </div>
  )
}

function Parcel({ order }: { order: CourierOrder }) {
  const [open, setOpen] = useState(false)
  const deliver = useDeliver(order.id)
  const failed = useFailed(order.id)
  const [name, setName] = useState(order.recipient_name)
  const [cash, setCash] = useState(String(order.cash_due || 0))

  return (
    <Panel>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-body font-semibold tabular">{order.code}</div>
          <a
            href={`https://yandex.uz/maps/?text=${encodeURIComponent(order.address_line)}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-start gap-1 text-body underline underline-offset-2">
            <MapPin className="mt-0.5 size-4 shrink-0 text-ink-faint" />
            {order.address_line}
          </a>
          {order.address_meta ? (
            <div className="text-small text-ink-soft">{order.address_meta}</div>
          ) : null}
          <a
            href={`tel:${order.recipient_phone}`}
            className="mt-1 inline-flex items-center gap-1 text-small underline underline-offset-2">
            <Phone className="size-4 text-ink-faint" />
            {order.recipient_phone}
          </a>
          {order.attempts ? (
            <p className="mt-1 rounded-control bg-warn-soft p-2 text-micro text-warn-ink">
              {order.attempts} marta urinilgan
              {order.last_failure ? ` — ${order.last_failure}` : ""}
            </p>
          ) : null}
        </div>

        {order.cash_due ? (
          <div className="shrink-0 rounded-control bg-warn-soft p-2 text-right">
            <Banknote className="ml-auto size-4 text-warn-ink" />
            <div className="figure text-warn-ink">{groups(order.cash_due)}</div>
            <div className="text-micro text-warn-ink">naqd olinadi</div>
          </div>
        ) : null}
      </div>

      <Problem error={deliver.error || failed.error} />

      {open ? (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            deliver.mutate({
              recipient_name: name.trim(),
              cash_collected: Number(cash) || 0,
            })
          }}
          className="mt-3 space-y-2 border-t pt-3">
          <label className="block">
            <span className="mb-1 block text-micro text-ink-soft">
              Kim qabul qildi
            </span>
            {/* Required, and a photograph is not: the name is the one field a
                courier can always fill in, standing in front of the person who
                took the goods. A photo needs signal, and a basement has none. */}
            <Input
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              aria-label="Kim qabul qildi"
              className="h-control-lg text-body" />
          </label>
          {order.cash_due ? (
            <label className="block">
              <span className="mb-1 block text-micro text-ink-soft">Olingan naqd</span>
              <Input
                value={cash}
                onChange={(event) => setCash(event.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                aria-label="Olingan naqd"
                className="h-control-lg tabular text-body" />
            </label>
          ) : null}
          <Button size="lg" type="submit" disabled={deliver.isPending || !name.trim()} className="w-full">
            Yetkazildi
          </Button>
        </form>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <Button size="lg" onClick={() => setOpen(true)}
          >
            Yetkazdim
          </Button>
          <Button size="lg" variant="secondary" disabled={failed.isPending} onClick={() => {
              const reason = window.prompt("Nima bo'ldi?")
              if (reason) failed.mutate(reason)
            }}
          >
            Bo'lmadi
          </Button>
        </div>
      )}
    </Panel>
  )
}

// -------------------------------------------------------------------- history

/**
 * What this courier has finished, which is not what is in their van.
 *
 * It used to read the round — the door that answers with the stops still open
 * — and filter it for "not shipped". A delivered parcel leaves that list, so
 * the only thing the filter could ever catch was a parcel taken and not yet
 * on the road, and a courier who had delivered thirteen was told there were
 * none while the earnings screen next to it counted all thirteen.
 *
 * Newest first, and the subtitle finally means it: the round comes back in
 * the order the promises were made, which is right for driving and backwards
 * for reading back.
 */
export function CourierHistoryPage() {
  const round = useMyHistory()
  const done = useMemo(
    () =>
      (round.data ?? [])
        .filter(
          (order) => order.status !== "packing" && order.status !== "shipped",
        )
        .sort((a, b) => b.id - a.id),
    [round.data],
  )

  return (
    <div className="space-y-4">
      <PageHeader title="Tarix" subtitle="Eng yangisi yuqorida" />
      <Problem error={round.error} />
      {round.isLoading ? <Waiting /> : null}
      {!round.isLoading && done.length === 0 ? (
        <Empty
          icon={ClipboardCheck}
          title="Hali yetkazilgan buyurtma yo'q"
          what="Yetkazganlaringiz shu yerda to'planib boradi."
        />
      ) : null}

      <ul className="space-y-2">
        {done.map((order) => (
          <li key={order.id}>
            <Panel>
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-small font-semibold tabular">{order.code}</div>
                  <div className="truncate text-micro text-ink-faint">
                    {order.address_line}
                  </div>
                </div>
                {/* A parcel that came back is not a parcel that failed to
                    arrive: it arrived, and then the customer sent it back.
                    Printing the raw English status for everything that is not
                    `delivered` said `returned` to somebody who reads Uzbek. */}
                <Pill tone={STATUS_TONE[order.status] ?? "neutral"}>
                  {STATUS_WORD[order.status] ?? order.status}
                </Pill>
              </div>
            </Panel>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ------------------------------------------------------------------- earnings

export function EarningsPage() {
  const earnings = useEarnings()

  return (
    <div className="space-y-4">
      <PageHeader title="Daromad" subtitle="Har yetkazilgan buyurtma uchun" />
      <Problem error={earnings.error} />
      {earnings.isLoading ? <Waiting /> : null}

      {earnings.data ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Bugun" value={money(earnings.data.earned_today)} />
            <Stat label="Shu oy" value={money(earnings.data.earned_month)} />
            <Stat
              label="Bugun yetkazildi"
              value={`${groups(earnings.data.delivered_today)} ta`}
            />
            <Stat
              label="Bitta buyurtma"
              value={money(earnings.data.fee_per_delivery)}
            />
          </div>

          {earnings.data.cash_on_hand ? (
            <div className="rounded-panel border border-warn bg-warn-soft p-3">
              <div className="text-micro text-warn-ink">Qo'ldagi naqd</div>
              <div className="figure text-warn-ink">
                {money(earnings.data.cash_on_hand)}
              </div>
              <p className="text-micro text-warn-ink">
                Kassaga topshirilishi kerak.
              </p>
            </div>
          ) : null}

          <Panel className="text-small text-ink-soft">
            Jami {groups(earnings.data.delivered_total)} ta yetkazilgan ·{" "}
            {groups(earnings.data.failed_attempts)} marta bo'lmagan
          </Panel>
        </>
      ) : null}
    </div>
  )
}
