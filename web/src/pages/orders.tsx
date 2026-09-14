/**
 * Buyurtmalar — one queue, read by the office and worked from the front.
 *
 * **A queue is worked from the front; a history is read from the top.** Asking
 * for `placed` is a bench queue and comes back oldest first — serving the
 * newest order first is how the first one waits all day. Asking for everything
 * is reading, and comes back newest first.
 *
 * **The buttons come from `next_statuses`.** The server says which moves are
 * open from where the order actually is, so a client cannot offer one it will
 * then be refused for. The one move that is not here is `shipped`: the
 * handover is a courier picking the parcel up, at their own door.
 *
 * ------------------------------------------------------------- why a table
 *
 * It was a stack of cards, one per order, each hand-drawing its own panel.
 * The office reads this screen at a desk, in the compact density, looking
 * *down* a queue — for the oldest one, for the one that is still unpaid, for
 * the customer who just telephoned. None of those questions can be answered
 * by a column of cards, because nothing in a card lines up with the same
 * thing in the card below it. Six fields that repeat on every row are six
 * columns, and they came with the three things the screen never had: a
 * search, a page size, and both of them in the address bar.
 *
 * What did *not* become a column is the act. The buttons stay on the row and
 * stay in the words the server gave them, because which move is open depends
 * on where the order is and a column of identical buttons would be a lie.
 *
 * ------------------------------------------------------- and why a drawer
 *
 * A row says where an order is. It cannot say what happened to it, and that
 * is the whole of the telephone call: a customer rings to ask where their
 * order is, and the person who answers needs the lines with their frozen
 * prices, the timeline, the money broken up, and — when it has gone wrong —
 * **every knock at the door**. That last list is carried by
 * `GET /admin/orders/{id}` and nowhere else, and nothing in the panel fetched
 * it, so `shipped → cancelled` was a decision the office could make with
 * none of the evidence it is supposed to make it on.
 *
 * The open order lives in the address bar (`?buyurtma=`), for the same reason
 * the open customer does: somebody on the telephone wants to send a colleague
 * the order, not a description of it.
 */

import { Banknote, Check, MapPin, Package, PackageCheck, Phone } from "lucide-react"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import { DataTable, type Column } from "@/components/data-table"
import { Empty, PageHeader, Panel, Pill, Problem, Segmented } from "@/components/page"
import type { Tone } from "@/components/page"
import { mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { age, date, dateTime, groups, minutesSince, money } from "@/lib/format"
import {
  useBuildPickTask,
  useCancelReasons,
  useMoveOrder,
  useOrder,
  useOrders,
} from "@/lib/queries"
import { useSession } from "@/lib/session"
import type {
  DeliveryAttempt,
  OrderDetail,
  OrderItem,
  OrderStatus,
  StaffOrder,
} from "@/lib/types"

const TABS: { key: string; label: string }[] = [
  { key: "placed", label: "Yangi" },
  { key: "packing", label: "Yig'ilmoqda" },
  { key: "shipped", label: "Yo'lda" },
  { key: "delivered", label: "Yetkazilgan" },
  { key: "", label: "Hammasi" },
]

const WORD: Record<OrderStatus, string> = {
  placed: "Yangi",
  packing: "Yig'ilmoqda",
  shipped: "Yo'lda",
  delivered: "Yetkazildi",
  cancelled: "Bekor qilindi",
  returned: "Qaytarildi",
}

/** A button says what it *does*; the chip beside it says where the order is.
 *
 * They used to share a word — a filter tab reading "Yig'ilmoqda" beside a
 * button reading "Yig'ilmoqda" — and one of them changes the order while the
 * other changes the list. */
/** Where the order is, as a colour: amber not yet, blue on its way, green
 *  arrived, grey over. The same three meanings as everywhere else. */
const TONE: Record<OrderStatus, Tone> = {
  placed: "warn",
  packing: "brand",
  shipped: "brand",
  delivered: "good",
  cancelled: "neutral",
  returned: "neutral",
}

const MOVE: Record<OrderStatus, string> = {
  placed: "Yangi qilish",
  packing: "Yig'ishga o'tkazish",
  shipped: "Kuryerga berish",
  delivered: "Yetkazildi deb belgilash",
  cancelled: "Bekor qilish",
  returned: "Qaytarildi deb belgilash",
}

const COLUMNS: Column<StaffOrder>[] = [
  {
    key: "code",
    header: "Buyurtma",
    cell: (order) => (
      <>
        <div className="tabular font-semibold">{order.code}</div>
        {/* What to fetch, in one line: a picker recognises an order by the
            thing in it. */}
        <div className="truncate text-micro text-ink-faint">
          {order.items_summary}
        </div>
      </>
    ),
  },
  {
    key: "customer",
    header: "Mijoz",
    cell: (order) => (
      <>
        <div className="truncate">{order.customer_name || order.customer_phone}</div>
        <div className="truncate text-micro text-ink-faint">{order.address_line}</div>
      </>
    ),
  },
  {
    key: "status",
    header: "Holat",
    width: "1%",
    cell: (order) => (
      <span className="flex flex-wrap items-center gap-1">
        <Pill tone={TONE[order.status]}>{WORD[order.status]}</Pill>
        {!order.paid ? <Pill>naqd</Pill> : null}
      </span>
    ),
  },
  {
    key: "total",
    header: "Summa",
    numeric: true,
    width: "1%",
    className: "whitespace-nowrap",
    cell: (order) => (
      <>
        <div className="font-semibold">{money(order.total)}</div>
        <div className="text-micro text-ink-faint">{groups(order.items_count)} dona</div>
      </>
    ),
  },
  {
    key: "created_at",
    header: "Vaqt",
    width: "1%",
    className: "whitespace-nowrap",
    cell: (order) => (
      <>
        <div className="tabular text-ink-soft">{dateTime(order.created_at)}</div>
        <div className="text-micro text-ink-faint">
          {order.status === "placed"
            ? `${age(minutesSince(order.created_at))} kutmoqda`
            : order.courier_name}
        </div>
      </>
    ),
  },
  {
    key: "act",
    header: "",
    align: "end",
    width: "1%",
    // The row opens the order; the buttons do their own thing. Without this
    // the stop, pressing "Yig'ishga o'tkazish" would also swing the drawer
    // open over the queue somebody is working down.
    cell: (order) => (
      <div onClick={(event) => event.stopPropagation()}>
        <Act order={order} />
      </div>
    ),
  },
]

export function OrdersPage() {
  const [params, setParams] = useSearchParams()

  // The bench queue is what this screen opens on — but an address bar that
  // arrives carrying a code or an order id is not somebody starting work, it
  // is somebody following a link, and the order at the end of it is very
  // rarely still in today's queue. Landing them on `placed` shows an empty
  // table for an order that exists, so a link opens the history instead.
  const [status, setStatus] = useState(() =>
    params.get("q") || params.get("buyurtma") ? "" : "placed",
  )
  const orders = useOrders(status)

  // The open order lives in the address bar, so the person on the telephone
  // can send a colleague the order itself rather than its code.
  const opened = Number(params.get("buyurtma")) || null
  const open = (id: number | null) => {
    const next = new URLSearchParams(params)
    if (id) next.set("buyurtma", String(id))
    else next.delete("buyurtma")
    setParams(next, { replace: true })
  }

  // **`OrderDetail` does not carry `next_statuses`; the queue row does.** So
  // the moves on the drawer are the row's own moves, looked up in the list
  // that is already in hand — not rules recomputed on the client, which would
  // be a second copy of the server's state machine drifting from the first.
  //
  // A link opened from elsewhere can land on an order the current tab does not
  // hold; then there is no row, and the drawer reads without offering a move
  // rather than guessing at one.
  const row = (orders.data?.items ?? []).find((order) => order.id === opened) ?? null

  return (
    <div className="space-y-4">
      {/* The filter lives in the header card rather than on the page under
          it. One band across the top of every screen — title on the left, the
          things that change what is below it on the right — is what makes
          eleven screens read as one application.

          It stays here rather than moving into the table's filter drawer:
          this is the *request*, not a narrowing of what came back, and a
          queue is a different list from a history. */}
      <PageHeader title="Buyurtmalar" subtitle="Navbat oldindan ishlanadi">
        <Segmented label="Holat" value={status} onChange={setStatus} options={TABS} />
      </PageHeader>

      <DataTable
        title="Buyurtmalar"
        rows={orders.data?.items ?? []}
        columns={COLUMNS}
        rowKey={(order) => order.id}
        loading={orders.isLoading}
        error={orders.error}
        onRowClick={(order) => open(order.id)}
        count={(n) => `${groups(n)} ta buyurtma`}
        searchPlaceholder="Kod, mijoz, manzil"
        search={(order) =>
          [
            order.code,
            order.customer_name,
            order.customer_phone,
            order.address_line,
            order.items_summary,
          ]
            .filter(Boolean)
            .join(" ")
        }
        empty={{
          icon: PackageCheck,
          title: "Bu yerda hech narsa yo'q",
          what: "Buyurtma telefonda yoki ilovada berilganda shu navbatga tushadi.",
        }}
      />

      <OrderSheet id={opened} row={row} onClose={() => open(null)} />
    </div>
  )
}

/**
 * What can be done to this order, in the server's own words.
 *
 * Its own component because every row holds two mutations of its own, and a
 * cell that owns state is a component whether or not it is written as one.
 * The drawer's footer renders the same thing, so the queue and the order are
 * never offering different moves.
 */
function Act({ order, wrap = false }: { order: StaffOrder; wrap?: boolean }) {
  const { staff } = useSession()
  const move = useMoveOrder(order.id)
  const build = useBuildPickTask()
  const [cancelling, setCancelling] = useState(false)

  // Putting an order on the pick board is the bench's own act, behind the
  // warehouse's door. The assistant on the telephone reads this queue and
  // moves an order along; they do not decide what a picker walks to next.
  const benched = staff?.role === "admin" || staff?.role === "warehouse"

  return (
    <div className="flex flex-col items-end gap-2">
      {/* In a table cell the buttons stay on one line — the column is sized to
          its content, so letting them wrap narrows the column, which makes
          them wrap again. In the drawer's footer, on a phone, they must fold. */}
      <div className={`flex justify-end gap-1 ${wrap ? "flex-wrap" : ""}`}>
        {order.status === "placed" && benched ? (
          <Button
            size="sm"
            variant="secondary"
            disabled={build.isPending}
            onClick={() => build.mutate(order.id)}
          >
            <PackageCheck />
            Terishga qo'yish
          </Button>
        ) : null}

        {order.next_statuses
          // The handover is the courier's own act, at a door. An office button
          // that marked a parcel shipped would be the office claiming somebody
          // else picked it up.
          .filter((next) => next !== "shipped")
          .map((next) =>
            next === "cancelled" ? (
              <Button
                key={next}
                size="sm"
                variant="ghost"
                className="text-danger hover:text-danger"
                disabled={move.isPending}
                onClick={() => setCancelling(true)}
              >
                {MOVE[next]}
              </Button>
            ) : (
              <Button
                key={next}
                size="sm"
                disabled={move.isPending}
                onClick={() => move.mutate({ status: next })}
              >
                {MOVE[next]}
              </Button>
            ),
          )}
      </div>

      {move.error || build.error ? (
        <Problem error={move.error || build.error} />
      ) : null}

      <CancelDialog
        order={order}
        open={cancelling}
        busy={move.isPending}
        onOpenChange={setCancelling}
        onCancel={(note) =>
          move.mutate({ status: "cancelled", note }, { onSuccess: () => setCancelling(false) })
        }
      />
    </div>
  )
}

/* ---------------------------------------------------------------- the order */

/**
 * One order, laid out for a telephone call.
 *
 * Not a form and not a record card: the questions come in the order they are
 * asked in that half-minute — *where is it*, *what is in it*, *what did they
 * pay*, and, when it has gone wrong, *who knocked, when, and what did they
 * say*. The last one is the reason this screen exists, so it is the panel
 * with room in it.
 */
function OrderSheet({
  id,
  row,
  onClose,
}: {
  id: number | null
  row: StaffOrder | null
  onClose: () => void
}) {
  const order = useOrder(id)
  const detail = order.data

  const failures = (detail?.attempts ?? []).filter((one) => one.result === "failed")

  return (
    <Sheet open={Boolean(id)} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent className="sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle className="tabular">{detail?.code ?? "Buyurtma"}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-2">
            {detail ? (
              <>
                <Pill tone={TONE[detail.status]}>{WORD[detail.status]}</Pill>
                {!detail.paid ? <Pill tone="warn">To'lanmagan</Pill> : null}
                {/* The knocks are at the bottom of a long drawer. If any of
                    them failed, the top of it says so, because that is the
                    fact the call is about. */}
                {failures.length ? (
                  <Pill tone="danger">
                    {groups(failures.length)} marta eshik ochilmadi
                  </Pill>
                ) : null}
                <span className="tabular">{dateTime(detail.created_at)}</span>
              </>
            ) : null}
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-4 bg-canvas">
          <Problem error={order.error} />
          {order.isLoading ? (
            <p className="text-small text-ink-soft">Yuklanmoqda…</p>
          ) : detail ? (
            <Detail order={detail} />
          ) : null}
        </SheetBody>

        {row ? (
          <SheetFooter className="[&>*]:flex-none">
            <Act order={row} wrap />
          </SheetFooter>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

function Detail({ order }: { order: OrderDetail }) {
  return (
    <>
      {/* 1. Where is it. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Timeline order={order} />
        <Whereabouts order={order} />
      </div>

      {/* 2. What is in it. */}
      <Panel title={`Nima bor · ${groups(order.items_count)} dona`} bare>
        {order.items.length === 0 ? (
          <Empty bare what="Bu buyurtmada bironta ham qator yo'q." />
        ) : (
          <ul className="divide-y divide-line">
            {order.items.map((item) => (
              <Line key={item.id} item={item} />
            ))}
          </ul>
        )}
      </Panel>

      {/* 3. What did they pay. */}
      <Money order={order} />

      {/* 4. Who knocked. */}
      <Attempts order={order} />
    </>
  )
}

/**
 * The four steps of the order's life, and which of them have happened.
 *
 * The rows are written blank at checkout, so `happened_at === null` means
 * *not reached yet* — not *missing*. A blank step drawn as an absence would
 * make a perfectly normal new order look broken.
 */
function Timeline({ order }: { order: OrderDetail }) {
  return (
    <Panel title="Qayerda">
      <ol className="space-y-0">
        {order.events.map((event, at) => {
          const last = at === order.events.length - 1
          const bad = event.status === "cancelled" || event.status === "returned"
          return (
            <li key={`${event.status}-${at}`} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={
                    event.done
                      ? `grid size-6 shrink-0 place-items-center rounded-full ${
                          bad ? "bg-danger text-danger-ink" : "bg-good text-good-ink"
                        }`
                      : "grid size-6 shrink-0 place-items-center rounded-full border border-line bg-surface"
                  }
                >
                  {event.done ? <Check className="size-3.5" /> : null}
                </span>
                {!last ? (
                  <span
                    className={`w-px flex-1 ${event.done ? "bg-good/40" : "bg-line"}`}
                  />
                ) : null}
              </div>

              <div className={`min-w-0 flex-1 ${last ? "pb-0" : "pb-4"}`}>
                <div
                  className={`text-small font-medium ${
                    event.done ? "text-ink" : "text-ink-faint"
                  }`}
                >
                  {event.title}
                </div>
                <div className="text-micro tabular text-ink-faint">
                  {event.happened_at ? dateTime(event.happened_at) : "hali emas"}
                </div>
                {event.note ? (
                  <p className="mt-1 text-micro text-ink-soft">{event.note}</p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>
    </Panel>
  )
}

/** Who it goes to, and where — the half of the call that is read out loud. */
function Whereabouts({ order }: { order: OrderDetail }) {
  // `delivery_start` / `delivery_end` are bare `HH:MM` strings, not instants —
  // running them through the date formatter yields an empty string and a
  // window that reads as a lone dash.
  const slot =
    order.delivery_start && order.delivery_end
      ? `${order.delivery_start}–${order.delivery_end}`
      : ""

  return (
    <Panel title="Kimga">
      <dl className="space-y-2.5">
        <Fact
          icon={Phone}
          name="Qabul qiluvchi"
          value={
            order.recipient_name || order.recipient_phone ? (
              <>
                <div>{order.recipient_name || "Ismi yozilmagan"}</div>
                <div className="tabular text-ink-soft">{order.recipient_phone}</div>
              </>
            ) : null
          }
        />
        <Fact
          icon={MapPin}
          name={order.delivery_kind === "pickup" ? "Topshirish punkti" : "Manzil"}
          value={
            order.address_line ? (
              <>
                <div>{order.address_line}</div>
                {order.address_meta ? (
                  <div className="text-ink-soft">{order.address_meta}</div>
                ) : null}
              </>
            ) : null
          }
        />
        {/* The label first, because it is the sentence the customer is
            looking at in their own app while they are on the telephone; the
            day and the window under it, for the colleague who has to write it
            down. */}
        <Fact
          icon={Package}
          name="Yetkazish"
          value={
            order.eta_label || order.delivery_day ? (
              <>
                {order.eta_label ? <div>{order.eta_label}</div> : null}
                {order.delivery_day ? (
                  <div className="tabular text-ink-soft">
                    {[date(order.delivery_day), slot].filter(Boolean).join(" · ")}
                  </div>
                ) : null}
              </>
            ) : null
          }
        />
      </dl>
    </Panel>
  )
}

/** One line of the order, at the price it was frozen at. */
function Line({ item }: { item: OrderItem }) {
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      {item.image_url ? (
        <img
          src={mediaUrl(item.image_url)}
          alt=""
          className="size-12 shrink-0 rounded-control object-cover"
        />
      ) : (
        <span className="grid size-12 shrink-0 place-items-center rounded-control bg-canvas text-ink-faint">
          <Package className="size-5" />
        </span>
      )}

      <div className="min-w-0 flex-1">
        <div className="truncate text-small font-medium">{item.title}</div>
        <div className="truncate text-micro text-ink-faint">
          {item.variant_label ||
            [item.colour, item.size].filter(Boolean).join(" · ") ||
            "O'lchamsiz"}
        </div>
      </div>

      {/* The price this line was sold at, not what the card says today. */}
      <div className="shrink-0 text-right">
        <div className="text-small font-semibold tabular">{money(item.line_total)}</div>
        <div className="text-micro tabular text-ink-faint">
          {groups(item.quantity)} × {groups(item.unit_price)}
        </div>
      </div>
    </li>
  )
}

/** What they paid, broken up — the row only ever had the total. */
function Money({ order }: { order: OrderDetail }) {
  return (
    <Panel
      title="Pul"
      aside={
        <span className="flex items-center gap-2">
          <span className="text-micro text-ink-soft">{order.payment_label}</span>
          <Pill tone={order.paid ? "good" : "warn"}>
            {order.paid ? "To'langan" : "To'lanmagan"}
          </Pill>
        </span>
      }
    >
      <dl className="space-y-1.5 text-small">
        <Row name="Tovarlar" value={money(order.subtotal)} />
        <Row name="Yetkazish" value={money(order.delivery_fee)} />
        {order.discount ? (
          <Row name="Chegirma" value={`−${money(order.discount)}`} tone="good" />
        ) : null}
        <div className="flex items-baseline justify-between border-t border-line pt-2">
          <dt className="font-medium">Jami</dt>
          <dd className="figure tabular">{money(order.total)}</dd>
        </div>
      </dl>
    </Panel>
  )
}

/**
 * Every knock at the door.
 *
 * Carried here and nowhere else. The courier's list has a *count*, and a
 * count cannot answer the question the office is actually asking — three
 * knocks at one wrong buzzer and three on three different days are the same
 * number and opposite decisions. So every attempt is a row with the name of
 * whoever went, what happened, what they were told, who took it, what cash
 * came back and the photograph, and a failure is drawn as a failure.
 */
function Attempts({ order }: { order: OrderDetail }) {
  const tried = order.attempts.length

  return (
    <Panel
      title="Eshik oldida"
      aside={
        tried ? (
          <span className="text-micro text-ink-soft">{groups(tried)} marta borilgan</span>
        ) : null
      }
      bare
    >
      {tried === 0 ? (
        // The quiet one-line empty rather than the house's big one: nobody
        // having knocked at a brand new order is the ordinary state, and a
        // headline with a glyph in the middle of a tall box would make the
        // longest panel in the drawer the one with nothing in it.
        <Empty
          bare
          what={
            order.delivery_kind === "pickup"
              ? "Bu buyurtma topshirish punktidan olinadi — eshik yo'q."
              : "Kuryer eshikni taqillatganda, har bir urinish shu yerga yoziladi."
          }
        />
      ) : (
        <ul className="divide-y divide-line">
          {order.attempts.map((attempt) => (
            <Knock key={attempt.id} attempt={attempt} />
          ))}
        </ul>
      )}
    </Panel>
  )
}

function Knock({ attempt }: { attempt: DeliveryAttempt }) {
  const failed = attempt.result === "failed"

  return (
    <li className={`flex gap-3 px-4 py-3 ${failed ? "bg-danger-soft" : ""}`}>
      {/* The colour is the first thing read, and it is on the left edge where
          a column of attempts can be scanned without reading any of them. */}
      <span
        className={`mt-0.5 w-1 shrink-0 self-stretch rounded-full ${
          failed ? "bg-danger" : "bg-good"
        }`}
      />

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={failed ? "danger" : "good"}>
            {failed ? "Topshirilmadi" : "Topshirildi"}
          </Pill>
          <span className="text-small font-medium">{attempt.courier_name}</span>
          <span className="text-micro tabular text-ink-faint">
            {dateTime(attempt.happened_at)}
          </span>
        </div>

        {/* What they were told at the door. On a failure this is the sentence
            somebody repeats down the telephone, so it is the biggest thing in
            the row rather than a caption under it. */}
        {failed ? (
          <p className="text-small text-danger">
            {attempt.reason || "Sabab yozilmagan"}
          </p>
        ) : null}

        <div
          className={`flex-wrap items-center gap-x-4 gap-y-1 text-micro text-ink-soft ${
            attempt.recipient_name || attempt.cash_collected ? "flex" : "hidden"
          }`}
        >
          {attempt.recipient_name ? (
            <span className="inline-flex items-center gap-1">
              <Check className="size-3.5" />
              {attempt.recipient_name} qabul qildi
            </span>
          ) : null}
          {attempt.cash_collected ? (
            <span className="inline-flex items-center gap-1 tabular">
              <Banknote className="size-3.5" />
              {money(attempt.cash_collected)} olindi
            </span>
          ) : null}
        </div>
      </div>

      {attempt.photo_url ? (
        <a
          href={mediaUrl(attempt.photo_url)}
          target="_blank"
          rel="noreferrer"
          className="shrink-0"
          title="Suratni ochish"
        >
          <img
            src={mediaUrl(attempt.photo_url)}
            alt="Eshik oldidagi surat"
            className="size-14 rounded-control object-cover"
          />
        </a>
      ) : null}
    </li>
  )
}

/* --------------------------------------------------------------- small parts */

function Fact({
  icon: Icon,
  name,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>
  name: string
  value: React.ReactNode
}) {
  return (
    <div className="flex gap-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-ink-faint" />
      <div className="min-w-0 flex-1">
        <dt className="text-micro text-ink-faint">{name}</dt>
        <dd className="text-small">{value ?? <span className="text-ink-faint">—</span>}</dd>
      </div>
    </div>
  )
}

function Row({ name, value, tone }: { name: string; value: string; tone?: "good" }) {
  return (
    <div className="flex items-baseline justify-between">
      <dt className="text-ink-soft">{name}</dt>
      <dd className={`tabular ${tone === "good" ? "text-good" : ""}`}>{value}</dd>
    </div>
  )
}

/* ------------------------------------------------------------- calling it off */

/**
 * Why it is being cancelled, asked properly.
 *
 * It was `window.prompt`, then a free-text box — and a sentence somebody
 * types is a sentence nobody can count. The shop has **five curated reasons**
 * in a table, translated, and the customer's own cancel button has been
 * sending them all along while the panel wrote prose into the same audit
 * trail beside them. Two cancel paths writing two different kinds of thing is
 * how "why do orders get called off" became a question with no answer.
 *
 * There is no `reason_id` on `POST /admin/orders/{id}/status`, so the label
 * goes as the `note`, joined to the comment the way the customer's path joins
 * them — `" · ".join(...)` in `routers/orders.py` — and the two paths land in
 * the journal as the same sentence.
 */
function CancelDialog({
  order,
  open,
  busy,
  onOpenChange,
  onCancel,
}: {
  order: StaffOrder
  open: boolean
  busy: boolean
  onOpenChange: (next: boolean) => void
  onCancel: (note: string) => void
}) {
  const reasons = useCancelReasons()
  const [chosen, setChosen] = useState<number | null>(null)
  const [comment, setComment] = useState("")

  const reason = (reasons.data ?? []).find((one) => one.id === chosen) ?? null
  const needsComment = Boolean(reason?.requires_comment)
  const ready = Boolean(reason) && (!needsComment || comment.trim().length > 0)

  const reset = () => {
    setChosen(null)
    setComment("")
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Buyurtmani bekor qilish</DialogTitle>
          <DialogDescription>
            {order.code} — sababi yozuvda qoladi.
          </DialogDescription>
        </DialogHeader>
        <DialogBody>
          <form
            id="cancel-order"
            onSubmit={(event) => {
              event.preventDefault()
              if (!reason || !ready) return
              // The same shape the customer's own cancel writes.
              onCancel(
                [reason.label, needsComment ? comment.trim() : ""]
                  .filter(Boolean)
                  .join(" · "),
              )
            }}
            className="space-y-3"
          >
            <fieldset className="space-y-1.5">
              <legend className="mb-1.5 text-small font-medium">
                Nega bekor qilinyapti?
              </legend>

              <Problem error={reasons.error} />
              {reasons.isLoading ? (
                <p className="text-small text-ink-soft">Yuklanmoqda…</p>
              ) : null}

              {(reasons.data ?? []).map((one) => {
                const picked = one.id === chosen
                return (
                  <label
                    key={one.id}
                    className={`flex cursor-pointer items-center gap-2.5 rounded-control border px-3 py-2 text-small transition-colors ${
                      picked
                        ? "border-brand bg-brand-soft text-ink"
                        : "border-line bg-surface hover:bg-line-soft"
                    }`}
                  >
                    <input
                      type="radio"
                      name="cancel-reason"
                      className="peer sr-only"
                      checked={picked}
                      onChange={() => {
                        setChosen(one.id)
                        if (!one.requires_comment) setComment("")
                      }}
                    />
                    <span
                      className={`grid size-4 shrink-0 place-items-center rounded-full border peer-focus-visible:ring-2 peer-focus-visible:ring-brand/45 ${
                        picked ? "border-brand" : "border-line"
                      }`}
                    >
                      {picked ? <span className="size-2 rounded-full bg-brand" /> : null}
                    </span>
                    {one.label}
                  </label>
                )
              })}
            </fieldset>

            {/* Only the reason that says it needs one asks for one. A comment
                box under every option is a box four people in five leave
                empty, which is how a required field stops meaning anything. */}
            {needsComment ? (
              <div className="space-y-1.5">
                <Label htmlFor="cancel-comment">Qisqacha izoh</Label>
                <Input
                  id="cancel-comment"
                  autoFocus
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="Nima bo'ldi?"
                />
              </div>
            ) : null}
          </form>
        </DialogBody>
        <DialogFooter showCloseButton>
          <Button
            type="submit"
            form="cancel-order"
            variant="danger"
            disabled={busy || !ready}
          >
            {/* Not "Bekor qilish": the footer's own dismiss button already
                says that, and two buttons reading the same word at opposite
                ends of a confirmation is the one place it must not happen. */}
            Ha, bekor qilinsin
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
