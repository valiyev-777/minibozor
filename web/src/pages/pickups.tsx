/**
 * Olib kelish — the van sent inward.
 *
 * A pickup run is a round of collections: approved return requests fetched
 * from customers' doors. It is not an order delivery and it is not a market
 * run, and the difference matters on this screen because everything here
 * moves backwards — the goods are coming towards the building, and the
 * customer at each door is waiting for an answer about money.
 *
 * **`collected` and `received` are two different people's claims, and they
 * stay two.** The courier says he has the goods; the warehouse says they
 * arrived. Collapsing the pair into one "done" would make the sentence *"he
 * collected it and it never reached us"* unsayable, which is the one sentence
 * a screen about goods in a van exists to be able to say. So a run sits in
 * `collected` until somebody at the bench presses the other button.
 *
 * **A door has three answers, not two.** `collected` is `boolean | null`, and
 * null is not "no" — it is *nobody tried this door yet*. A round half driven
 * looks completely different from a round where three customers were out, and
 * drawing null as a failure would invent three customers who were out.
 *
 * **Receiving moves no stock, on purpose.** Each parcel is opened separately
 * on the returns screen: arriving and being whole are two different facts,
 * established by two different people. The screen says so, because a
 * warehouse that presses receive and then waits for its shelf counts to move
 * is a warehouse that will press it again.
 *
 * **The role decides, and the server decides first.** Building a run is the
 * office's — the server refuses it to anybody else — so the bench is not
 * shown a button it cannot use; it is shown the sentence instead. Receiving
 * is the bench's act and the one the bench's own menu brings it here for.
 */

import {
  Camera,
  Check,
  ChevronLeft,
  CircleSlash,
  DoorOpen,
  Loader2,
  PackageCheck,
  Truck,
  X,
} from "lucide-react"
import { useMemo, useState } from "react"

import { Empty, PageHeader, Panel, Pill, Problem, Segmented, Stat, Waiting, type Tone } from "@/components/page"
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
import { cn } from "@/lib/cn"
import { ageBrief, dateTime, groups, minutesSince, money } from "@/lib/format"
import {
  useCouriers,
  useCreatePickup,
  usePickups,
  useReceivePickup,
  useReturns,
} from "@/lib/queries"
import { useSession } from "@/lib/session"
import type { PickupLine, PickupRun, PickupRunStatus } from "@/lib/types"

const STATUS: Record<PickupRunStatus, { label: string; tone: Tone }> = {
  open: { label: "Yo'lda", tone: "warn" },
  collected: { label: "Kuryerda", tone: "brand" },
  received: { label: "Qabul qilindi", tone: "good" },
  cancelled: { label: "Bekor qilingan", tone: "neutral" },
}

type Filter = "all" | PickupRunStatus

export function PickupsPage() {
  const { staff } = useSession()
  const role = staff?.role
  // The server answers 403 to anybody but the office on the create door, and
  // both roles on the receive one. Neither fact is guessed here twice: the
  // list is the same for everybody, the two acts are not.
  const mayBuild = role === "admin"
  const mayReceive = role === "admin" || role === "warehouse"

  const [filter, setFilter] = useState<Filter>("all")
  const [openId, setOpenId] = useState<number | null>(null)
  const [building, setBuilding] = useState(false)

  // One request for every status rather than one per tab: a handful of runs,
  // and the counts on the tabs are then true rather than "the tab you are
  // looking at".
  const runs = usePickups("")

  const all = useMemo(
    () =>
      [...(runs.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [runs.data],
  )
  const counts = useMemo(() => {
    const out: Record<string, number> = { all: all.length }
    for (const run of all) out[run.status] = (out[run.status] ?? 0) + 1
    return out
  }, [all])
  const shown = filter === "all" ? all : all.filter((run) => run.status === filter)

  const open = counts.open ?? 0
  const waiting = counts.collected ?? 0
  const doors = all
    .filter((run) => run.status === "open")
    .reduce((sum, run) => sum + run.lines.length, 0)

  const run = openId ? all.find((one) => one.id === openId) : undefined
  if (run) {
    return (
      <Run
        run={run}
        mayReceive={mayReceive}
        onBack={() => setOpenId(null)}
      />
    )
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Olib kelish"
        subtitle="Tasdiqlangan qaytarishlarni mijoz eshigidan olib kelish"
      >
        {mayBuild ? (
          <Button className="gap-2" onClick={() => setBuilding(true)}>
            <Truck />
            Reys yig'ish
          </Button>
        ) : (
          <span className="text-micro text-ink-soft">
            Reysni ofis yig'adi — bu yerda kelgan reys qabul qilinadi
          </span>
        )}
      </PageHeader>

      <Problem error={runs.error} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label="Yo'ldagi reys"
          value={groups(open)}
          hint={`${groups(doors)} eshik`}
          icon={Truck}
          tone={open > 0 ? "warn" : "neutral"}
        />
        <Stat
          label="Qabul kutmoqda"
          value={groups(waiting)}
          hint="kuryer olgan, omborga kelmagan"
          icon={PackageCheck}
          tone={waiting > 0 ? "brand" : "neutral"}
        />
        <Stat label="Jami reys" value={groups(all.length)} hint="shu ro'yxatda" />
      </div>

      <Segmented
        label="Reys holati"
        value={filter}
        onChange={setFilter}
        options={[
          { key: "all", label: `Hammasi · ${counts.all ?? 0}` },
          { key: "open", label: `Yo'lda · ${counts.open ?? 0}` },
          { key: "collected", label: `Kuryerda · ${counts.collected ?? 0}` },
          { key: "received", label: `Qabul qilindi · ${counts.received ?? 0}` },
        ]}
      />

      {runs.isLoading ? <Waiting what="Reyslar" /> : null}

      {!runs.isLoading && shown.length === 0 ? (
        <Empty
          icon={Truck}
          title="Reys yo'q"
          what={
            mayBuild
              ? "Reys tasdiqlangan qaytarish arizalaridan yig'iladi: kuryerni tanlang, arizalarni belgilang."
              : "Ofis reys yig'sa, u shu yerda ko'rinadi. Kuryer eshiklarni belgilagach, reysni qabul qilasiz."
          }
        >
          {/* Secondary, not a second filled button: the act already has its
              one primary in the header, and two blue buttons for one act is
              the screen telling the reader there are two acts. */}
          {mayBuild ? (
            <Button variant="secondary" onClick={() => setBuilding(true)}>
              Reys yig'ish
            </Button>
          ) : null}
        </Empty>
      ) : null}

      <ul className="space-y-2">
        {shown.map((one) => (
          <li key={one.id}>
            <RunRow run={one} onOpen={() => setOpenId(one.id)} />
          </li>
        ))}
      </ul>

      {mayBuild ? (
        <BuildRun
          open={building}
          onClose={() => setBuilding(false)}
          onMade={(made) => {
            setBuilding(false)
            setOpenId(made.id)
          }}
        />
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ one row */

function RunRow({ run, onOpen }: { run: PickupRun; onOpen: () => void }) {
  const got = run.lines.filter((line) => line.collected === true).length
  const missed = run.lines.filter((line) => line.collected === false).length
  const untried = run.lines.filter((line) => line.collected === null).length

  return (
    <Panel className="transition-colors hover:border-line">
      <button type="button" onClick={onOpen} className="flex w-full items-center gap-3 text-start">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-body font-semibold tabular">{run.code}</span>
            <Pill tone={STATUS[run.status].tone}>{STATUS[run.status].label}</Pill>
          </div>
          <div className="truncate text-small text-ink-soft">
            {run.courier_name} · {groups(run.lines.length)} eshik ·{" "}
            {ageBrief(minutesSince(run.created_at))} oldin
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-micro">
            {got > 0 ? <span className="text-good">{groups(got)} olindi</span> : null}
            {missed > 0 ? <span className="text-danger">{groups(missed)} olinmadi</span> : null}
            {untried > 0 ? (
              <span className="text-ink-faint">{groups(untried)} urinilmagan</span>
            ) : null}
            {run.note ? <span className="truncate text-ink-soft">{run.note}</span> : null}
          </div>
        </div>
        <span className="shrink-0 text-micro text-ink-faint">Ochish</span>
      </button>
    </Panel>
  )
}

/* --------------------------------------------------------------- one run */

function Run({
  run,
  mayReceive,
  onBack,
}: {
  run: PickupRun
  mayReceive: boolean
  onBack: () => void
}) {
  const receive = useReceivePickup(run.id)
  const [photo, setPhoto] = useState<string | null>(null)

  const canReceive = run.next_statuses.includes("received")
  const got = run.lines.filter((line) => line.collected === true).length

  return (
    <div className="space-y-4">
      <PageHeader
        title={run.code}
        subtitle={`${run.courier_name} · ${groups(run.lines.length)} eshik`}
      >
        <Button variant="ghost" className="gap-1" onClick={onBack}>
          <ChevronLeft />
          Ro'yxatga
        </Button>
        {canReceive && mayReceive ? (
          <Button
            className="gap-2"
            disabled={receive.isPending}
            onClick={() => receive.mutate()}
          >
            {receive.isPending ? <Loader2 className="animate-spin" /> : <PackageCheck />}
            Omborga qabul qilish
          </Button>
        ) : null}
      </PageHeader>

      <Problem error={receive.error} />

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Reys" className="lg:col-span-1">
          <dl className="space-y-2 text-small">
            <Line name="Holati">
              <Pill tone={STATUS[run.status].tone}>{STATUS[run.status].label}</Pill>
            </Line>
            <Line name="Kuryer">{run.courier_name}</Line>
            <Line name="Yig'ilgan">{dateTime(run.created_at)}</Line>
            <Line name="Kuryer olgan">
              {run.collected_at ? dateTime(run.collected_at) : <Quiet>hali yo'q</Quiet>}
            </Line>
            <Line name="Omborga kelgan">
              {run.received_at ? dateTime(run.received_at) : <Quiet>hali yo'q</Quiet>}
            </Line>
            {run.note ? <Line name="Izoh">{run.note}</Line> : null}
          </dl>

          {/* Why the two claims are two, said where the second one is made. */}
          {run.status === "open" ? (
            <p className="mt-3 rounded-control bg-line-soft p-3 text-micro text-ink-soft">
              Eshiklarni kuryer o'z ilovasida belgilaydi. Shu yerdan reysni oldinga
              surib bo'lmaydi — kuryer nimani olganini o'zi aytadi.
            </p>
          ) : null}

          {run.status === "collected" ? (
            <p className="mt-3 rounded-control bg-brand-soft p-3 text-micro text-brand-deep">
              Kuryer {groups(got)} ta qopni olganini aytdi. Ombor qabul qilganda{" "}
              <span className="font-medium">zaxira qimirlamaydi</span>: har bir qop
              «Qaytarishlar» ekranida alohida ochiladi va butunligi o'sha yerda
              yoziladi.
            </p>
          ) : null}

          {run.status === "collected" && !mayReceive ? (
            <p className="mt-3 rounded-control bg-warn-soft p-3 text-micro text-warn-ink">
              Qabul qilishni ombor bosadi — server boshqasidan qabul qilmaydi.
            </p>
          ) : null}

          {run.status === "received" ? (
            <p className="mt-3 rounded-control bg-good-soft p-3 text-micro text-good">
              Qoplar omborda. Zaxira hali o'zgargani yo'q — har bir qop
              «Qaytarishlar»da ochilganda o'zgaradi.
            </p>
          ) : null}
        </Panel>

        <Panel title={`Eshiklar · ${groups(run.lines.length)}`} bare className="lg:col-span-2">
          {run.lines.length === 0 ? (
            <Empty bare what="Bu reysda eshik yo'q." />
          ) : (
            <ul className="divide-y divide-line">
              {run.lines.map((line) => (
                <li key={line.id}>
                  <Door line={line} onPhoto={setPhoto} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Dialog open={Boolean(photo)} onOpenChange={(next) => (next ? null : setPhoto(null))}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>Kuryerning surati</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {photo ? (
              <img
                src={mediaUrl(photo)}
                alt="Eshikdagi surat"
                className="mx-auto max-h-[60vh] rounded-panel"
              />
            ) : null}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  )
}

/** One door: who, what, and which of the three answers it got. */
function Door({
  line,
  onPhoto,
}: {
  line: PickupLine
  onPhoto: (path: string) => void
}) {
  const answer =
    line.collected === true
      ? { label: "Olindi", tone: "good" as Tone, icon: Check }
      : line.collected === false
        ? { label: "Olinmadi", tone: "danger" as Tone, icon: X }
        : { label: "Urinilmagan", tone: "neutral" as Tone, icon: DoorOpen }
  const Icon = answer.icon

  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span
        className={cn(
          "grid size-8 shrink-0 place-items-center rounded-full",
          line.collected === true && "bg-good-soft text-good",
          line.collected === false && "bg-danger-soft text-danger",
          line.collected === null && "bg-line-soft text-ink-faint",
        )}
      >
        <Icon className="size-4" />
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{line.customer_name || "Ismsiz"}</span>
          <Pill tone={answer.tone}>{answer.label}</Pill>
          <span className="text-micro tabular text-ink-soft">{line.order_code}</span>
        </div>
        <div className="truncate text-small text-ink-soft">{line.product_title}</div>
        <div className="text-micro text-ink-soft">{line.address_line}</div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-ink-faint">
          <span className="tabular">{line.customer_phone}</span>
          {line.reason ? <span>Sabab: {line.reason}</span> : null}
          {line.attempted_at ? <span>{dateTime(line.attempted_at)}</span> : null}
        </div>

        {/* The sentence somebody decides on: what happens to a parcel that
            was not collected is decided from this line and nothing else. */}
        {line.note ? (
          <p
            className={cn(
              "mt-2 rounded-control p-2 text-micro",
              line.collected === false
                ? "bg-danger-soft text-danger"
                : "bg-line-soft text-ink-soft",
            )}
          >
            {line.note}
          </p>
        ) : null}
      </div>

      {line.photo_url ? (
        <button
          type="button"
          onClick={() => onPhoto(line.photo_url as string)}
          className="shrink-0 rounded-control border border-line p-0.5 transition-colors hover:border-brand"
          aria-label="Suratni ko'rish"
        >
          <img
            src={mediaUrl(line.photo_url)}
            alt=""
            className="size-14 rounded-[calc(var(--radius-control)-2px)] object-cover"
          />
        </button>
      ) : line.collected !== null ? (
        /* No photograph is only worth a square once somebody has been to the
           door. Before that it is not an absence, it is a door. */
        <span
          className="grid size-14 shrink-0 place-items-center rounded-control bg-line-soft text-ink-faint"
          title="Surat yo'q"
        >
          <Camera className="size-4" />
        </span>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------ building a run */

/**
 * A courier, the approved returns to fetch, and a note.
 *
 * Only approved requests may ride: one still being decided is not something
 * to send a van for, and a refused one has nothing to collect. A request
 * already on a live run is refused too — two vans for one parcel is a wasted
 * trip and a courier told at the door that the goods are gone. Both refusals
 * arrive as a sentence from the server and both are shown rather than
 * swallowed, because the person who ticked the box is the one who needs to
 * read them.
 */
function BuildRun({
  open,
  onClose,
  onMade,
}: {
  open: boolean
  onClose: () => void
  onMade: (run: PickupRun) => void
}) {
  const couriers = useCouriers()
  const returns = useReturns("approved")
  const create = useCreatePickup()

  const [courier, setCourier] = useState("")
  const [picked, setPicked] = useState<number[]>([])
  const [note, setNote] = useState("")

  const waiting = returns.data ?? []
  const ready = courier !== "" && picked.length > 0

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          create.reset()
          onClose()
        }
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Reys yig'ish</DialogTitle>
          <DialogDescription>
            Faqat ofis tasdiqlagan arizalar reysga tushadi. Boshqa reysda ketayotgan
            ariza qabul qilinmaydi.
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          <label className="block">
            <span className="mb-1 block text-micro font-medium text-ink-soft">Kuryer</span>
            <select
              value={courier}
              onChange={(event) => setCourier(event.target.value)}
              className="h-control w-full min-w-0 rounded-control border border-transparent bg-line-soft px-3 text-small text-ink outline-none transition-[background-color,border-color,box-shadow] focus-visible:border-brand focus-visible:bg-surface focus-visible:ring-2 focus-visible:ring-brand/25"
            >
              <option value="">Tanlang</option>
              {(couriers.data ?? []).map((one) => (
                <option key={one.id} value={one.id}>
                  {one.full_name || one.phone}
                </option>
              ))}
            </select>
          </label>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-micro font-medium text-ink-soft">
                Tasdiqlangan arizalar
              </span>
              <span className="text-micro text-ink-faint">
                {groups(picked.length)} ta belgilandi
              </span>
            </div>

            {returns.isLoading ? <Waiting what="Arizalar" /> : null}

            {!returns.isLoading && waiting.length === 0 ? (
              <Empty
                icon={CircleSlash}
                title="Tasdiqlangan ariza yo'q"
                what="Ofis «Qaytarishlar» ekranida arizani tasdiqlagach, u shu ro'yxatda paydo bo'ladi."
              />
            ) : (
              <ul className="space-y-1">
                {waiting.map((one) => {
                  const on = picked.includes(one.id)
                  return (
                    <li key={one.id}>
                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={on}
                        onClick={() =>
                          setPicked((was) =>
                            was.includes(one.id)
                              ? was.filter((id) => id !== one.id)
                              : [...was, one.id],
                          )
                        }
                        className={cn(
                          "flex w-full items-start gap-3 rounded-control border p-2 text-start transition-colors",
                          on
                            ? "border-brand bg-brand-soft"
                            : "border-line bg-surface hover:bg-line-soft",
                        )}
                      >
                        <span
                          className={cn(
                            "mt-0.5 grid size-5 shrink-0 place-items-center rounded-[6px] border",
                            on ? "border-brand bg-brand text-brand-ink" : "border-line",
                          )}
                        >
                          {on ? <Check className="size-3.5" /> : null}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex flex-wrap items-center gap-2">
                            <span className="text-small font-medium">
                              {one.customer_name || one.customer_phone}
                            </span>
                            <span className="text-micro tabular text-ink-soft">
                              {one.order_code}
                            </span>
                          </span>
                          <span className="block truncate text-micro text-ink-soft">
                            {one.product_title} · {one.reason}
                          </span>
                          <span className="block text-micro text-ink-faint">
                            {money(one.refund_amount)} ·{" "}
                            {ageBrief(minutesSince(one.created_at))} oldin
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <label className="block">
            <span className="mb-1 block text-micro font-medium text-ink-soft">
              Izoh — kuryer o'qiydi
            </span>
            <Input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={200}
              placeholder="Ertalabki aylanma"
            />
          </label>

          <Problem error={create.error} />
        </DialogBody>

        <DialogFooter showCloseButton>
          <Button
            disabled={!ready || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  courier_id: Number(courier),
                  return_request_ids: picked,
                  note: note.trim(),
                },
                {
                  onSuccess: (made) => {
                    setPicked([])
                    setNote("")
                    setCourier("")
                    onMade(made)
                  },
                },
              )
            }
          >
            {create.isPending ? <Loader2 className="animate-spin" /> : null}
            {picked.length === 0
              ? "Ariza belgilanmagan"
              : `Reysga ${groups(picked.length)} ta ariza`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* --------------------------------------------------------------- small parts */

function Line({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="shrink-0 text-micro text-ink-soft">{name}</dt>
      <dd className="min-w-0 truncate text-end">{children}</dd>
    </div>
  )
}

function Quiet({ children }: { children: React.ReactNode }) {
  return <span className="text-ink-faint">{children}</span>
}
