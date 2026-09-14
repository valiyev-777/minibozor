/**
 * Jurnal — the trail, read back at last.
 *
 * ------------------------------------------------------------------- why
 *
 * Thirty-eight places in the server write an audit row before they commit,
 * and until now nothing read one back: the only way to answer "who changed
 * this price" or "who let that courier in" was a database client on the
 * server. The table has been filling up for the whole life of the shop and
 * this is the first screen that opens it.
 *
 * ----------------------------------------------------------- the filters
 *
 * Every one is a question somebody has asked out loud. What happened to
 * order 412 — entity and its number. What did the new warehouse lad do on his
 * first day — an actor and a date. Who has been changing prices — an action.
 * Where did that note about the telephone call go — the search box, which
 * looks in the note and in both values.
 *
 * `action` matches on a prefix on the server, which is why the chooser
 * offers **families** rather than the thirty-four individual actions:
 * `user` is `user.role`, `user.create`, `user.active` and `user.profile` at
 * once, and "everything that has been done to accounts" is the question
 * actually being asked. The dotted pairs were named that way so they group.
 *
 * ------------------------------------------------------------ the change
 *
 * Old struck through, an arrow, new in the row's own weight. A log that
 * prints only the new value answers "what is it now", which is the one
 * question you could already answer by looking at the thing.
 */

import { ScrollText } from "lucide-react"

import { DataTable, useTableState } from "@/components/data-table"
import { PageHeader, type Tone } from "@/components/page"
import { date, groups, time } from "@/lib/format"
import { useAudit, useStaffList } from "@/lib/queries"
import { ROLE_LABEL, type AuditRow, type UserRole } from "@/lib/types"

/**
 * The families, in the words the office uses for them.
 *
 * Not a list of every action: the server matches this as a prefix, so one
 * entry here opens a whole family, and a select with thirty-four dotted
 * identifiers in it is a select nobody reads to the bottom of.
 */
const FAMILIES: Array<{ value: string; label: string }> = [
  { value: "user", label: "Hisoblar" },
  { value: "order", label: "Buyurtmalar" },
  { value: "product", label: "Mahsulotlar" },
  { value: "variant", label: "Rang va o'lchamlar" },
  { value: "supply", label: "Bozor safari" },
  { value: "pile", label: "Qabul" },
  { value: "stock", label: "Ombor qoldig'i" },
  { value: "location", label: "Javonlar" },
  { value: "pickup", label: "Olib ketish" },
  { value: "return", label: "Qaytarish" },
  { value: "slot", label: "Yetkazish vaqti" },
]

export const ENTITIES: Array<{ value: string; label: string }> = [
  { value: "user", label: "Hisob" },
  { value: "order", label: "Buyurtma" },
  { value: "product", label: "Mahsulot" },
  { value: "product_variant", label: "Variant" },
  { value: "variant", label: "Variant (eski)" },
  { value: "supply", label: "Safar" },
  { value: "location", label: "Joy" },
  { value: "pickup_run", label: "Olib ketish" },
  { value: "return_request", label: "Qaytarish" },
  { value: "delivery_slot", label: "Yetkazish oynasi" },
]

/** The words each action is actually about, so a row reads as a sentence
 *  rather than as an identifier. Anything not named here falls back to the
 *  identifier itself — a new action added on the server shows up as what it
 *  is called instead of disappearing behind an empty cell. */
export const ACTIONS: Record<string, string> = {
  "user.create": "Hisob ochildi",
  "user.role": "Lavozim o'zgardi",
  "user.active": "Hisob holati",
  "user.profile": "Ma'lumoti tuzatildi",
  "order.status": "Buyurtma holati",
  "order.cancel": "Buyurtma bekor qilindi",
  "order.deliver": "Yetkazildi",
  "order.taken": "Kuryer oldi",
  "order.attempt_failed": "Yetkazib bo'lmadi",
  "product.create": "Karta yozildi",
  "product.status": "Karta holati",
  "product.price": "Narx o'zgardi",
  "product.specs": "Xususiyatlari",
  "product.archive": "Arxivlandi",
  "product.delete": "Karta o'chirildi",
  "variant.price": "Variant narxi",
  "variant.retired": "Variant to'xtatildi",
  "supply.start": "Safar boshlandi",
  "supply.receive": "Safar qabul qilindi",
  "supply.sorted": "Safar taqsimlandi",
  "supply.cancel": "Safar bekor qilindi",
  "pile.receive": "Uyum qabul qilindi",
  "stock.count": "Sanaldi",
  "stock.damage": "Yaroqsizga chiqarildi",
  "stock.empty": "Bo'shatildi",
  "location.rack_added": "Javon qo'shildi",
  "pickup.create": "Olib ketish ochildi",
  "pickup.collect": "Olib ketildi",
  "pickup.receive": "Olib ketish qabul qilindi",
  "return.status": "Qaytarish holati",
  "return.inspect": "Qaytarish ko'rildi",
  "return.refund": "Pul qaytarildi",
  "return.restock": "Javonga qaytdi",
  "slot.create": "Yetkazish oynasi",
}

/** Something was taken away, called off or thrown out. Worth a colour in a
 *  log that is otherwise a wall of ordinary work. */
const UNDOING = /cancel|delete|archive|damage|failed|empty|retired/

function toneOf(row: AuditRow): Tone | null {
  // An account switched off is an undoing, and the action alone cannot say
  // so: `user.active` is both the closing of a door and the reopening of it,
  // and which one is in the value.
  if (row.action === "user.active" && row.new_value === "false") return "danger"
  if (UNDOING.test(row.action)) return "danger"
  if (row.action.startsWith("user.")) return "brand"
  return null
}

/**
 * A stored value in the words the office uses — but only where this screen
 * can be sure what it is looking at.
 *
 * A role is translated because the field says it is a role. `true` and
 * `false` are translated because no free-text field ever holds exactly those
 * two words and a switch written as `false` is a switch nobody reads.
 * Everything else is printed as it was stored: a log that paraphrases is a
 * log you cannot quote.
 */
function say(value: string, field: string): string {
  if (field === "role") return ROLE_LABEL[value as UserRole] ?? value
  if (value === "true") return "Ha"
  if (value === "false") return "Yo'q"
  return value
}

const DATE_FIELD = [
  "h-control w-full min-w-0 rounded-control border border-line bg-surface px-3 text-small text-ink tabular",
  "outline-none transition-[border-color,box-shadow]",
  "focus:border-brand focus:ring-2 focus:ring-brand/25",
].join(" ")

export function AuditPage() {
  const state = useTableState()

  // The actor chooser is the staff directory: everybody who can change
  // anything works here, and a free-text box for a person whose id is an
  // integer is a box nobody can fill in.
  const staff = useStaffList({ size: 100 })

  const trail = useAudit({
    actor_id: state.filter("actor_id"),
    entity: state.filter("entity"),
    entity_id: state.filter("entity_id"),
    action: state.filter("action"),
    from_day: state.filter("from_day"),
    to_day: state.filter("to_day"),
    q: state.q,
    page: state.page,
    size: state.size,
  })

  return (
    <div>
      <PageHeader title="Jurnal" subtitle="Kim nimani, qachon o'zgartirgan" />

      <DataTable<AuditRow>
        title="Jurnal"
        rows={trail.data?.items ?? []}
        total={trail.data?.total}
        loading={trail.isLoading}
        error={trail.error}
        rowKey={(row) => row.id}
        count={(n) => `${groups(n)} ta yozuv`}
        searchPlaceholder="Izoh yoki qiymat"
        empty={{
          icon: ScrollText,
          title: "Yozuv topilmadi",
          what: "Jurnal har bir o'zgarishda o'zi to'ladi — saralashni kengaytiring yoki sanani o'zgartiring.",
        }}
        indicator={{
          of: toneOf,
          legend: [
            { tone: "brand", label: "Hisob o'zgarishi" },
            { tone: "danger", label: "Bekor qilish, o'chirish" },
          ],
        }}
        filters={[
          {
            key: "action",
            label: "Nima qilingan",
            kind: "select",
            options: FAMILIES,
          },
          { key: "entity", label: "Nimaga", kind: "select", options: ENTITIES },
          {
            key: "actor_id",
            label: "Kim",
            kind: "select",
            options: (staff.data?.items ?? []).map((one) => ({
              value: String(one.id),
              label: `${one.full_name || one.phone} — ${ROLE_LABEL[one.role]}`,
            })),
          },
          {
            key: "entity_id",
            label: "Raqami",
            kind: "text",
            placeholder: "412",
          },
          {
            key: "from_day",
            label: "Sanadan",
            kind: "custom",
            render: (value, set) => (
              <input
                type="date"
                value={value}
                onChange={(event) => set(event.target.value)}
                className={DATE_FIELD}
              />
            ),
          },
          {
            key: "to_day",
            label: "Sanagacha",
            kind: "custom",
            render: (value, set) => (
              <input
                type="date"
                value={value}
                onChange={(event) => set(event.target.value)}
                className={DATE_FIELD}
              />
            ),
          },
        ]}
        columns={[
          {
            key: "when",
            header: "Qachon",
            width: "1%",
            cell: (row) => (
              <div className="whitespace-nowrap">
                <div className="tabular">{date(row.created_at)}</div>
                <div className="text-micro tabular text-ink-faint">
                  {time(row.created_at)}
                </div>
              </div>
            ),
          },
          {
            key: "actor",
            header: "Kim",
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate font-medium">{row.actor_name}</div>
                <div className="truncate text-micro text-ink-soft">
                  {/* The authority the change was made under, off the row
                      itself — not whatever that person's job is today. */}
                  {row.actor_role ? ROLE_LABEL[row.actor_role] : "Tizim"}
                  {row.actor_phone ? (
                    <span className="tabular"> · {row.actor_phone}</span>
                  ) : null}
                </div>
              </div>
            ),
          },
          {
            key: "action",
            header: "Nima qilingan",
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate">{ACTIONS[row.action] ?? row.action}</div>
                <div className="truncate text-micro tabular text-ink-faint">
                  {row.action}
                </div>
              </div>
            ),
          },
          {
            key: "entity",
            header: "Nimaga",
            width: "1%",
            cell: (row) => (
              <span className="whitespace-nowrap">
                {ENTITIES.find((one) => one.value === row.entity)?.label ?? row.entity}
                {row.entity_id ? (
                  <span className="tabular text-ink-soft"> #{row.entity_id}</span>
                ) : null}
              </span>
            ),
          },
          {
            key: "change",
            header: "O'zgarish",
            cell: (row) => <Change row={row} />,
          },
          {
            key: "note",
            header: "Izoh",
            cell: (row) =>
              row.note ? (
                <span className="line-clamp-2 max-w-60 text-ink-soft" title={row.note}>
                  {row.note}
                </span>
              ) : null,
          },
        ]}
      />

      {/* Said once, at the bottom, because the first thing somebody looks for
          on a log screen is the button that tidies it up. There is not one. */}
      <p className="mt-3 text-micro text-ink-faint">
        Jurnal faqat o'qiladi — hech bir yozuv o'chirilmaydi va tuzatilmaydi.
      </p>
    </div>
  )
}

/**
 * Old, then new — and the field they belong to.
 *
 * A value can be a long string (a note, an address), so both are clipped to
 * one line with the whole thing on the title. The struck-through half is
 * what makes the row a change rather than a statement.
 */
function Change({ row }: { row: AuditRow }) {
  if (!row.field && !row.old_value && !row.new_value) return null

  return (
    <div className="min-w-0 max-w-64">
      {row.field ? (
        <div className="truncate text-micro tabular text-ink-faint">{row.field}</div>
      ) : null}
      <div className="flex min-w-0 items-baseline gap-1.5">
        {row.old_value ? (
          <span
            className="max-w-24 truncate text-ink-faint line-through"
            title={row.old_value}
          >
            {say(row.old_value, row.field)}
          </span>
        ) : null}
        {row.old_value && row.new_value ? (
          <span aria-hidden className="shrink-0 text-ink-faint">
            →
          </span>
        ) : null}
        {row.new_value ? (
          <span className="min-w-0 truncate font-medium" title={row.new_value}>
            {say(row.new_value, row.field)}
          </span>
        ) : null}
      </div>
    </div>
  )
}
