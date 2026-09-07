import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, PhoneCall } from "lucide-react"
import { Button, ButtonLink, Empty, Labelled, Panel, Pill } from "@/components/ui"
import { useOffline } from "@/offline/OfflineProvider"
import { canDeliver, shiftState, stops } from "@/offline/derive"
import { dayLabel, prettyPhone, sum } from "@/lib/format"

/**
 * One door.
 *
 * Ordered the way a courier uses it: where to go, who to call, what they are
 * holding, and — on its own, in its own box — how much money to ask for. The
 * cash figure is separated from the order total because they are different
 * numbers on a card order, and asking a customer who has already paid for
 * another 240 000 so'm is the single most expensive mistake available here.
 */
export function OrderPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { orders, shift, rows } = useOffline()

  const orderId = Number(id)
  const stop = stops(orders.data, rows).find((s) => s.order.id === orderId)
  if (!stop) return <Empty>Bu buyurtma ro'yxatda yo'q. Reysni yangilang.</Empty>

  const { order, queued, done } = stop
  const state = shiftState(shift.data, rows)
  const shiftReady = canDeliver(state)

  return (
    <div className="mx-auto max-w-xl space-y-4 p-4 pb-safe">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-lg font-semibold text-muted"
      >
        <ArrowLeft className="size-6" />
        Reys
      </button>

      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-3xl font-bold">{order.code}</h1>
        {order.sequence > 0 ? <Pill tone="brand">{order.sequence}-manzil</Pill> : null}
        {order.delivery_window ? <Pill>{order.delivery_window}</Pill> : null}
        {order.delivery_day ? <Pill>{dayLabel(order.delivery_day)}</Pill> : null}
      </div>

      {queued ? (
        <Panel tone="pending">
          <p className="text-lg font-bold text-pending">
            {queued === "deliver" ? "Yetkazildi · yuborilmagan" : "Urinish yozildi · yuborilmagan"}
          </p>
          <p className="mt-1 text-base text-muted">
            Telefoningizda saqlandi. Tarmoq qaytganda o'zi yuboriladi.
          </p>
        </Panel>
      ) : null}

      <Panel>
        <Labelled label="Manzil">
          <span className="selectable">{order.address_line}</span>
        </Labelled>
        {order.address_meta ? (
          <p className="selectable mt-1 text-lg text-muted">{order.address_meta}</p>
        ) : null}
      </Panel>

      <Panel>
        <Labelled label="Mijoz">{order.recipient_name}</Labelled>
        <p className="selectable mt-1 text-lg text-muted">{prettyPhone(order.recipient_phone)}</p>
      </Panel>

      {/* One tap, and the phone's own dialler. Not `tel:` inside a menu and not
          a number to copy: a courier calls from a doorway with one hand. */}
      <ButtonLink href={`tel:${order.recipient_phone}`} tone="ghost">
        <PhoneCall className="size-6" />
        Qo'ng'iroq qilish
      </ButtonLink>

      {/*
        The money, alone in its own box.

        `cash_due` is nought on a card order and the wording changes with it —
        the server computes both and this screen never adds anything up itself.
      */}
      {order.cash_due > 0 ? (
        <Panel tone="cash">
          <p className="text-lg font-semibold text-muted">Olinadigan naqd pul</p>
          <p className="text-5xl font-bold tabular-nums">{sum(order.cash_due)}</p>
        </Panel>
      ) : (
        <Panel>
          <p className="text-lg font-semibold text-good">Karta bilan to'langan — pul olinmaydi</p>
        </Panel>
      )}

      <Panel>
        <div className="flex items-baseline justify-between">
          <span className="text-lg text-muted">Tovarlar</span>
          <span className="text-2xl font-bold">{order.items_count} dona</span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <span className="text-lg text-muted">Buyurtma summasi</span>
          <span className="text-xl font-semibold tabular-nums">{sum(order.total)}</span>
        </div>
        {/*
          The line items are not here because the courier API does not carry
          them: `CourierOrderOut` has a count and a total and no list. That is
          the server's call — a courier hands over a sealed parcel and the
          picking was checked at the warehouse — and inventing a list from
          another endpoint would mean reading an operator's, which a courier
          is refused. If dispatch wants the contents on this screen, it is a
          field on `CourierOrderOut`, not a second request from here.
        */}
      </Panel>

      {order.attempts > 0 ? (
        <Panel tone="bad">
          <p className="text-lg font-bold text-bad">{order.attempts} marta urinilgan</p>
          {order.last_failure ? (
            <p className="mt-1 text-lg">Oxirgi sabab: {order.last_failure}</p>
          ) : null}
        </Panel>
      ) : null}

      {done ? null : (
        <div className="space-y-3 pt-2">
          {!shiftReady ? (
            <Panel tone="pending">
              <p className="text-lg font-bold text-pending">Smena ochilmagan</p>
              <p className="mt-1 text-base">
                Yetkazishni belgilash uchun smena ochiq bo'lishi shart — naqd pul shu smenaga
                yoziladi.
              </p>
              <Link to="/shift" className="mt-3 block">
                <Button tone="brand">Smenani ochish</Button>
              </Link>
            </Panel>
          ) : (
            <Link to={`/order/${order.id}/deliver`} className="block">
              <Button tone="good">Yetkazildi</Button>
            </Link>
          )}
          <Link to={`/order/${order.id}/failed`} className="block">
            <Button tone="ghost">Urinish muvaffaqiyatsiz</Button>
          </Link>
        </div>
      )}
    </div>
  )
}
