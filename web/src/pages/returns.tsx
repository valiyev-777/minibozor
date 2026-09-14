/**
 * Qaytarishlar — the half of an order that runs backwards.
 *
 * ------------------------------------------------------------------- why
 *
 * This was the one flow in the building with a person waiting at the far end
 * of it and no screen at all. A customer raises a return from the phone, the
 * server has every door — approve, reject, inspect, refund — and nobody could
 * open one, so the request sat there and the money never went back. Clothing
 * is the return-heaviest retail there is and this shop sells sized garments
 * out of market sacks; the commonest sentence in the reason list is
 * "O'lcham to'g'ri kelmadi".
 *
 * -------------------------------------------------------------- two axes
 *
 * A return has **two** states and they are not one column.
 *
 * `status` is the money: submitted → approved or rejected, approved →
 * refunded, and the last two are where it stops. `inspection` is the parcel:
 * `null` until somebody opens it, then whole or damaged, once and for ever.
 * The two cross. A return can be approved and unopened, refunded and
 * unopened, or opened before the money moves — the server is race-safe about
 * the shelf either way — so "Ochilmagan" is its own tab rather than a status,
 * because on the status axis it is invisible.
 *
 * ------------------------------------------------------------ the buttons
 *
 * Drawn from `next_statuses`, which the server puts in the row. Not from a
 * copy of the rules kept here: a second copy is a copy that drifts, and the
 * way it drifts is a button that 409s. What the reader's role does not allow
 * is not drawn either — and in its place there is a sentence saying whose job
 * it is, because a screen that silently omits the thing somebody came for
 * reads as broken.
 *
 * --------------------------------------------------------------- two jobs
 *
 * The owner decides and pays. The warehouse opens the parcel. They reach this
 * same screen from two different menus, at two different densities, and the
 * bench is standing up with the parcel in one hand — so the inspect control
 * is two big buttons and a note, not a form, and it opens first for them.
 */

import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import {
  Ban,
  CheckCircle2,
  Clock,
  ExternalLink,
  PackageOpen,
  ShieldCheck,
  Undo2,
  Wallet,
} from "lucide-react"

import { DataTable, useTableState } from "@/components/data-table"
import {
  PageHeader,
  Panel,
  Pill,
  Problem,
  Segmented,
  Stat,
  type Tone,
} from "@/components/page"
import { mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/cn"
import { ageBrief, dateTime, groups, minutesSince, money } from "@/lib/format"
import { useDecideReturn, useInspectReturn, useReturn, useReturns } from "@/lib/queries"
import { useSession } from "@/lib/session"
import type { ReturnStatus, StaffReturn } from "@/lib/types"

/* ------------------------------------------------------------ the two axes */

/** Green happened, red did not, amber not yet, blue is where it is now. */
const STATUS: Record<ReturnStatus, { label: string; tone: Tone }> = {
  submitted: { label: "Javob kutmoqda", tone: "warn" },
  approved: { label: "Tasdiqlangan", tone: "brand" },
  rejected: { label: "Rad etilgan", tone: "danger" },
  refunded: { label: "Puli qaytarildi", tone: "good" },
}

/** The parcel, which is a different question from the money. `null` is not a
 *  missing value — it is the answer "nobody has opened it yet". */
const VERDICT: Record<"ok" | "damaged" | "none", { label: string; tone: Tone }> = {
  ok: { label: "Butun", tone: "good" },
  damaged: { label: "Buzilgan", tone: "danger" },
  none: { label: "Ochilmagan", tone: "warn" },
}

function verdictOf(row: StaffReturn) {
  return VERDICT[row.inspection ?? "none"]
}

/** Has the parcel reached the building at all? Only then is there anything to
 *  open — and it is the same rule the server refuses on. */
function arrived(row: StaffReturn): boolean {
  return row.status === "approved" || row.status === "refunded"
}

/**
 * What goes back to the card — and `null` until it is known.
 *
 * The server works the figure out at the moment of paying, because it is not
 * the sum of the goods: a whole order coming back takes the delivery fee with
 * it and one line of an order does not. So until the refund lands the row
 * carries nought, and nought is not a sum of money — printing "0 so'm" beside
 * a decision about somebody's money would be the screen stating a figure it
 * has not been told.
 */
function amountOf(row: StaffReturn): string | null {
  return row.refund_amount > 0 ? money(row.refund_amount) : null
}

/**
 * A day without an answer.
 *
 * Not a service promise — a threshold at which the age column stops being a
 * fact and starts being the reason to open the row. A return raised this
 * morning is work; one raised on Tuesday is a person who has told somebody
 * about it.
 */
const ANSWER_LATE_MINUTES = 24 * 60

/* ----------------------------------------------------------------- the tabs */

type Tab = { key: string; label: string; status: string; awaiting: string }

/**
 * The queues first, the history after.
 *
 * "Ochilmagan" sits second because it is the other piece of *work* on this
 * screen, and it is the only one that cannot be reached by filtering the
 * status column.
 */
const TABS: Tab[] = [
  { key: "javob", label: "Javob kutmoqda", status: "submitted", awaiting: "" },
  { key: "ochilmagan", label: "Ochilmagan", status: "", awaiting: "inspection" },
  { key: "tasdiqlangan", label: "Tasdiqlangan", status: "approved", awaiting: "" },
  { key: "qaytarilgan", label: "Puli qaytarildi", status: "refunded", awaiting: "" },
  { key: "rad", label: "Rad etilgan", status: "rejected", awaiting: "" },
  { key: "hammasi", label: "Hammasi", status: "", awaiting: "" },
]

export function ReturnsPage() {
  const { staff } = useSession()
  const state = useTableState()
  const [params, setParams] = useSearchParams()

  // The bench opens on the parcels nobody has looked in; the office opens on
  // the people waiting for an answer. Same screen, two different first
  // questions, and neither of them is "everything".
  const fallback = staff?.role === "warehouse" ? "ochilmagan" : "javob"
  const chosen = state.filter("holat") || fallback
  const tab = TABS.find((one) => one.key === chosen) ?? TABS[0]

  const rows = useReturns(tab.status, tab.awaiting)

  // One extra read of the whole list, for the two counts that are work. A
  // number on a tab is what makes a queue a queue rather than a filter — and
  // deriving these locally is honest because both are properties of a row.
  const everything = useReturns("", "")
  const waiting = (everything.data ?? []).filter((one) => one.status === "submitted").length
  const unopened = (everything.data ?? []).filter(
    (one) => arrived(one) && one.inspection === null,
  ).length

  // The open return lives in the address bar: "this one, look" is a link.
  const opened = Number(params.get("ariza")) || null
  const open = (id: number | null) => {
    const next = new URLSearchParams(params)
    if (id) next.set("ariza", String(id))
    else next.delete("ariza")
    setParams(next, { replace: true })
  }

  const counts: Record<string, number> = { javob: waiting, ochilmagan: unopened }

  return (
    <div>
      <PageHeader
        title="Qaytarishlar"
        subtitle="Tovarni qaytarib, pulini so'raganlar"
      />

      <DataTable<StaffReturn>
        title={tab.label}
        rows={rows.data ?? []}
        loading={rows.isLoading}
        error={rows.error}
        rowKey={(row) => row.id}
        onRowClick={(row) => open(row.id)}
        count={(n) => `${groups(n)} ta ariza`}
        searchPlaceholder="Kod, mijoz, tovar"
        search={(row) =>
          [row.order_code, row.customer_name, row.customer_phone, row.product_title, row.reason].join(" ")
        }
        empty={{
          icon: Undo2,
          title: emptyTitle(tab.key),
          what: emptyWhat(tab.key),
        }}
        beforeSearch={
          <Segmented
            label="Qaysi arizalar"
            value={tab.key}
            onChange={(next) => state.setFilter("holat", next)}
            options={TABS.map((one) => ({
              key: one.key,
              label: (
                <span className="inline-flex items-center gap-1.5">
                  {one.label}
                  {counts[one.key] ? (
                    <span className="rounded-full bg-warn-soft px-1.5 text-micro font-semibold tabular text-warn-ink">
                      {counts[one.key]}
                    </span>
                  ) : null}
                </span>
              ),
            }))}
          />
        }
        indicator={{
          of: (row) =>
            row.status === "submitted"
              ? "danger"
              : row.status === "approved"
                ? "warn"
                : row.status === "refunded" && row.inspection === null
                  ? "brand"
                  : row.status === "refunded"
                    ? "good"
                    : "neutral",
          legend: [
            { tone: "danger", label: "Javob kutmoqda" },
            { tone: "warn", label: "Puli qaytarilmagan" },
            { tone: "brand", label: "Quti ochilmagan" },
            { tone: "good", label: "Tugagan" },
            { tone: "neutral", label: "Rad etilgan" },
          ],
        }}
        columns={[
          {
            key: "order",
            header: "Buyurtma",
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate font-medium tabular">{row.order_code}</div>
                <div className="truncate text-micro text-ink-soft">
                  {row.order_item_id ? "Bitta qator" : "Butun buyurtma"}
                </div>
              </div>
            ),
          },
          {
            key: "customer",
            header: "Mijoz",
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate">{row.customer_name || "Ismi yozilmagan"}</div>
                <div className="truncate text-micro tabular text-ink-soft">
                  {row.customer_phone}
                </div>
              </div>
            ),
          },
          {
            key: "product",
            header: "Tovar",
            cell: (row) =>
              row.product_title ? (
                <span className="line-clamp-2 max-w-56">{row.product_title}</span>
              ) : null,
          },
          {
            key: "reason",
            header: "Sababi",
            cell: (row) => (
              <span className="line-clamp-2 max-w-56 text-ink-soft">{row.reason}</span>
            ),
          },
          {
            key: "amount",
            header: "Summasi",
            numeric: true,
            width: "1%",
            sortable: true,
            sortValue: (row) => row.refund_amount,
            cell: (row) => {
              const sum = amountOf(row)
              return sum ? (
                <span className="whitespace-nowrap font-medium">{sum}</span>
              ) : (
                <span className="text-micro text-ink-faint">Hisoblanmagan</span>
              )
            },
          },
          {
            // An unanswered return is a person waiting, so this is the urgent
            // column and it is written in words: "3 kun" is the decision, and
            // a timestamp makes the reader do the subtraction.
            key: "age",
            header: "Kutmoqda",
            width: "1%",
            sortable: true,
            sortValue: (row) => row.created_at,
            cell: (row) => {
              const minutes = minutesSince(row.created_at)
              const late = row.status === "submitted" && minutes >= ANSWER_LATE_MINUTES
              return (
                <span
                  title={dateTime(row.created_at)}
                  className={cn(
                    "whitespace-nowrap tabular",
                    late ? "font-semibold text-danger" : "text-ink-soft",
                  )}
                >
                  {ageBrief(minutes)}
                </span>
              )
            },
          },
          {
            key: "status",
            header: "Holati",
            width: "1%",
            cell: (row) => (
              <Pill tone={STATUS[row.status].tone} className="whitespace-nowrap">
                {STATUS[row.status].label}
              </Pill>
            ),
          },
          {
            key: "inspection",
            header: "Qutisi",
            width: "1%",
            align: "end",
            cell: (row) =>
              !arrived(row) ? (
                <span className="text-micro text-ink-faint">Kelmagan</span>
              ) : (
                <Pill tone={verdictOf(row).tone} className="whitespace-nowrap">
                  {row.inspection ? row.inspection_label || verdictOf(row).label : "Ochilmagan"}
                </Pill>
              ),
          },
        ]}
      />

      <ReturnSheet id={opened} onClose={() => open(null)} />
    </div>
  )
}

function emptyTitle(tab: string): string {
  if (tab === "javob") return "Javob kutayotgan ariza yo'q"
  if (tab === "ochilmagan") return "Ochilmagan quti yo'q"
  return "Ariza yo'q"
}

function emptyWhat(tab: string): string {
  if (tab === "javob") return "Hammasiga javob berilgan. Mijoz ilovadan ariza yuborganda shu yerda paydo bo'ladi."
  if (tab === "ochilmagan") return "Qaytib kelgan har bir quti ochilgan. Ariza tasdiqlangach, tovar omborga keladi va shu yerda kutadi."
  return "Mijoz ilovadan tovarni qaytarishni so'raganda ariza shu yerda paydo bo'ladi."
}

/* --------------------------------------------------------------- the drawer */

function ReturnSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const detail = useReturn(id)
  const row = detail.data

  return (
    <Sheet open={Boolean(id)} onOpenChange={(next) => (next ? undefined : onClose())}>
      {/* Full width on a phone: the bench reads this standing up, and a
          drawer three-quarters across a handset is a column of two words. */}
      <SheetContent className="sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{row ? row.order_code : "Qaytarish"}</SheetTitle>
          <SheetDescription className="flex flex-wrap items-center gap-2">
            {row ? (
              <>
                <span>{row.customer_name || "Ismi yozilmagan"}</span>
                <span className="tabular">{row.customer_phone}</span>
                <Pill tone={STATUS[row.status].tone}>{STATUS[row.status].label}</Pill>
              </>
            ) : (
              <span>Yuklanmoqda…</span>
            )}
          </SheetDescription>
        </SheetHeader>

        <SheetBody className="space-y-4 bg-canvas">
          <Problem error={detail.error} />
          {detail.isLoading ? (
            <p className="text-small text-ink-soft">Yuklanmoqda…</p>
          ) : row ? (
            // Keyed, so a half-typed rejection reason does not follow the
            // reader into the next return they open.
            <ReturnDetail key={row.id} row={row} />
          ) : null}
        </SheetBody>
      </SheetContent>
    </Sheet>
  )
}

/**
 * One return, in the order it gets read — and that order is not the same for
 * both readers.
 *
 * The office reads about the money: what is being asked for, how long somebody
 * has waited, what they said, what the parcel turned out to be, and then the
 * three acts. The bench is standing at a table with the parcel already in
 * their hands, on a phone — so for them the two big buttons come first and the
 * customer's words and pictures come under them, which is the order they are
 * used in. A figure about a refund is not their question at all and is not
 * drawn for them.
 */
function ReturnDetail({ row }: { row: StaffReturn }) {
  const { staff } = useSession()
  const minutes = minutesSince(row.created_at)
  const late = row.status === "submitted" && minutes >= ANSWER_LATE_MINUTES
  const bench = staff?.role === "warehouse"

  const request = (
    <>
      <Panel title="Ariza">
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">
          <Fact name="Sababi" value={row.reason} />
          <Fact
            name="Buyurtma"
            value={
              <Link
                to={`/buyurtmalar?q=${encodeURIComponent(row.order_code)}`}
                className="inline-flex items-center gap-1 font-medium tabular text-brand-deep hover:underline"
              >
                {row.order_code}
                <ExternalLink className="size-3.5" />
              </Link>
            }
          />
          <Fact name="Tovar" value={row.product_title || null} />
          {/* One line of an order or all of it — the difference is the
              delivery fee, which comes back only with a whole order. */}
          <Fact
            name="Qamrovi"
            value={row.order_item_id ? "Bitta qator" : "Butun buyurtma, yetkazish bilan"}
          />
          <Fact
            name="Mijoz"
            value={`${row.customer_name || "Ismi yozilmagan"} · ${row.customer_phone}`}
          />
        </dl>

        {row.comment ? (
          <p className="mt-3 rounded-control bg-line-soft p-3 text-small">
            <span className="caption block text-ink-faint">Mijozning izohi</span>
            {row.comment}
          </p>
        ) : null}

        {row.photos.length ? <Photos photos={row.photos} /> : null}
      </Panel>

      {row.resolution ? (
        <Panel title="Mijozga aytilgan javob">
          <p className="text-small">{row.resolution}</p>
        </Panel>
      ) : null}
    </>
  )

  if (bench) {
    return (
      <>
        <Inspection row={row} />
        {request}
        <Decision row={row} />
      </>
    )
  }

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2">
        <Stat
          label={row.status === "refunded" ? "Qaytarilgan pul" : "Qaytariladigan pul"}
          value={amountOf(row) ?? "—"}
          hint={
            amountOf(row)
              ? "To'landi"
              : row.status === "rejected"
                ? "Ariza rad etildi — pul qaytmaydi"
                : "To'lov paytida hisoblanadi"
          }
          icon={Wallet}
          tone={
            row.status === "refunded"
              ? "good"
              : row.status === "rejected"
                ? "neutral"
                : "brand"
          }
        />
        <Stat
          label={row.status === "submitted" ? "Javob kutmoqda" : "Ariza yoshi"}
          value={ageBrief(minutes)}
          hint={dateTime(row.created_at)}
          icon={Clock}
          tone={late ? "danger" : "neutral"}
        />
      </div>

      {request}
      <Inspection row={row} />
      <Decision row={row} />
    </>
  )
}

function Fact({ name, value }: { name: string; value: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-micro text-ink-faint">{name}</dt>
      <dd className="truncate text-small">
        {value || <span className="text-ink-faint">—</span>}
      </dd>
    </div>
  )
}

/** What the customer photographed. Relative paths — each client prefixes its
 *  own host — and a thumbnail of a torn seam is worth reading at full size,
 *  so each one opens. */
function Photos({ photos }: { photos: string[] }) {
  return (
    <div className="scroll-slim mt-3 flex gap-2 overflow-x-auto">
      {photos.map((path) => (
        <a
          key={path}
          href={mediaUrl(path)}
          target="_blank"
          rel="noreferrer"
          className="block shrink-0 overflow-hidden rounded-control border border-line focus-visible:ring-2 focus-visible:ring-brand/40 focus:outline-none"
        >
          <img
            src={mediaUrl(path)}
            alt="Mijoz yuborgan surat"
            loading="lazy"
            className="size-24 bg-line-soft object-cover"
          />
        </a>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------- the parcel */

/**
 * The warehouse's door: whole or damaged, once.
 *
 * Two big buttons and a note, because the person answering is standing at a
 * bench holding the garment — a select and a Save is a form for somebody
 * sitting down. One shot: the server refuses a second verdict, so once it has
 * landed this is a sentence rather than a control, and there is no button
 * here that would 409.
 */
function Inspection({ row }: { row: StaffReturn }) {
  const { staff } = useSession()
  const inspect = useInspectReturn(row.id)
  const [note, setNote] = useState("")

  // The server lets the owner open a parcel too — in a shop this size the
  // same person often does both — so this follows the server rather than the
  // menu the reader arrived from.
  const mayInspect = staff?.role === "warehouse" || staff?.role === "admin"

  if (row.inspection) {
    const verdict = verdictOf(row)
    return (
      <Panel title="Quti ochilgan">
        <div className="flex flex-wrap items-center gap-3">
          <Pill tone={verdict.tone}>{row.inspection_label || verdict.label}</Pill>
          {row.inspected_at ? (
            <span className="text-micro tabular text-ink-soft">
              {dateTime(row.inspected_at)}
            </span>
          ) : null}
          {/* `relisted` means the room has moved for this parcel, not that it
              went back on sale — the same flag covers a shirt that reached
              the receiving area and one that reached the damaged corner, so
              where it landed has to be read off the verdict. */}
          {row.relisted ? (
            row.inspection === "damaged" ? (
              <Pill tone="danger">
                <ShieldCheck className="size-3" />
                BRAK burchagiga tushdi
              </Pill>
            ) : (
              <Pill tone="good">
                <ShieldCheck className="size-3" />
                Omborga qaytdi, sotuvga tayyor
              </Pill>
            )
          ) : null}
        </div>
        {row.inspection_note ? (
          <p className="mt-2 text-small text-ink-soft">{row.inspection_note}</p>
        ) : null}
        <p className="mt-2 text-micro text-ink-faint">
          Bir marta javob beriladi — o'zgartirib bo'lmaydi.
        </p>
      </Panel>
    )
  }

  // A sentence and not an `Empty`: inside a drawer the tall empty state is a
  // hole where the reader is looking for the next thing to do, and "nothing
  // here yet" is one line of news.
  if (!arrived(row)) {
    return (
      <Panel title="Quti">
        <p className="flex items-start gap-2 text-small text-ink-soft">
          <PackageOpen className="mt-0.5 size-4 shrink-0 text-ink-faint" />
          {row.status === "rejected"
            ? "Ariza rad etilgan — tovar omborga kelmaydi."
            : "Tovar hali kelmagan. Avval ariza tasdiqlanadi, tovar keladi, keyin quti ochiladi."}
        </p>
      </Panel>
    )
  }

  if (!mayInspect) {
    return (
      <Panel title="Quti ochilmagan">
        <p className="text-small text-ink-soft">
          Qutini ombor ochadi va nima kelganini yozadi.
        </p>
      </Panel>
    )
  }

  return (
    <Panel title="Nima keldi?">
      <p className="text-small text-ink-soft">
        Qutini oching va tovarni ko'ring. Butun tovar sotuvga qaytadi, buzilgani
        BRAK burchagiga tushadi. Javob bir marta beriladi.
      </p>

      {/* The note is above the buttons because pressing one of them is the
          last thing that happens: the verdict commits on the tap, and a field
          underneath it would be a field somebody fills in too late. */}
      <label className="mt-3 block">
        <span className="mb-1 block text-micro font-medium text-ink-soft">
          Izoh (ixtiyoriy)
        </span>
        <textarea
          value={note}
          rows={2}
          onChange={(event) => setNote(event.target.value)}
          placeholder="Masalan: yoqasi yirtilgan"
          className={FIELD}
        />
      </label>

      {inspect.error ? (
        <div className="mt-3">
          <Problem error={inspect.error} />
        </div>
      ) : null}

      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <Button
          variant="secondary"
          size="lg"
          disabled={inspect.isPending}
          onClick={() => inspect.mutate({ result: "ok", note: note.trim() })}
          className="flex-1 border-good/40 text-good hover:bg-good-soft hover:text-good"
        >
          <CheckCircle2 />
          Butun
        </Button>
        <Button
          variant="secondary"
          size="lg"
          disabled={inspect.isPending}
          onClick={() => inspect.mutate({ result: "damaged", note: note.trim() })}
          className="flex-1 border-danger/40 text-danger hover:bg-danger-soft hover:text-danger"
        >
          <Ban />
          Buzilgan
        </Button>
      </div>
    </Panel>
  )
}

/* --------------------------------------------------------------- the money */

const FIELD = [
  "w-full min-w-0 rounded-control border border-transparent bg-line-soft px-3 py-2 text-small text-ink",
  "outline-none transition-[background-color,border-color,box-shadow]",
  "placeholder:text-ink-faint focus:border-brand focus:bg-surface focus:ring-2 focus:ring-brand/25",
].join(" ")

/**
 * The owner's three acts, and every one of them comes from `next_statuses`.
 *
 * Rejecting needs a reason because the reason *is* the sentence the customer
 * reads, and paying needs an answer about the shelf that has no default —
 * a stock count must not move, or fail to move, because somebody left a field
 * alone. So neither is a bare button: each opens the one question it cannot
 * be done without, and nothing is preselected.
 */
function Decision({ row }: { row: StaffReturn }) {
  const { staff } = useSession()
  const decide = useDecideReturn(row.id)
  const [act, setAct] = useState<"reject" | "refund" | null>(null)
  const [reason, setReason] = useState("")
  const [note, setNote] = useState("")
  const [restock, setRestock] = useState<boolean | null>(null)

  const may = (next: ReturnStatus) => row.next_statuses.includes(next)
  const isOwner = staff?.role === "admin"

  const close = () => {
    setAct(null)
    setReason("")
    setNote("")
    setRestock(null)
  }

  if (row.next_statuses.length === 0) {
    return (
      <Panel title="Qaror">
        <p className="text-small text-ink-soft">
          {row.status === "refunded"
            ? "Pul mijozga qaytarilgan. Ariza yopildi."
            : "Ariza rad etilgan va yopilgan."}
        </p>
      </Panel>
    )
  }

  // Not drawn, and said out loud. The server refuses these three doors to
  // anybody but the owner, and a screen that just leaves them out reads as a
  // screen that is broken.
  if (!isOwner) {
    return (
      <Panel title="Qaror">
        <p className="text-small text-ink-soft">
          Arizani tasdiqlash, rad etish va pulni qaytarish — do'kon egasining
          ishi. Sizning ishingiz qutini ochib, nima kelganini aytish.
        </p>
      </Panel>
    )
  }

  if (act === "reject") {
    return (
      <Panel title="Arizani rad etish">
        <label className="block">
          <span className="mb-1 block text-micro font-medium text-ink-soft">
            Sababi — <span className="text-danger">majburiy</span>
          </span>
          <textarea
            autoFocus
            rows={3}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Masalan: tovar kiyilgan, yorlig'i yo'q"
            className={FIELD}
          />
          {/* The one thing about this field somebody has to know before they
              type into it: it is not an internal note. */}
          <span className="mt-1 block text-micro text-ink-faint">
            Shu jumlani mijoz ilovada o'qiydi.
          </span>
        </label>

        <label className="mt-3 block">
          <span className="mb-1 block text-micro font-medium text-ink-soft">
            Ichki izoh (ixtiyoriy)
          </span>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Kim qo'ng'iroq qildi, nima dedi"
            className={FIELD}
          />
        </label>

        <div className="mt-3">
          <Problem error={decide.error} />
        </div>

        <div className="mt-3 flex gap-3 [&>*]:flex-1">
          <Button variant="secondary" onClick={close}>
            Bekor qilish
          </Button>
          <Button
            variant="danger"
            disabled={!reason.trim() || decide.isPending}
            onClick={() =>
              decide.mutate(
                { decision: "reject", reason: reason.trim(), note: note.trim() },
                { onSuccess: close },
              )
            }
          >
            Rad etish
          </Button>
        </div>
      </Panel>
    )
  }

  if (act === "refund") {
    const verdict = verdictOf(row)
    return (
      <Panel title="Pulni qaytarish">
        <p className="text-small text-ink-soft">
          Tovar qayerga ketdi? Javob berilmasa pul qaytmaydi — ombor soni
          o'z-o'zidan o'zgarmasligi kerak. Summani server hisoblaydi:
          {row.order_item_id
            ? " shu qatorning o'zi."
            : " butun buyurtma, yetkazish puli bilan."}
        </p>

        {/* The verdict beside the choice, because "is this sellable" is the
            question the person paying is about to ask — and when nobody has
            opened the parcel, that absence is the answer. */}
        <p className="mt-2 flex flex-wrap items-center gap-2 text-micro text-ink-soft">
          Ombor javobi:
          {row.inspection ? (
            <>
              <Pill tone={verdict.tone}>{row.inspection_label || verdict.label}</Pill>
              {row.inspection_note ? <span>{row.inspection_note}</span> : null}
            </>
          ) : (
            <>
              <Pill tone="warn">Ochilmagan</Pill>
              <span>quti hali ochilmagan — javonga qaytarishga shoshilmang</span>
            </>
          )}
        </p>

        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <Choice
            on={restock === true}
            tone="good"
            title="Javonga qaytarilsin"
            what="Tovar butun, yana sotiladi"
            onPick={() => setRestock(true)}
          />
          <Choice
            on={restock === false}
            tone="danger"
            title="Javonga qaytarilmasin"
            what="Buzilgan yoki hali ko'rilmagan"
            onPick={() => setRestock(false)}
          />
        </div>

        <label className="mt-3 block">
          <span className="mb-1 block text-micro font-medium text-ink-soft">
            Ichki izoh (ixtiyoriy)
          </span>
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="To'lov qanday qaytarildi"
            className={FIELD}
          />
        </label>

        <div className="mt-3">
          <Problem error={decide.error} />
        </div>

        <div className="mt-3 flex gap-3 [&>*]:flex-1">
          <Button variant="secondary" onClick={close}>
            Bekor qilish
          </Button>
          <Button
            variant="primary"
            disabled={restock === null || decide.isPending}
            onClick={() =>
              decide.mutate(
                { decision: "refund", restock: restock === true, note: note.trim() },
                { onSuccess: close },
              )
            }
          >
            Pulni qaytarish
          </Button>
        </div>
      </Panel>
    )
  }

  return (
    <Panel title="Qaror">
      <Problem error={decide.error} />
      <div className="flex flex-col gap-2 sm:flex-row">
        {may("approved") ? (
          <Button
            variant="primary"
            className="flex-1"
            disabled={decide.isPending}
            onClick={() => decide.mutate({ decision: "approve" })}
          >
            <CheckCircle2 />
            Tasdiqlash
          </Button>
        ) : null}
        {may("refunded") ? (
          <Button variant="primary" className="flex-1" onClick={() => setAct("refund")}>
            <Wallet />
            Pulni qaytarish
          </Button>
        ) : null}
        {may("rejected") ? (
          <Button variant="danger" className="flex-1" onClick={() => setAct("reject")}>
            <Ban />
            Rad etish
          </Button>
        ) : null}
      </div>
      {may("approved") ? (
        <p className="mt-2 text-micro text-ink-faint">
          Tasdiqlash — pul hali qaytmaydi: avval tovar omborga keladi.
        </p>
      ) : null}
    </Panel>
  )
}

/** One of two answers, and neither of them is chosen for you. A radio drawn
 *  as a card, because the difference between the two is a sentence rather
 *  than a word. */
function Choice({
  on,
  tone,
  title,
  what,
  onPick,
}: {
  on: boolean
  tone: "good" | "danger"
  title: string
  what: string
  onPick: () => void
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={on}
      onClick={onPick}
      className={cn(
        "rounded-control border p-3 text-left transition-colors",
        "focus-visible:ring-2 focus-visible:ring-brand/40 focus:outline-none",
        on
          ? tone === "good"
            ? "border-good bg-good-soft"
            : "border-danger bg-danger-soft"
          : "border-line bg-surface hover:bg-line-soft",
      )}
    >
      <span
        className={cn(
          "block text-small font-medium",
          on && (tone === "good" ? "text-good" : "text-danger"),
        )}
      >
        {title}
      </span>
      <span className="block text-micro text-ink-soft">{what}</span>
    </button>
  )
}
