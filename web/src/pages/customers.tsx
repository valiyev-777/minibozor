/**
 * Mijozlar — the people who buy here, with what they are worth beside them.
 *
 * ------------------------------------------------------------------- why
 *
 * Customers appeared nowhere in this panel. They were half of the "Xodimlar"
 * list, which is how they got in, and there was no screen where anybody could
 * look one up. So the answer to "how many orders has this man had" was the
 * owner's memory, and the answer to "what is in her basket that she cannot
 * check out" was nothing at all.
 *
 * -------------------------------------------------------------- the table
 *
 * Four figures beside the name, because those are what somebody reaches for
 * before picking up the telephone: how often this person buys, what they have
 * actually paid for, when they last did, and whether they are still using the
 * app. `spent` is delivered orders only — a placed order is a promise and a
 * cancelled one is nothing, and counting either would make the shop's keenest
 * tyre-kicker its best customer.
 *
 * The three orderings are the server's and they are a control rather than
 * three sortable headers: "biggest spender" is a question about the whole
 * list, not about the column it happens to sort by, and a header arrow on
 * page one of forty would sort thirty rows.
 *
 * ------------------------------------------------------------- the drawer
 *
 * This is the screen somebody opens **while the customer is on the
 * telephone**, so it is laid out to be read in half a minute and not filled
 * in: the four figures first, then the last orders, then what is sitting in
 * the basket — which is the commonest call there is. Nothing here is
 * editable. The office does not correct a shopper's own address or card, and
 * a form would invite it.
 */

import { Link, useSearchParams } from "react-router-dom"
import {
  CreditCard,
  Heart,
  MapPin,
  Receipt,
  ShoppingBasket,
  Wallet,
} from "lucide-react"

import { DataTable, useTableState } from "@/components/data-table"
import {
  Empty,
  PageHeader,
  Panel,
  Pill,
  Problem,
  Segmented,
  Stat,
  type Tone,
} from "@/components/page"
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { date, dateTime, groups, money } from "@/lib/format"
import { useCustomer, useCustomers } from "@/lib/queries"
import type { CustomerDetail, CustomerRow, OrderStatus } from "@/lib/types"

const ORDERINGS: Array<{ key: string; label: string }> = [
  { key: "recent", label: "Yangi" },
  { key: "spend", label: "Ko'p sarflagan" },
  { key: "orders", label: "Ko'p buyurtma" },
]

/** The same five meanings the rest of the app uses: green happened, red did
 *  not, amber not yet, blue is where the thing is now. */
const ORDER_TONE: Record<OrderStatus, Tone> = {
  placed: "brand",
  packing: "warn",
  shipped: "brand",
  delivered: "good",
  cancelled: "danger",
  returned: "danger",
}

export function CustomersPage() {
  const state = useTableState()
  const [params, setParams] = useSearchParams()
  const ordering = state.filter("ordering") || "recent"

  const customers = useCustomers({
    q: state.q,
    ordering,
    page: state.page,
    size: state.size,
  })

  // The open customer lives in the address bar, so the person who found them
  // can send the link to whoever picks up next.
  const opened = Number(params.get("mijoz")) || null
  const open = (id: number | null) => {
    const next = new URLSearchParams(params)
    if (id) next.set("mijoz", String(id))
    else next.delete("mijoz")
    setParams(next, { replace: true })
  }

  return (
    <div>
      <PageHeader title="Mijozlar" subtitle="Shu yerdan xarid qiladiganlar" />

      <DataTable<CustomerRow>
        title="Mijozlar"
        rows={customers.data?.items ?? []}
        total={customers.data?.total}
        loading={customers.isLoading}
        error={customers.error}
        rowKey={(row) => row.id}
        onRowClick={(row) => open(row.id)}
        count={(n) => `${groups(n)} ta mijoz`}
        searchPlaceholder="Ism yoki raqam"
        empty={{
          icon: Receipt,
          title: "Mijoz topilmadi",
          what: "Mijoz ilovadan ro'yxatdan o'tganda shu yerda paydo bo'ladi.",
        }}
        beforeSearch={
          <Segmented
            label="Tartibi"
            value={ordering}
            onChange={(next) => state.setFilter("ordering", next)}
            options={ORDERINGS.map((one) => ({ key: one.key, label: one.label }))}
          />
        }
        columns={[
          {
            key: "person",
            header: "Mijoz",
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate font-medium">
                  {row.full_name || "Ismi yozilmagan"}
                </div>
                <div className="truncate text-micro tabular text-ink-soft">
                  {row.phone}
                </div>
              </div>
            ),
          },
          {
            key: "orders_count",
            header: "Buyurtma",
            numeric: true,
            width: "1%",
            cell: (row) =>
              row.orders_count ? (
                groups(row.orders_count)
              ) : (
                <span className="text-ink-faint">0</span>
              ),
          },
          {
            key: "spent",
            header: "Sarflagan",
            numeric: true,
            width: "1%",
            cell: (row) =>
              row.spent ? (
                <span className="whitespace-nowrap font-medium">{money(row.spent)}</span>
              ) : (
                <span className="text-ink-faint">—</span>
              ),
          },
          {
            key: "last_order",
            header: "So'nggi buyurtma",
            width: "1%",
            cell: (row) =>
              row.last_order_at ? (
                <span className="whitespace-nowrap tabular">{date(row.last_order_at)}</span>
              ) : (
                <span className="text-micro text-ink-faint">Hech qachon</span>
              ),
          },
          {
            key: "seen",
            header: "Seansi",
            width: "1%",
            align: "end",
            cell: (row) =>
              row.last_seen ? (
                <Pill tone="good">Tizimda</Pill>
              ) : (
                <span className="text-micro text-ink-faint">Kirmagan</span>
              ),
          },
        ]}
      />

      <CustomerSheet id={opened} onClose={() => open(null)} />
    </div>
  )
}

/* --------------------------------------------------------------- the drawer */

function CustomerSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const customer = useCustomer(id)

  return (
    <Sheet open={Boolean(id)} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent className="sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle>
            {customer.data
              ? customer.data.full_name || "Ismi yozilmagan"
              : "Mijoz"}
          </SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-2">
            <span className="tabular">{customer.data?.phone ?? ""}</span>
            {customer.data && !customer.data.is_active ? (
              <Pill tone="danger">Hisob o'chirilgan</Pill>
            ) : null}
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-4 bg-canvas">
          <Problem error={customer.error} />
          {customer.isLoading ? (
            <p className="text-small text-ink-soft">Yuklanmoqda…</p>
          ) : customer.data ? (
            <Profile customer={customer.data} />
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}

/**
 * Everything about one person, in the order it gets read.
 *
 * The figures first — they are the sentence somebody says back down the
 * telephone. Then the orders, because the call is nearly always about one of
 * them. Then the basket, because the second commonest call is about a line
 * that will not check out. The addresses and the cards are facts somebody
 * reads out loud when asked, so they are last and they are plain.
 */
function Profile({ customer }: { customer: CustomerDetail }) {
  const basket = customer.cart.reduce((sum, line) => sum + line.line_total, 0)

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat
          label="Buyurtma"
          value={groups(customer.orders_count)}
          hint={
            customer.last_order_at
              ? `So'nggisi ${date(customer.last_order_at)}`
              : "Hali yo'q"
          }
          icon={Receipt}
          tone="brand"
        />
        <Stat
          label="Sarflagan"
          value={money(customer.spent)}
          hint="Yetkazilgan buyurtmalar"
          icon={Wallet}
          tone="good"
        />
        <Stat
          label="Savatda"
          value={money(basket)}
          hint={`${groups(customer.cart.length)} ta qator`}
          icon={ShoppingBasket}
          tone={customer.cart.length ? "warn" : "neutral"}
        />
        <Stat
          label="Sevimlilar"
          value={groups(customer.favorites_count)}
          hint={customer.last_seen ? "Ilovadan foydalanmoqda" : "Ilovaga kirmagan"}
          icon={Heart}
        />
      </div>

      <Panel title="Hisobi">
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Fact name="Telefon" value={<span className="tabular">{customer.phone}</span>} />
          <Fact name="Elektron pochta" value={customer.email || null} />
          <Fact
            name="Ro'yxatdan o'tgan"
            value={<span className="tabular">{date(customer.created_at)}</span>}
          />
          <Fact
            name="Tug'ilgan kuni"
            value={
              customer.birth_date ? (
                <span className="tabular">{date(customer.birth_date)}</span>
              ) : null
            }
          />
          <Fact name="Ilova tili" value={customer.language?.toUpperCase() || null} />
          <Fact
            name="Seansi"
            value={
              customer.last_seen ? (
                <span className="tabular">{dateTime(customer.last_seen)} dan beri</span>
              ) : null
            }
          />
        </dl>
      </Panel>

      <Panel title="So'nggi buyurtmalari" bare>
        {customer.orders.length === 0 ? (
          <Empty bare what="Hali hech narsa buyurtma qilmagan." />
        ) : (
          <ul className="divide-y divide-line">
            {customer.orders.map((order) => (
              <li key={order.id}>
                {/* The order queue is where an order is worked on, so the
                    code is a way through to it rather than a second,
                    read-only copy of the same row. */}
                <Link
                  to={`/buyurtmalar?q=${encodeURIComponent(order.code)}`}
                  className="flex flex-wrap items-center gap-3 px-4 py-2.5 transition-colors hover:bg-line-soft"
                >
                  <span className="w-28 shrink-0 text-small font-medium tabular">
                    {order.code}
                  </span>
                  <Pill tone={ORDER_TONE[order.status]}>{order.status_label}</Pill>
                  <span className="flex-1 text-micro tabular text-ink-soft">
                    {dateTime(order.created_at)}
                  </span>
                  <span className="text-small font-medium tabular">
                    {money(order.total)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title="Savatda hozir"
        aside={
          customer.cart.length ? (
            <span className="text-small font-medium tabular">{money(basket)}</span>
          ) : null
        }
        bare
      >
        {customer.cart.length === 0 ? (
          <Empty bare what="Savati bo'sh." />
        ) : (
          <ul className="divide-y divide-line">
            {customer.cart.map((line) => (
              <li key={line.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-small font-medium">
                    {line.title}
                  </span>
                  <span className="block truncate text-micro text-ink-soft">
                    {line.variant_label} · {groups(line.quantity)} dona
                  </span>
                </span>
                {/* Why a line will not check out, worked out by the server
                    the same way the shopper's own screen works it out — so
                    the office and the customer are looking at one answer. */}
                {line.in_stock ? null : <Pill tone="danger">Tugagan</Pill>}
                <span className="text-small tabular">{money(line.line_total)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Manzillari" bare>
          {customer.addresses.length === 0 ? (
            <Empty bare what="Manzil saqlamagan." />
          ) : (
            <ul className="divide-y divide-line">
              {customer.addresses.map((address) => (
                <li key={address.id} className="flex gap-3 px-4 py-2.5">
                  <MapPin className="mt-0.5 size-4 shrink-0 text-ink-faint" />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-small font-medium">{address.title}</span>
                      {address.is_default ? <Pill tone="brand">Asosiy</Pill> : null}
                    </div>
                    <div className="text-micro text-ink-soft">{address.line}</div>
                    {address.meta ? (
                      <div className="text-micro text-ink-faint">{address.meta}</div>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Kartalari" bare>
          {customer.cards.length === 0 ? (
            <Empty bare what="Karta saqlamagan." />
          ) : (
            <ul className="divide-y divide-line">
              {customer.cards.map((card) => (
                <li key={card.id} className="flex items-center gap-3 px-4 py-2.5">
                  <CreditCard className="size-4 shrink-0 text-ink-faint" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-small font-medium tabular">
                      {card.brand} ···· {card.last4}
                    </span>
                    <span className="block text-micro tabular text-ink-soft">
                      {card.expiry}
                    </span>
                  </span>
                  {card.is_default ? <Pill tone="brand">Asosiy</Pill> : null}
                  {card.status === "active" ? (
                    <Pill tone="good">Ishlaydi</Pill>
                  ) : card.status === "expired" ? (
                    <Pill tone="warn">Muddati o'tgan</Pill>
                  ) : (
                    <Pill tone="danger">Bloklangan</Pill>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  )
}

/** One fact from a profile: a quiet name and the thing itself. An em dash
 *  where there is nothing, so a missing email reads as missing rather than
 *  as a row that failed to draw. */
function Fact({ name, value }: { name: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3">
      <dt className="shrink-0 text-micro text-ink-soft">{name}</dt>
      <dd className="min-w-0 truncate text-small">
        {value || <span className="text-ink-faint">—</span>}
      </dd>
    </div>
  )
}
