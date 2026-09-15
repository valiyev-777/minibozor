/**
 * Xodimlar — the people who work here, and nobody who buys here.
 *
 * ------------------------------------------------------------------- why
 *
 * The screen this replaces read `/admin/users`, which answers with every
 * account in the shop. So a page titled "Xodimlar" was a list of every person
 * who had ever bought a pair of shoes, and it got one row longer every day.
 * It is now `/admin/staff`, which is the question the screen was asking all
 * along — and it is paged, filtered and searched on the server, because a
 * directory is read to find one person.
 *
 * ------------------------------------------------------------- the role
 *
 * A role used to be five buttons in a row: one click, no confirmation, no
 * record of why. The audit table has had a `note` field the whole time and
 * this screen never filled it, so the log said *what* changed and never
 * *why* — which is the half somebody needs a year later.
 *
 * So it is a deliberate act now. Open the person, choose the job, say why,
 * and press once. The one change that is not reversible from a desk — making
 * somebody a customer, which shuts the panel behind them — says so before it
 * is made, in the button and above it.
 *
 * ------------------------------------------------------------ last seen
 *
 * `last_seen` is the newest refresh token the account still holds, so it
 * means *there is a live session* and not "they were here at 14:02". It is
 * shown as that and labelled as that: an office that reads a derived
 * timestamp as a clocking-off time is an office that will argue about
 * somebody's hours with a number that was never about hours.
 */

import { useState } from "react"
import { Link } from "react-router-dom"
import { Loader2, ScrollText, UserPlus, Users } from "lucide-react"

import { DataTable, useTableState } from "@/components/data-table"
import { PageHeader, Panel, Pill, Problem, Segmented, type Tone } from "@/components/page"
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
import {
  Sheet,
  SheetBody,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { cn } from "@/lib/cn"
import { date, dateTime, groups } from "@/lib/format"
import {
  useAppointStaff,
  useAudit,
  useEditUser,
  useSetActive,
  useSetRole,
  useStaffList,
} from "@/lib/queries"
import { ACTIONS, ENTITIES } from "@/pages/audit"
import { ROLE_LABEL, type StaffMember, type UserRole } from "@/lib/types"

/** Every role there is, in the words the office uses. `customer` is here
 *  because standing somebody down is a role change like any other — it is
 *  simply the one that closes the panel behind them. */
const ROLES: Array<{ key: UserRole; label: string }> = (
  ["admin", "warehouse", "courier", "customer"] as const
).map((key) => ({ key, label: ROLE_LABEL[key] }))

/** The three that are jobs. `customer` is not one, and the server refuses an
 *  appointment to it — so the form does not offer it. */
const JOBS = ROLES.filter((role) => role.key !== "customer")

/** Only the office's own job is coloured. Three neutral pills and one brand
 *  one says "these people work here, and that one can change what they do";
 *  four colours would say nothing at all. */
const ROLE_TONE: Record<UserRole, Tone> = {
  admin: "brand",
  warehouse: "neutral",
  courier: "neutral",
  customer: "warn",
}

export function StaffPage() {
  const state = useTableState()
  const people = useStaffList({
    q: state.q,
    role: state.filter("role"),
    active: state.filter("active"),
    page: state.page,
    size: state.size,
  })

  const [appointing, setAppointing] = useState(false)
  const [opened, setOpened] = useState<StaffMember | null>(null)

  // Re-read the open person out of the list rather than holding a copy: a
  // role changed in the drawer refetches the table, and a drawer still
  // showing the old job is the screen disagreeing with itself.
  const rows = people.data?.items ?? []
  const person = opened ? (rows.find((one) => one.id === opened.id) ?? opened) : null

  return (
    <div>
      <PageHeader title="Xodimlar" subtitle="Shu yerda ishlaydiganlar" />

      <DataTable<StaffMember>
        title="Xodimlar"
        rows={rows}
        total={people.data?.total}
        loading={people.isLoading}
        error={people.error}
        rowKey={(row) => row.id}
        onRowClick={(row) => setOpened(row)}
        count={(n) => `${groups(n)} ta xodim`}
        searchPlaceholder="Ism yoki raqam"
        empty={{
          icon: Users,
          title: "Xodim topilmadi",
          what: "Bu yerda faqat shu yerda ishlaydiganlar — mijozlar Mijozlar ekranida. Yangi odamni «Xodim qo'shish» tugmasi bilan tayinlang.",
        }}
        indicator={{
          of: (row) => (row.is_active ? null : "danger"),
          legend: [{ tone: "danger", label: "O'chirilgan hisob" }],
        }}
        filters={[
          {
            key: "role",
            label: "Lavozimi",
            kind: "select",
            options: JOBS.map((role) => ({ value: role.key, label: role.label })),
          },
          {
            key: "active",
            label: "Hisob holati",
            kind: "select",
            options: [
              { value: "true", label: "Faol" },
              { value: "false", label: "O'chirilgan" },
            ],
          },
        ]}
        afterSearch={
          <Button onClick={() => setAppointing(true)}>
            <UserPlus />
            Xodim qo'shish
          </Button>
        }
        columns={[
          {
            key: "person",
            header: "Xodim",
            cell: (row) => (
              <div className="min-w-0">
                <div
                  className={cn(
                    "truncate font-medium",
                    !row.is_active && "text-ink-faint line-through",
                  )}
                >
                  {row.full_name || "Ismi yozilmagan"}
                </div>
                <div className="truncate text-micro tabular text-ink-soft">
                  {row.phone}
                </div>
              </div>
            ),
          },
          {
            key: "role",
            header: "Lavozimi",
            width: "1%",
            cell: (row) => <Pill tone={ROLE_TONE[row.role]}>{ROLE_LABEL[row.role]}</Pill>,
          },
          {
            key: "seen",
            header: "Seansi",
            cell: (row) => <Seen when={row.last_seen} />,
          },
          {
            key: "joined",
            header: "Qo'shilgan",
            width: "1%",
            cell: (row) => <span className="tabular">{date(row.created_at)}</span>,
          },
          {
            key: "state",
            header: "Holati",
            width: "1%",
            align: "end",
            cell: (row) =>
              row.is_active ? (
                <Pill tone="good">Faol</Pill>
              ) : (
                <Pill tone="danger">O'chirilgan</Pill>
              ),
          },
        ]}
      />

      <Appoint open={appointing} onClose={() => setAppointing(false)} />
      <Person
        person={person}
        onClose={() => setOpened(null)}
      />
    </div>
  )
}

/**
 * Whether there is a live session, said as that and not as a clock.
 *
 * A token is written on sign-in and rewritten on every renewal, so a date
 * here is when the session was last refreshed — near enough to "they are
 * using it" to be worth showing, and nowhere near exact enough to be called
 * a last-seen time. Nothing outstanding means they have never signed in, or
 * signed out of everything.
 */
function Seen({ when }: { when: string | null }) {
  if (!when) {
    return <span className="text-micro text-ink-faint">Hech qachon kirmagan</span>
  }
  return (
    <div className="min-w-0">
      <Pill tone="good">Tizimda</Pill>
      <div className="truncate text-micro tabular text-ink-faint">
        {dateTime(when)} dan beri
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- appointing */

/**
 * Hiring, from inside the running system for the first time.
 *
 * The sentence under the fields is the whole point of the door and it is not
 * decoration: until now an admin had to wait for the new courier to sign in
 * as a shopper before they could be made a courier, so "the number need not
 * exist yet" is the thing somebody standing at the counter needs told.
 */
function Appoint({ open, onClose }: { open: boolean; onClose: () => void }) {
  const appoint = useAppointStaff()
  const [phone, setPhone] = useState("")
  const [name, setName] = useState("")
  const [role, setRole] = useState<UserRole>("courier")
  const [note, setNote] = useState("")

  const close = () => {
    appoint.reset()
    setPhone("")
    setName("")
    setNote("")
    setRole("courier")
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : close())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Xodim qo'shish</DialogTitle>
          <DialogDescription>
            Raqam hali tizimda bo'lmasa ham bo'ladi — hisob shu yerda ochiladi.
            Xodim keyin o'z raqami bilan, odatdagi SMS kodi orqali kiradi.
          </DialogDescription>
        </DialogHeader>

        <form
          id="appoint"
          onSubmit={(event) => {
            event.preventDefault()
            appoint.mutate(
              {
                phone: phone.trim(),
                full_name: name.trim(),
                role,
                note: note.trim(),
              },
              { onSuccess: close },
            )
          }}
        >
          <DialogBody className="space-y-4">
            <Field label="Telefon raqami" hint="907778899 ham bo'ladi — +998 o'zi qo'shiladi">
              <Input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="907778899"
                inputMode="tel"
                autoFocus
                required
                className="tabular"
              />
            </Field>

            <Field label="Ismi" hint="Ilovaga kirgach o'zi yozgan ismi ustun turadi">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Anvar Qodirov"
                maxLength={120}
              />
            </Field>

            {/* Not wrapped in `Field`: that is a `<label>`, and a label
                around a row of buttons makes every one of them the label's
                target. */}
            <div>
              <span className="mb-1 block text-micro font-medium text-ink-soft">
                Lavozimi
              </span>
              <Segmented
                label="Lavozimi"
                value={role}
                onChange={setRole}
                options={JOBS.map((one) => ({ key: one.key, label: one.label }))}
              />
            </div>

            <Field label="Izoh" hint="Nima uchun — jurnalga shu yoziladi">
              <Input
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Do'konda ishga olindi"
                maxLength={200}
              />
            </Field>

            <Problem error={appoint.error} />
          </DialogBody>
        </form>

        <DialogFooter showCloseButton>
          <Button type="submit" form="appoint" disabled={appoint.isPending || !phone.trim()}>
            {appoint.isPending ? <Loader2 className="animate-spin" /> : null}
            Tayinlash
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ---------------------------------------------------------------- one person */

/**
 * One colleague, and the four things an office does about one.
 *
 * A drawer rather than a page: every act here is short — correct a name,
 * change a job, switch an account off — and it is done while looking at the
 * list, which is where the next one is.
 */
function Person({
  person,
  onClose,
}: {
  person: StaffMember | null
  onClose: () => void
}) {
  return (
    <Sheet open={Boolean(person)} onOpenChange={(next) => (next ? undefined : onClose())}>
      <SheetContent className="sm:max-w-xl">
        {person ? (
          <>
            <SheetHeader>
              <SheetTitle>{person.full_name || person.phone}</SheetTitle>
              <SheetDescription className="flex flex-wrap items-center gap-2">
                <span className="tabular">{person.phone}</span>
                <Pill tone={ROLE_TONE[person.role]}>{ROLE_LABEL[person.role]}</Pill>
                {person.is_active ? null : <Pill tone="danger">O'chirilgan</Pill>}
              </SheetDescription>
            </SheetHeader>

            {/* Canvas behind the panels, the way the shell paints the page behind
                its cards: a `surface` panel on a `surface` drawer is not a
                panel, it is a heading with a rule under it. */}
            <SheetBody className="space-y-4 bg-canvas">
              <Details key={`d${person.id}`} person={person} />
              <RoleChange key={`r${person.id}`} person={person} onLeft={onClose} />
              <Activity key={`a${person.id}`} person={person} />
              <Trail person={person} />
            </SheetBody>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}

/** The two fields the office is allowed to correct on somebody else's
 *  account: a name taken down over the telephone, and an email nobody can
 *  spell out loud. Not the language and not the notification switches —
 *  those are the account holder's own. */
function Details({ person }: { person: StaffMember }) {
  const edit = useEditUser(person.id)
  const [name, setName] = useState(person.full_name)
  const [email, setEmail] = useState(person.email ?? "")

  const moved = name !== person.full_name || email !== (person.email ?? "")

  return (
    <Panel title="Ma'lumotlari">
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          edit.mutate({ full_name: name.trim(), email: email.trim() })
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Ismi">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              placeholder="Anvar Qodirov"
            />
          </Field>
          <Field label="Elektron pochta">
            <Input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              maxLength={120}
              type="email"
              placeholder="anvar@minibozor.uz"
            />
          </Field>
        </div>

        <Problem error={edit.error} />

        <div className="flex items-center gap-3">
          <Button type="submit" variant="secondary" size="sm" disabled={!moved || edit.isPending}>
            {edit.isPending ? <Loader2 className="animate-spin" /> : null}
            Saqlash
          </Button>
          {!moved && edit.isSuccess ? (
            <span className="text-micro text-good">Saqlandi</span>
          ) : null}
        </div>
      </form>
    </Panel>
  )
}

/**
 * The role, with the reason — which is the field this screen has never sent.
 *
 * The warning above the button is for one case only: a job turned into
 * `customer` is somebody who cannot open the panel tomorrow morning, and
 * the person pressing it is usually thinking "remove them from the list"
 * rather than "close the door". Said once, in the place it applies.
 */
function RoleChange({ person, onLeft }: { person: StaffMember; onLeft: () => void }) {
  const setRole = useSetRole(person.id)
  const [role, setRole_] = useState<UserRole>(person.role)
  const [note, setNote] = useState("")

  const changing = role !== person.role
  const locksOut = role === "customer"

  return (
    <Panel title="Lavozimi">
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          setRole.mutate(
            { role, note: note.trim() },
            {
              onSuccess: () => {
                setNote("")
                // They are no longer staff, so they are no longer in the list
                // behind this drawer. Leaving it open would be a panel about
                // a row that is not there.
                if (role === "customer") onLeft()
              },
            },
          )
        }}
      >
        <div>
          <span className="mb-1 block text-micro font-medium text-ink-soft">
            Yangi lavozimi
          </span>
          <Segmented
            label="Lavozimi"
            value={role}
            onChange={setRole_}
            options={ROLES.map((one) => ({ key: one.key, label: one.label }))}
          />
        </div>

        <Field label="Nima uchun" hint="Jurnalga shu yoziladi — bir yildan keyin o'qiladigan yagona joy">
          <Input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
            placeholder="Omborga o'tdi"
          />
        </Field>

        {changing && locksOut ? (
          <p className="rounded-control bg-warn-soft p-3 text-micro text-warn-ink">
            «Mijoz» — bu lavozim emas. {person.full_name || person.phone} shundan keyin
            boshqaruv panelini ocha olmaydi; buyurtmalari va tarixi joyida qoladi.
          </p>
        ) : null}

        <Problem error={setRole.error} />

        <Button
          type="submit"
          variant={locksOut ? "danger" : "secondary"}
          size="sm"
          disabled={!changing || setRole.isPending}
        >
          {setRole.isPending ? <Loader2 className="animate-spin" /> : null}
          {locksOut ? "Xodimlikdan chiqarish" : "Lavozimni o'zgartirish"}
        </Button>
      </form>
    </Panel>
  )
}

/**
 * Somebody left, or somebody came back — and it is not a delete.
 *
 * Their orders, the addresses they were delivered to and every audit row
 * naming them stay where they are; what changes is that the guard stops
 * letting them in. The last live admin cannot be switched off, and the
 * server's sentence is shown rather than the button being hidden: the person
 * who tried is the one who needs to read it.
 */
function Activity({ person }: { person: StaffMember }) {
  const setActive = useSetActive(person.id)
  const [note, setNote] = useState("")

  return (
    <Panel title="Hisobi">
      <form
        className="space-y-3"
        onSubmit={(event) => {
          event.preventDefault()
          setActive.mutate(
            { active: !person.is_active, note: note.trim() },
            { onSuccess: () => setNote("") },
          )
        }}
      >
        <p className="text-small text-ink-soft">
          {person.is_active
            ? "Hisob o'chirilsa, bu odam tizimga kira olmaydi. Buyurtmalari, manzillari va jurnaldagi yozuvlari joyida qoladi — bu o'chirish emas."
            : "Hisob hozir o'chirilgan: bu odam tizimga kira olmaydi."}
        </p>

        <Field label="Nima uchun" hint="Jurnalga shu yoziladi">
          <Input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
            placeholder={person.is_active ? "Ishdan bo'shadi" : "Ishga qaytdi"}
          />
        </Field>

        <Problem error={setActive.error} />

        <Button
          type="submit"
          variant={person.is_active ? "danger" : "secondary"}
          size="sm"
          disabled={setActive.isPending}
        >
          {setActive.isPending ? <Loader2 className="animate-spin" /> : null}
          {person.is_active ? "Hisobni o'chirish" : "Hisobni qayta yoqish"}
        </Button>
      </form>
    </Panel>
  )
}

/**
 * What this colleague has been doing — the question an office actually asks
 * about one of its own.
 *
 * Ten rows and a way through to the whole trail, rather than a second log on
 * a screen that is about a person. `/jurnal` already filters by actor, so the
 * link is the filter.
 */
function Trail({ person }: { person: StaffMember }) {
  const trail = useAudit({ actor_id: String(person.id), size: 10 })
  const rows = trail.data?.items ?? []

  return (
    <Panel
      title="So'nggi harakatlari"
      aside={
        <Button asChild variant="ghost" size="sm">
          <Link to={`/jurnal?actor_id=${person.id}`}>
            <ScrollText />
            Jurnalda
          </Link>
        </Button>
      }
      bare
    >
      {trail.isLoading ? (
        <p className="p-4 text-small text-ink-soft">Yuklanmoqda…</p>
      ) : rows.length === 0 ? (
        <p className="p-4 text-small text-ink-soft">
          Hali hech narsa qilmagan — yoki hali tizimga kirmagan.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((row) => (
            <li key={row.id} className="flex items-baseline gap-3 px-4 py-2">
              <span className="w-28 shrink-0 text-micro tabular text-ink-faint">
                {dateTime(row.created_at)}
              </span>
              <span className="min-w-0 flex-1 text-small">
                {/* The journal's own words, imported rather than invented
                    again: this list and `/jurnal` are the same rows, and two
                    spellings of `order.deliver` on two screens is how a
                    vocabulary drifts. */}
                <span className="font-medium">{ACTIONS[row.action] ?? row.action}</span>
                <span className="text-ink-soft">
                  {" · "}
                  {ENTITIES.find((one) => one.value === row.entity)?.label ?? row.entity}
                  {row.entity_id ? ` #${row.entity_id}` : ""}
                </span>
                {row.note ? (
                  <span className="block truncate text-micro text-ink-soft">{row.note}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/* -------------------------------------------------------------------- bits */

/** A label over a field, with the sentence that stops the question being
 *  asked underneath it. Local to this file because it is the shape a form on
 *  a people screen takes, and one more shared component for four uses is a
 *  component nobody finds. */
export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1 block text-micro font-medium text-ink-soft">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-micro text-ink-faint">{hint}</span> : null}
    </label>
  )
}
