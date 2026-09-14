/**
 * Yetkazish oynalari — a fortnight of delivery windows, seen from the office.
 *
 * **A calendar, not a table.** The question this screen is opened with is not
 * "list every window" — it is *"is Saturday evening full again?"*, and that
 * is a question about the shape of a week. A flat table sorted by day answers
 * it only by scrolling and counting; seven columns with the weekdays lined up
 * answers it by looking down one column. Two rows of seven is the fortnight
 * the endpoint's own default covers. Below a wide desk the columns fold down
 * into one chronological list, because on a phone the alignment is worth
 * nothing and the width is worth everything.
 *
 * **`capacity_left` is what is left, not the size of the window.** There is
 * no total anywhere in the API, so this screen never draws a fill bar and
 * never writes "12 of 20 taken" — it would be inventing the 20. It says how
 * many seats remain, and it says nothing else about the window's size.
 *
 * **A sold-out window is visible only here.** Checkout does not refuse a full
 * window, it decrements and declines to go below zero; what actually stops
 * over-booking is the customer's app hiding what it cannot sell. So the
 * evening window that has gone red on this grid has *disappeared* from the
 * shop, and the whole point of the screen is to notice that and either raise
 * its seats or open another window beside it.
 *
 * **An empty day is not an empty day.** When a customer asks about a day that
 * has no windows at all, the server invents three standard ones (09–13,
 * 13–18, 18–21, free, twenty seats). The admin list does not do this — so a
 * blank Thursday here is a Thursday that will quietly fill itself the moment
 * somebody looks at it in the shop. An owner who plans a week around a blank
 * column and then finds it populated stops trusting the screen, so every
 * blank future day says so on its own face.
 */

import {
  CalendarDays,
  CalendarPlus,
  ChevronLeft,
  ChevronRight,
  Info,
  Loader2,
  Plus,
  Trash2,
  Zap,
} from "lucide-react"
import { useMemo, useState } from "react"

import { PageHeader, Panel, Pill, Problem, Stat, type Tone } from "@/components/page"
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
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import { useCreateSlots, useSlots, useUpdateSlot } from "@/lib/queries"
import type { StaffSlot } from "@/lib/types"

/** Monday first, the way a week is read here. */
const WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
const WEEKDAYS_LONG = [
  "Dushanba",
  "Seshanba",
  "Chorshanba",
  "Payshanba",
  "Juma",
  "Shanba",
  "Yakshanba",
]

/** Two weeks — the same span the endpoint defaults to. */
const FORTNIGHT = 14

/** The three the server itself opens on an empty day, so "the usual" is one
 *  press rather than six fields typed from memory. */
const STANDARD = [
  { start_time: "09:00", end_time: "13:00", note: "Ertalab", price: 0, express: false, capacity: 20 },
  { start_time: "13:00", end_time: "18:00", note: "Kunduzi", price: 0, express: false, capacity: 20 },
  { start_time: "18:00", end_time: "21:00", note: "Kechqurun", price: 0, express: false, capacity: 20 },
]

export function SlotsPage() {
  // Which fortnight, counted from the one that starts today. Backwards is
  // allowed and shows the past — this list carries the days the customer's
  // one never would.
  const [step, setStep] = useState(0)
  const [opening, setOpening] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)

  const days = useMemo(() => fortnightFrom(step), [step])
  const fromDay = key(days[0])
  const toDay = key(days[days.length - 1])
  const today = key(new Date())

  const slots = useSlots(fromDay, toDay)

  const byDay = useMemo(() => {
    const out = new Map<string, StaffSlot[]>()
    for (const slot of slots.data ?? []) {
      const list = out.get(slot.day) ?? []
      list.push(slot)
      out.set(slot.day, list)
    }
    for (const list of out.values()) list.sort((a, b) => a.start_time.localeCompare(b.start_time))
    return out
  }, [slots.data])

  const all = slots.data ?? []
  const soldOut = all.filter((slot) => slot.capacity_left === 0).length
  const seats = all.reduce((sum, slot) => sum + slot.capacity_left, 0)
  const express = all.filter((slot) => slot.express).length
  // Only days still ahead: the server fills a day when somebody asks about
  // it, and nobody asks about last Tuesday.
  const blank = days.filter((day) => key(day) >= today && !byDay.has(key(day))).length

  return (
    <div className="space-y-4">
      <PageHeader
        title="Yetkazish oynalari"
        subtitle={`${human(days[0])} — ${human(days[days.length - 1])}`}
      >
        <div className="flex items-center gap-1">
          <Button
            variant="secondary"
            size="icon"
            aria-label="Oldingi ikki hafta"
            onClick={() => setStep((was) => was - 1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={step === 0}
            onClick={() => setStep(0)}
          >
            Bugun
          </Button>
          <Button
            variant="secondary"
            size="icon"
            aria-label="Keyingi ikki hafta"
            onClick={() => setStep((was) => was + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
        <Button className="gap-2" onClick={() => setOpening(true)}>
          <CalendarPlus />
          Oyna ochish
        </Button>
      </PageHeader>

      <Problem error={slots.error} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Tugagan oyna"
          value={groups(soldOut)}
          hint="mijozga ko'rinmaydi"
          icon={CalendarDays}
          tone={soldOut > 0 ? "danger" : "neutral"}
        />
        <Stat
          label="Oynasiz kun"
          value={groups(blank)}
          hint="so'ralganda o'zi ochiladi"
          icon={Info}
          tone={blank > 0 ? "warn" : "neutral"}
        />
        <Stat label="Qolgan o'rin" value={groups(seats)} hint="shu ikki haftada" />
        <Stat label="Tezkor oyna" value={groups(express)} hint="qo'shimcha haqli" />
      </div>

      <Panel
        title="Ikki hafta"
        bare
        aside={
          <span className="text-micro text-ink-soft">
            {slots.isLoading ? "Yuklanmoqda…" : `${all.length} ta oyna`}
          </span>
        }
      >
        {/* The weekday strip only exists where the columns line up under it. */}
        <div className="hidden grid-cols-7 gap-2 px-4 pt-4 xl:grid">
          {WEEKDAYS.map((name, at) => (
            <div
              key={name}
              className="text-micro font-medium text-ink-soft"
              title={WEEKDAYS_LONG[at]}
            >
              {name}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 items-start gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-7">
          {/* Leading blanks so the first day sits under its own weekday. They
              exist only in the seven-column layout; in a folded list they
              would be three empty cards at the top. */}
          {Array.from({ length: weekday(days[0]) }, (_, at) => (
            <div key={`pad-${at}`} className="hidden xl:block" aria-hidden />
          ))}

          {days.map((day) => (
            <Day
              key={key(day)}
              day={day}
              today={today}
              slots={byDay.get(key(day)) ?? []}
              editing={editing}
              onEdit={setEditing}
              loading={slots.isLoading}
            />
          ))}
        </div>

        {/* The two facts a person cannot get from the grid by looking at it,
            and both of them change what the grid means. */}
        <div className="space-y-1 border-t border-line px-4 py-3 text-micro text-ink-soft">
          <p>
            <span className="font-medium text-danger">Tugagan</span> oyna do'konda
            umuman ko'rinmaydi — buyurtma uni rad etmaydi, ilova uni yashiradi. Uni
            faqat shu ekran ko'radi: o'rin qo'shing yoki yoniga yangi oyna oching.
          </p>
          <p>
            Butunlay <span className="font-medium">bo'sh kun</span> bo'sh qolmaydi:
            mijoz o'sha kunni so'rasa, tizim 09:00–13:00, 13:00–18:00 va 18:00–21:00
            oynalarini (bepul, 20 o'rin) o'zi ochib beradi. Bu ro'yxat ularni oldindan
            ko'rsatmaydi.
          </p>
        </div>
      </Panel>

      <OpenWindows open={opening} onClose={() => setOpening(false)} days={days} />
    </div>
  )
}

/* ------------------------------------------------------------------ one day */

function Day({
  day,
  today,
  slots,
  editing,
  onEdit,
  loading,
}: {
  day: Date
  today: string
  slots: StaffSlot[]
  editing: number | null
  onEdit: (id: number | null) => void
  loading: boolean
}) {
  const id = key(day)
  const past = id < today
  const isToday = id === today

  return (
    <section
      className={cn(
        "rounded-panel border p-2",
        isToday ? "border-brand bg-brand-soft/40" : "border-line bg-canvas/60",
        // A day with nothing on it should read as a gap in the fortnight, not
        // as a card somebody has to inspect.
        slots.length === 0 && !isToday && "border-dashed bg-transparent",
        past && "opacity-60",
      )}
    >
      <header className="mb-1.5 flex items-baseline justify-between gap-2 px-1">
        <h3 className="text-small font-semibold tabular">
          {day.getDate()}.{pad(day.getMonth() + 1)}
        </h3>
        <span className="text-micro text-ink-soft xl:hidden">
          {WEEKDAYS_LONG[weekday(day)]}
        </span>
        {past ? <span className="hidden text-micro text-ink-faint xl:inline">o'tdi</span> : null}
      </header>

      {slots.length === 0 ? (
        /* A blank day is blank in two different ways, and the difference is
           the whole warning: a past one stayed blank, a future one will not. */
        <p className="rounded-control px-2 py-2 text-micro text-ink-soft">
          {loading ? "…" : past ? "Oyna bo'lmagan" : "Oyna yo'q — so'ralganda o'zi ochiladi"}
        </p>
      ) : (
        <ul className="space-y-1">
          {slots.map((slot) =>
            editing === slot.id ? (
              <li key={slot.id}>
                <SlotEditor slot={slot} onDone={() => onEdit(null)} />
              </li>
            ) : (
              <li key={slot.id}>
                <SlotRow slot={slot} onEdit={() => onEdit(slot.id)} />
              </li>
            ),
          )}
        </ul>
      )}
    </section>
  )
}

/** Hours, the wording the customer reads, the surcharge, express — and what
 *  is left, which is the only number here that is true on its own. */
function SlotRow({ slot, onEdit }: { slot: StaffSlot; onEdit: () => void }) {
  const empty = slot.capacity_left === 0
  return (
    <button
      type="button"
      onClick={onEdit}
      className={cn(
        "w-full rounded-control border px-2 py-1.5 text-start transition-colors",
        empty
          ? "border-danger/30 bg-danger-soft hover:border-danger/50"
          : "border-transparent bg-surface hover:border-line hover:bg-line-soft",
      )}
    >
      {/* Wrapping rather than shrinking: in a seven-column week the pill and
          the hours do not both fit, and a delivery window broken across two
          lines mid-time («09:00–\n13:00») is the one thing on the card that
          must stay readable at a glance. */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-1.5">
        <span className="whitespace-nowrap text-small font-medium tabular">
          {slot.start_time}–{slot.end_time}
        </span>
        <Pill tone={seatTone(slot.capacity_left)}>
          {empty ? "Tugagan" : `${groups(slot.capacity_left)} o'rin`}
        </Pill>
      </div>
      <div className="truncate text-micro text-ink-soft">{slot.note || "Izohsiz"}</div>
      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-micro">
        {slot.price > 0 ? (
          <span className="font-medium tabular text-ink">+{money(slot.price)}</span>
        ) : (
          <span className="text-ink-faint">Bepul</span>
        )}
        {slot.express ? (
          <Pill tone="brand">
            <Zap className="size-3" />
            Tezkor
          </Pill>
        ) : null}
      </div>
    </button>
  )
}

/**
 * The same row, become editable where it stands.
 *
 * In place rather than in a modal because the thing being changed is one
 * number in one square of a grid, and the reason for changing it — the two
 * red windows either side of it — is on the screen behind any modal that
 * would open over it.
 *
 * Only what moved is sent: the PATCH treats an absent field as "leave it",
 * so an untouched surcharge is not re-posted as the same number and does not
 * land in the audit trail as a change.
 */
function SlotEditor({ slot, onDone }: { slot: StaffSlot; onDone: () => void }) {
  const save = useUpdateSlot(slot.id)
  const [seats, setSeats] = useState(String(slot.capacity_left))
  const [price, setPrice] = useState(String(slot.price))
  const [note, setNote] = useState(slot.note)
  const [express, setExpress] = useState(slot.express)

  const seatsNumber = Number(seats)
  const priceNumber = Number(price)
  const broken =
    !Number.isInteger(seatsNumber) ||
    seatsNumber < 0 ||
    !Number.isInteger(priceNumber) ||
    priceNumber < 0

  const changes = {
    ...(seatsNumber !== slot.capacity_left ? { capacity_left: seatsNumber } : {}),
    ...(priceNumber !== slot.price ? { price: priceNumber } : {}),
    ...(note !== slot.note ? { note } : {}),
    ...(express !== slot.express ? { express } : {}),
  }
  const moved = Object.keys(changes).length > 0

  return (
    <form
      className="space-y-2 rounded-control border border-brand bg-surface p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (!moved || broken) return
        save.mutate(changes, { onSuccess: onDone })
      }}
    >
      <div className="text-small font-medium tabular">
        {slot.start_time}–{slot.end_time}
      </div>

      <label className="block">
        <span className="mb-1 block text-micro font-medium text-ink-soft">
          Qolgan o'rin
        </span>
        <div className="flex items-center gap-1">
          <Input
            value={seats}
            onChange={(event) => setSeats(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            className="h-control-sm"
            aria-invalid={!Number.isInteger(seatsNumber) || seatsNumber < 0}
          />
          {/* The act this screen exists for is "that evening is full, give it
              more" — two presses rather than a cursor into a field. */}
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setSeats(String(Math.max(0, seatsNumber || 0) + 5))}
          >
            +5
          </Button>
        </div>
      </label>

      <label className="block">
        <span className="mb-1 block text-micro font-medium text-ink-soft">
          Ustama (so'm)
        </span>
        <Input
          value={price}
          onChange={(event) => setPrice(event.target.value.replace(/\D/g, ""))}
          inputMode="numeric"
          className="h-control-sm"
        />
      </label>

      <label className="block">
        {/* Short, because this label lives in one square of a seven-column
            week. That the customer reads it is said in the form that writes
            windows, where there is room for the sentence. */}
        <span className="mb-1 block text-micro font-medium text-ink-soft">Izoh</span>
        <Input
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={80}
          placeholder="Kechqurun"
          className="h-control-sm"
        />
      </label>

      <Toggle on={express} onChange={setExpress} label="Tezkor" />

      <Problem error={save.error} />

      <div className="flex gap-1">
        <Button
          type="submit"
          size="sm"
          className="flex-1"
          disabled={!moved || broken || save.isPending}
        >
          {save.isPending ? <Loader2 className="animate-spin" /> : null}
          Saqlash
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          Bekor
        </Button>
      </div>
    </form>
  )
}

/* ----------------------------------------------------------- opening windows */

type Draft = {
  start_time: string
  end_time: string
  note: string
  price: number
  express: boolean
  capacity: number
}

/**
 * Several days at once, because that is what the endpoint is for.
 *
 * A day at a time is four calls a day and twenty-eight to fill a fortnight,
 * which is how a shop runs out of windows. Days times windows, and the call
 * is idempotent per day and hours — so "top up the next fortnight" can be
 * pressed again tomorrow without doubling anything, and **an answer of
 * nothing is a success**: it means every window asked for already existed.
 * Said in those words, because an empty answer that looks like a failure is
 * the one that gets pressed four more times.
 */
function OpenWindows({
  open,
  onClose,
  days,
}: {
  open: boolean
  onClose: () => void
  days: Date[]
}) {
  const create = useCreateSlots()
  const [from, setFrom] = useState(key(days[0]))
  const [to, setTo] = useState(key(days[days.length - 1]))
  const [weekdays, setWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6])
  const [windows, setWindows] = useState<Draft[]>(() => STANDARD.map((one) => ({ ...one })))
  const [made, setMade] = useState<number | null>(null)

  const chosen = useMemo(() => daysBetween(from, to).filter((day) => weekdays.includes(weekday(day))), [from, to, weekdays])

  const badTime = windows.some(
    (one) => !HOURS.test(one.start_time) || !HOURS.test(one.end_time) || one.end_time <= one.start_time,
  )
  const nothing = chosen.length === 0 || windows.length === 0

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setMade(null)
          create.reset()
          onClose()
        }
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Oyna ochish</DialogTitle>
          <DialogDescription>
            Tanlangan kunlarning har biriga quyidagi oynalar ochiladi. Allaqachon shu
            soatlarda oynasi bor kun o'zgarishsiz qoladi.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-micro font-medium text-ink-soft">
                Qaysi kundan
              </span>
              <Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
            </label>
            <label className="block">
              <span className="mb-1 block text-micro font-medium text-ink-soft">
                Qaysi kungacha
              </span>
              <Input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
            </label>
          </div>

          <div>
            <span className="mb-1 block text-micro font-medium text-ink-soft">
              Hafta kunlari
            </span>
            <div className="flex flex-wrap gap-1">
              {WEEKDAYS.map((name, at) => (
                <button
                  key={name}
                  type="button"
                  aria-pressed={weekdays.includes(at)}
                  onClick={() =>
                    setWeekdays((was) =>
                      was.includes(at) ? was.filter((one) => one !== at) : [...was, at],
                    )
                  }
                  className={cn(
                    "h-control-sm rounded-control px-3 text-small transition-colors",
                    weekdays.includes(at)
                      ? "bg-brand text-brand-ink"
                      : "bg-line-soft text-ink-soft hover:text-ink",
                  )}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-micro font-medium text-ink-soft">Oynalar</span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="gap-1"
                onClick={() =>
                  setWindows((was) => [
                    ...was,
                    { start_time: "18:00", end_time: "21:00", note: "", price: 0, express: false, capacity: 20 },
                  ])
                }
              >
                <Plus />
                Yana oyna
              </Button>
            </div>

            {/* The two numeric fields at the end are a seat count and a sum of
                money, and nothing in a bare box says which is which. */}
            <div className="hidden gap-2 px-2 text-micro text-ink-soft sm:grid sm:grid-cols-[auto_auto_1fr_auto_auto]">
              <span className="w-24">Boshlanishi</span>
              <span className="w-24">Tugashi</span>
              <span>Izoh</span>
              <span className="w-20">O'rin</span>
              <span className="w-28">Ustama</span>
            </div>

            <ul className="space-y-2">
              {windows.map((one, at) => {
                const bad =
                  !HOURS.test(one.start_time) ||
                  !HOURS.test(one.end_time) ||
                  one.end_time <= one.start_time
                const patch = (changes: Partial<Draft>) =>
                  setWindows((was) => was.map((w, i) => (i === at ? { ...w, ...changes } : w)))
                return (
                  <li
                    key={at}
                    className={cn(
                      "rounded-control border p-2",
                      bad ? "border-danger bg-danger-soft" : "border-line bg-line-soft/50",
                    )}
                  >
                    <div className="grid gap-2 sm:grid-cols-[auto_auto_1fr_auto_auto]">
                      <Input
                        value={one.start_time}
                        onChange={(event) => patch({ start_time: clock(event.target.value) })}
                        inputMode="numeric"
                        maxLength={5}
                        placeholder="09:00"
                        className="w-24 bg-surface"
                        aria-label="Boshlanishi"
                      />
                      <Input
                        value={one.end_time}
                        onChange={(event) => patch({ end_time: clock(event.target.value) })}
                        inputMode="numeric"
                        maxLength={5}
                        placeholder="13:00"
                        className="w-24 bg-surface"
                        aria-label="Tugashi"
                      />
                      <Input
                        value={one.note}
                        onChange={(event) => patch({ note: event.target.value })}
                        maxLength={80}
                        placeholder="Izoh — mijoz o'qiydi"
                        className="bg-surface"
                        aria-label="Izoh"
                      />
                      <Input
                        value={String(one.capacity)}
                        onChange={(event) =>
                          patch({ capacity: Number(event.target.value.replace(/\D/g, "")) || 0 })
                        }
                        inputMode="numeric"
                        className="w-20 bg-surface"
                        aria-label="O'rin"
                      />
                      <Input
                        value={String(one.price)}
                        onChange={(event) =>
                          patch({ price: Number(event.target.value.replace(/\D/g, "")) || 0 })
                        }
                        inputMode="numeric"
                        className="w-28 bg-surface"
                        aria-label="Ustama"
                      />
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <Toggle
                        on={one.express}
                        onChange={(next) => patch({ express: next })}
                        label="Tezkor"
                      />
                      <div className="flex items-center gap-2">
                        <span className="text-micro text-ink-faint">
                          {one.capacity} o'rin ·{" "}
                          {one.price > 0 ? `+${money(one.price)}` : "bepul"}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          aria-label="Oynani olib tashlash"
                          disabled={windows.length === 1}
                          onClick={() => setWindows((was) => was.filter((_, i) => i !== at))}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </div>
                    {bad ? (
                      <p className="mt-1 text-micro text-danger">
                        Soat 09:00 ko'rinishida bo'lsin va tugashi boshlanishidan keyin
                        bo'lsin.
                      </p>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </div>

          <Problem error={create.error} />

          {made === null ? null : made === 0 ? (
            <p className="rounded-control bg-line-soft p-3 text-small text-ink-soft">
              Yangi oyna qo'shilmadi — tanlangan kunlarda bu soatlar allaqachon ochiq
              edi. Bu xato emas.
            </p>
          ) : (
            <p className="rounded-control bg-good-soft p-3 text-small text-good">
              {groups(made)} ta oyna ochildi.
            </p>
          )}
        </DialogBody>

        <DialogFooter showCloseButton>
          <Button
            disabled={nothing || badTime || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  days: chosen.map(key),
                  windows: windows.map((one) => ({
                    start_time: one.start_time,
                    end_time: one.end_time,
                    note: one.note,
                    price: one.price,
                    express: one.express,
                    capacity: one.capacity,
                  })),
                },
                { onSuccess: (made_) => setMade(made_.length) },
              )
            }
          >
            {create.isPending ? <Loader2 className="animate-spin" /> : null}
            {nothing
              ? "Kun tanlanmagan"
              : `${chosen.length} kun × ${windows.length} oyna`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* --------------------------------------------------------------- small parts */

/** A switch, spelled as a pressed button: the app has no checkbox and a
 *  two-state chip is the same object the filters already use. */
function Toggle({
  on,
  onChange,
  label,
}: {
  on: boolean
  onChange: (next: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      className={cn(
        "inline-flex h-control-sm items-center gap-1.5 whitespace-nowrap rounded-control px-2 text-micro font-medium transition-colors",
        on ? "bg-brand-soft text-brand-deep" : "bg-line-soft text-ink-soft hover:text-ink",
      )}
    >
      <Zap className={cn("size-3.5", on ? "text-brand" : "text-ink-faint")} />
      {label}
    </button>
  )
}

const HOURS = /^([01]\d|2[0-3]):[0-5]\d$/

/**
 * Keystrokes into a 24-hour time.
 *
 * Not `<input type="time">`: the native control follows the *browser's*
 * locale and offers «9:00 PM» on a machine set to English, which is not how
 * a delivery window is written here or anywhere else in this app — and its
 * AM/PM spinner does not fit the column either. Digits, with the colon put
 * in after two of them, which is also what the server's pattern wants.
 */
function clock(typed: string): string {
  const digits = typed.replace(/\D/g, "").slice(0, 4)
  return digits.length <= 2 ? digits : `${digits.slice(0, 2)}:${digits.slice(2)}`
}

/** Nought is the news, and three left on a Saturday evening is nearly the
 *  news. Anything else is just a number. */
function seatTone(left: number): Tone {
  if (left === 0) return "danger"
  if (left <= 3) return "warn"
  return "neutral"
}

function pad(value: number): string {
  return value.toString().padStart(2, "0")
}

/** `YYYY-MM-DD` from the local calendar. `toISOString` would answer in UTC,
 *  which is yesterday for part of every evening. */
function key(when: Date): string {
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
}

function human(when: Date): string {
  return `${pad(when.getDate())}.${pad(when.getMonth() + 1)}`
}

/** Monday is 0. */
function weekday(when: Date): number {
  return (when.getDay() + 6) % 7
}

function fortnightFrom(step: number): Date[] {
  const first = new Date()
  first.setHours(12, 0, 0, 0)
  first.setDate(first.getDate() + step * FORTNIGHT)
  return Array.from({ length: FORTNIGHT }, (_, at) => {
    const day = new Date(first)
    day.setDate(first.getDate() + at)
    return day
  })
}

function daysBetween(from: string, to: string): Date[] {
  const first = parse(from)
  const last = parse(to)
  if (!first || !last || last < first) return []
  const out: Date[] = []
  const walk = new Date(first)
  // The endpoint takes sixty days at most; more than that is a typed year,
  // not an intention.
  while (walk <= last && out.length < 60) {
    out.push(new Date(walk))
    walk.setDate(walk.getDate() + 1)
  }
  return out
}

function parse(day: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day)
  if (!match) return null
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12)
}
