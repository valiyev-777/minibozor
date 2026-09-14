/**
 * The room, drawn.
 *
 * This is the screen the shop is judged by, and it is the answer to the one
 * question the warehouse exists to answer: where is it.
 *
 * **The racks are drawn as racks.** Bottom row at the bottom, rack letter and
 * column numbers on the edges, the way the shelf itself is labelled — so that
 * standing in front of the shelf and looking at the screen are the same act.
 * Nothing here is hard-coded to three units of four by four: the racks come
 * from the API, and a fourth one appears the moment the office builds it —
 * which is now a form on this screen rather than a line of source and a
 * deployment. Shelving goes up on a Saturday; it should not wait for a
 * release on the Monday.
 *
 * **The staging areas sit above the racks**, as their own row, because they
 * are not shelves — they are the states goods pass through. A `QABUL` tile
 * with something in it older than an hour is the one thing on this screen
 * that should be impossible to ignore, and it is the only tile allowed to
 * shout.
 *
 * **Search dims rather than filters.** Type a name or paste a barcode and the
 * cells holding it light up while the rest of the room fades: a filtered grid
 * loses the shape of the room, and the shape is how somebody knows where to
 * walk.
 *
 * ------------------------------------------------- and it is where work starts
 *
 * This is also the bench's first screen — it is where a warehouse hand lands
 * after signing in — and for a long time it answered only "where is it". A
 * picker standing here with an empty trolley had to know, unprompted, that
 * there might be orders waiting on another screen; the queue lengths lived
 * behind menu items, and a queue nobody can see the length of is a queue that
 * grows.
 *
 * ------------------------------------------------------- and where things go
 *
 * **Moving goods is done by pointing at the room**, not by typing a code into
 * a box. Picking a line — or the whole cell at once, which is the ordinary
 * case for a model standing in four sizes — turns every cell on this map into
 * a target: the room stays exactly where it was, each cell says how much room
 * it has and whether it already holds this model, and one click on it finishes
 * the move. The cell it came from is drawn as the source and cannot be picked.
 *
 * Capacity is shown and never enforced — a cell with no room left is still a
 * choosable place, because on a market day it is sometimes the right one, and
 * a system that refuses it just gets lied to. What the server refuses is said
 * out loud, beside the bar that asked for it, and what succeeded is said too:
 * where it went and what is standing there now.
 *
 * So the room now opens with **the work**: three rows, always the same three,
 * in the order a day actually runs — goods in, orders out, and counting. They
 * carry their own numbers, they are the whole navigation on a phone (where
 * the menu is behind a button), and a queue that has been standing too long
 * says so in red. Under them, the room's own figures: how much is on the
 * shelves and how much of the shelving is spoken for.
 */

import {
  ArrowRight,
  Check,
  ChevronRight,
  Grid3x3,
  Layers,
  Loader2,
  PackageCheck,
  PackageSearch,
  Plus,
  RotateCcw,
  Search,
  X,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { Empty, Fill, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, ageBrief, groups, percent, units } from "@/lib/format"
import {
  useAddRack,
  useEmptyStock,
  useExtendRack,
  useLocation,
  useMove,
  useMoveCell,
  usePickQueue,
  useRetiredCells,
  useSetCellActive,
  useShelfMap,
  useSupplies,
  useWhereIs,
} from "@/lib/queries"
import { canReach } from "@/lib/nav"
import { useSession } from "@/lib/session"
import type { Role } from "@/lib/session"
import type { CellContent, Location, LocationDetail } from "@/lib/types"

// A tile that has been standing this long is the one thing on the screen that
// should be impossible to ignore. An hour, because a sack that arrived before
// lunch and is still there is goods nobody has counted.
const SHOUT_AFTER_MINUTES = 60

/**
 * Goods on their way from one place to another, waiting for a destination.
 *
 * Two shapes, because there are two real jobs. A **cell** move is what is
 * standing there — all of it, or the lines somebody ticked — and carries no
 * quantities: one request, read inside the transaction, nothing left behind
 * halfway. A **line** move carries a count, because a picker taking two of
 * five is a real thing; it starts at the whole line, so the common case is
 * still no typing.
 */
type Moving =
  | { kind: "line"; from: string; line: CellContent; qty: number }
  | {
      kind: "cell"
      from: string
      lines: CellContent[]
      /** Empty means everything standing in the cell. */
      variant_ids: number[]
      units: number
    }

/** What the map needs to know while it is being used as a destination picker. */
type Targeting = {
  from: string
  /** Cells already holding the model that is moving — the obvious answer. */
  holds: Set<string>
  pending: boolean
  onPick: (code: string) => void
}

/** What is moving, in words, for the bar and for the sentence afterwards. */
function movingWords(moving: Moving): string {
  if (moving.kind === "line") {
    return `${moving.line.product_title} · ${moving.line.variant_label} — ${units(moving.qty)}`
  }
  if (moving.variant_ids.length) {
    return `${moving.lines.length} xil — ${units(moving.units)}`
  }
  return `${moving.from} dagi hammasi — ${units(moving.units)}`
}

/** The model on the move, when it is one model. Two are not "shu model". */
function movingModel(moving: Moving): { id: number; title: string } | null {
  const lines = moving.kind === "line" ? [moving.line] : moving.lines
  const first = lines[0]
  if (!first) return null
  if (lines.some((line) => line.product_id !== first.product_id)) return null
  return { id: first.product_id, title: first.product_title }
}

export function ShelfMapPage() {
  const room = useShelfMap()
  // The holes in the room, on their own door. They are drawn in the grid and
  // counted in nothing — see `Racks`.
  const gone = useRetiredCells()
  const [needle, setNeedle] = useState("")
  const found = useWhereIs(needle)
  const [open, setOpen] = useState<string | null>(null)

  // Goods in the hand, so to speak: chosen, and looking for somewhere to go.
  const [moving, setMoving] = useState<Moving | null>(null)
  const [landed, setLanded] = useState<{ to: LocationDetail; what: string } | null>(null)
  const move = useMove()
  const moveCell = useMoveCell()
  const pending = move.isPending || moveCell.isPending
  const refused = move.error ?? moveCell.error

  // Which cells the search lit up. A set rather than a filter, because the
  // room keeps its shape and the rest of it dims.
  const lit = useMemo(() => {
    const codes = new Set<string>()
    for (const row of found.data ?? []) {
      for (const place of row.places) codes.add(place.code)
    }
    return codes
  }, [found.data])

  const searching = needle.trim().length > 1

  // Where else this model is already standing. Bringing a split model back
  // together is most of why anybody moves anything, so the cells that would
  // do it say so rather than leaving somebody to remember.
  const model = moving ? movingModel(moving) : null
  const modelId = model?.id ?? null
  const elsewhere = useWhereIs(model?.title ?? "")
  const holds = useMemo(() => {
    const codes = new Set<string>()
    if (modelId === null) return codes
    for (const row of elsewhere.data ?? []) {
      if (row.product_id !== modelId) continue
      for (const place of row.places) codes.add(place.code)
    }
    return codes
  }, [elsewhere.data, modelId])

  function start(next: Moving) {
    move.reset()
    moveCell.reset()
    setLanded(null)
    // The sheet is over the map, and the map is now the control.
    setOpen(null)
    setMoving(next)
  }

  function stop() {
    move.reset()
    moveCell.reset()
    setMoving(null)
  }

  function pick(code: string) {
    if (!moving || pending) return
    // A line emptied down to nought is somebody halfway through typing, not a
    // move; the bar keeps the field and the map keeps waiting.
    if (moving.kind === "line" && moving.qty < 1) return
    const what = movingWords(moving)
    const done = (to: LocationDetail) => {
      setMoving(null)
      setLanded({ to, what })
    }
    if (moving.kind === "line") {
      move.mutate(
        {
          variant_id: moving.line.variant_id,
          qty: moving.qty,
          from_code: moving.from,
          to_code: code,
        },
        { onSuccess: done },
      )
    } else {
      moveCell.mutate(
        {
          from_code: moving.from,
          to_code: code,
          variant_ids: moving.variant_ids.length ? moving.variant_ids : undefined,
        },
        { onSuccess: done },
      )
    }
  }

  // Escape is the way out of any mode, and somebody who started a move by
  // mistake should not have to hunt for the word "bekor".
  useEffect(() => {
    if (!moving) return
    const listen = (event: KeyboardEvent) => {
      if (event.key === "Escape") stop()
    }
    window.addEventListener("keydown", listen)
    return () => window.removeEventListener("keydown", listen)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moving])

  const targeting: Targeting | null = moving
    ? { from: moving.from, holds, pending, onPick: pick }
    : null

  return (
    <div className={cn("space-y-4", moving && "pb-28")}>
      <PageHeader title="Ombor xaritasi" subtitle="Nima qayerda turibdi">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={needle}
            onChange={(event) => setNeedle(event.target.value)}
            placeholder="Nomi yoki shtrix-kod"
            className="h-control w-56 pl-8"
            aria-label="Qidirish" />
          {needle ? (
            <button
              type="button"
              onClick={() => setNeedle("")}
              aria-label="Tozalash"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint">
              <X className="size-4" />
            </button>
          ) : null}
        </div>
        <AddRack />
        <EmptyRoom />
      </PageHeader>

      <Problem error={room.error} />

      {landed ? (
        <Landed landed={landed} onOpen={setOpen} onClose={() => setLanded(null)} />
      ) : null}

      {searching && !moving ? <FoundSummary lit={lit} rows={found.data ?? []} /> : null}

      {room.isLoading ? <Waiting what="Xona" /> : null}

      {/* The work first, and it is drawn whether or not the room has loaded:
          it is the reason somebody signed in, and it does not depend on a
          map of the shelves to be true. */}
      <Work />

      {room.data ? (
        <>
          <Staging
            tiles={[...room.data.staging, ...room.data.couriers]}
            lit={searching && !moving ? lit : null}
            onOpen={setOpen}
            targeting={targeting}
          />
          <Racks
            cells={room.data.cells}
            retired={gone.data ?? []}
            lit={searching && !moving ? lit : null}
            onOpen={setOpen}
            targeting={targeting}
          />
        </>
      ) : null}

      <CellDialog code={open} onClose={() => setOpen(null)} onMove={start} />

      {moving ? (
        <MoveBar
          moving={moving}
          onQty={(qty) => setMoving(moving.kind === "line" ? { ...moving, qty } : moving)}
          pending={pending}
          error={refused}
          onCancel={stop}
        />
      ) : null}
    </div>
  )
}

/**
 * Where it went, said once and out of the way.
 *
 * The move already returned the destination's whole state and it used to be
 * thrown away, which left the person who moved forty pairs of shoes staring at
 * a sheet that had closed. What matters afterwards is two things: it happened,
 * and what is standing in that cell now — because "it went to A-02-03" is only
 * reassuring if A-02-03 turns out to hold what you expect.
 */
function Landed({
  landed,
  onOpen,
  onClose,
}: {
  landed: { to: LocationDetail; what: string }
  onOpen: (code: string) => void
  onClose: () => void
}) {
  return (
    <div
      role="status"
      className="no-print flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control border border-good/25 bg-good-soft p-3 text-small text-good"
    >
      <Check className="size-4 shrink-0" />
      <span className="min-w-0 flex-1">
        {landed.what} → <b className="tabular font-semibold">{landed.to.code}</b>. Endi u
        yerda {units(landed.to.units)}
        {landed.to.products ? ` · ${landed.to.products} xil` : ""}.
      </span>
      <Button variant="ghost" size="sm" onClick={() => onOpen(landed.to.code)}>
        Ochish
      </Button>
      <Button variant="ghost" size="sm" onClick={onClose} aria-label="Yopish">
        <X className="size-4" />
      </Button>
    </div>
  )
}

/**
 * The bar that stands between choosing goods and choosing a place.
 *
 * Pinned to the bottom of the window rather than dropped into the page: it is
 * a mode, the map above it is the control, and on a phone held in one hand
 * the bottom is where the thumb already is. It says what is in the hand, it
 * says what to do next, and it carries the refusal when there is one — which
 * is the whole reason a failed move used to look like nothing happening.
 */
function MoveBar({
  moving,
  onQty,
  pending,
  error,
  onCancel,
}: {
  moving: Moving
  onQty: (qty: number) => void
  pending: boolean
  error: unknown
  onCancel: () => void
}) {
  const whole = moving.kind === "line" ? moving.line.qty : moving.units

  return (
    <div className="no-print sticky bottom-2 z-30 space-y-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-panel border border-brand bg-surface p-3 shadow-raised">
        <span className="grid size-10 shrink-0 place-items-center rounded-control bg-brand-soft text-brand-deep">
          <ArrowRight className="size-5" />
        </span>

        {/* A floor under the width of the words: squeezed to "Erk…" by a
            quantity box, the bar stops saying what is in the hand. Below that
            the controls wrap onto their own line instead. */}
        <span className="min-w-[9rem] flex-1">
          <span className="block truncate text-small font-semibold">{movingWords(moving)}</span>
          {/* The instruction wraps rather than truncates: on a phone it is the
              half of this bar somebody actually needs, and a cut-off
              "qayerga? xarita…" teaches nothing. */}
          <span className="block text-micro text-ink-soft">
            <b className="tabular font-medium text-ink">{moving.from}</b> dan —{" "}
            {pending ? "ko'chirilmoqda…" : "qayerga? yacheykani bosing"}
          </span>
        </span>

        {/* A part of a line, for the picker taking two of five. Secondary: it
            starts at everything, so the common move needs no keystroke. */}
        {moving.kind === "line" ? (
          <label className="flex shrink-0 items-center gap-1.5">
            <span className="text-micro text-ink-soft">Nechta</span>
            <Input
              value={String(moving.qty)}
              onChange={(event) => {
                const typed = Number(event.target.value.replace(/\D/g, "")) || 0
                onQty(Math.min(Math.max(typed, 0), whole))
              }}
              inputMode="numeric"
              aria-label="Nechta ko'chirish"
              className="h-control w-16 text-center tabular"
            />
            <span className="text-micro tabular text-ink-faint">/ {groups(whole)}</span>
          </label>
        ) : null}

        {pending ? <Loader2 className="size-4 shrink-0 animate-spin text-brand" /> : null}

        <Button type="button" variant="secondary" size="sm" onClick={onCancel}>
          Bekor <span className="ms-1 hidden text-micro text-ink-faint sm:inline">Esc</span>
        </Button>
      </div>

      {/* Beside the control that caused it: the room is still on screen
          behind this, and the sentence names the cell that refused. */}
      {error ? (
        <div className="rounded-control bg-surface shadow-raised">
          <Problem error={error} />
        </div>
      ) : null}
    </div>
  )
}

// ---------------------------------------------------------------------- work

/**
 * The three jobs of a day at the bench, with their queues on them.
 *
 * Always the same three, always in this order, and drawn even when they are
 * all empty — a strip that appears and disappears is a strip nobody learns
 * the shape of, and "nothing waiting" is worth reading at a glance. The
 * counts come from the queues themselves rather than from the office's
 * dashboard: this is the bench's own work, and it should not go quiet because
 * a figure the shop cares about happens to be unavailable.
 *
 * A queue that has been standing too long turns red. An hour for picking,
 * because an order taken this morning and still on the board at noon is a
 * customer being let down; an evening for sacks, because a run judged
 * against an hour would be red every market day.
 */

const PICK_LATE_MINUTES = 60
const SACK_LATE_MINUTES = 14 * 60

function Work() {
  const { staff } = useSession()
  const queue = usePickQueue()
  const sacks = useSupplies("draft")

  const role = staff?.role ?? "warehouse"
  const picking = (queue.data ?? []).filter((task) => task.status !== "picked")
  const oldestPick = Math.max(0, ...picking.map((task) => task.age_minutes))
  const unopened = sacks.data ?? []
  const oldestSack = Math.max(0, ...unopened.map((sack) => sack.age_minutes))

  const jobs = [
    {
      to: "/qabul",
      icon: PackageSearch,
      label: "Qabul",
      hint: unopened.length
        ? `${unopened.length > 1 ? "eng eskisi " : ""}${ageBrief(oldestSack)} turgan`
        : "tavar keldi — javonga qo'yish",
      count: unopened.length,
      unit: "qop",
      late: unopened.length > 0 && oldestSack >= SACK_LATE_MINUTES,
    },
    {
      to: "/terish",
      icon: PackageCheck,
      label: "Terish",
      hint: picking.length
        ? `${picking.length > 1 ? "eng eskisi " : ""}${ageBrief(oldestPick)} kutmoqda`
        : "terish uchun buyurtma yo'q",
      count: picking.length,
      unit: "buyurtma",
      late: picking.length > 0 && oldestPick >= PICK_LATE_MINUTES,
    },
    {
      to: "/sanash",
      icon: Layers,
      label: "Sanash",
      hint: "yacheykani qayta sanash",
      count: 0,
      unit: "",
      late: false,
    },
    // Nowhere to go and nothing to say is not a row. The owner reads this
    // screen too and picking is not on their menu; they keep the queue they
    // can act on the length of, and lose the one they cannot.
  ].filter((job) => canReach(role, job.to) || job.count > 0)

  if (!jobs.length) return null

  // The columns are counted rather than fixed at three: a two-row strip in a
  // three-column grid leaves a third of it as a band of the divider colour.
  // One under the other on a phone, where three of these side by side would
  // be three icons and no words.
  return (
    <Panel bare>
      <div
        className="grid gap-px bg-line sm:grid-cols-[repeat(var(--jobs),minmax(0,1fr))]"
        style={{ "--jobs": jobs.length } as React.CSSProperties}
      >
        {jobs.map((job) => (
          <Job key={job.to} {...job} role={role} />
        ))}
      </div>
    </Panel>
  )
}

/**
 * One job, and it is a link only for whoever does it.
 *
 * The owner reads this screen too, and picking and counting are not on their
 * menu — so for them the queue is worth *knowing* and there is nowhere to
 * send them. A row that looks like a link and lands you back where you
 * started is worse than a row that never offered.
 */
function Job({
  to,
  icon: Face,
  label,
  hint,
  count,
  unit,
  late,
  role,
}: {
  to: string
  icon: LucideIcon
  label: string
  hint: string
  count: number
  /** What the figure counts, said once beside it rather than in the hint. */
  unit: string
  late: boolean
  role: Role
}) {
  const open = canReach(role, to)
  // Nothing to say and nowhere to go: an owner does not need a dead row
  // reading "Sanash — yacheykani qayta sanash".
  if (!open && !count) return null

  const inside = (
    <>
      <span
        className={cn(
          "grid size-10 shrink-0 place-items-center rounded-control transition-colors",
          late
            ? "bg-danger-soft text-danger"
            : count
              ? "bg-brand-soft text-brand-deep"
              : "bg-line-soft text-ink-soft group-hover:bg-brand-soft group-hover:text-brand-deep",
        )}
      >
        <Face className="size-5" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-body font-semibold">{label}</span>
        <span className={cn("block truncate text-micro", late ? "text-danger" : "text-ink-faint")}>
          {hint}
        </span>
      </span>

      {count ? (
        <span className="text-right">
          <span
            className={cn(
              "block tabular text-figure font-semibold leading-none",
              late ? "text-danger" : "text-ink",
            )}
          >
            {groups(count)}
          </span>
          <span className="block text-micro text-ink-faint">{unit}</span>
        </span>
      ) : null}
      {open ? (
        <ChevronRight className="size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
      ) : null}
    </>
  )

  if (!open) return <div className="flex items-center gap-3 bg-surface p-3">{inside}</div>
  return (
    <Link
      to={to}
      className="group flex items-center gap-3 bg-surface p-3 transition-colors hover:bg-line-soft">
      {inside}
    </Link>
  )
}

// --------------------------------------------------------------------- racks

function Racks({
  cells,
  retired,
  lit,
  onOpen,
  targeting,
}: {
  cells: Location[]
  /** Cells that are no longer part of the room. Drawn, never counted. */
  retired: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  // Grouped from the data, so a fourth rack is a seed change and not a code
  // change — and so is a rack with five columns.
  //
  // **The retired cells are grouped in here and nowhere else.** A rack takes
  // its shape from the cells it is given — `max(column_no) × max(row_no)` —
  // so a cell retired out of the last column or the top row would quietly
  // shrink the shelf on screen, and the shelf standing in the room would not
  // have moved. The hole has to be drawn for the picture to stay true; it is
  // still a hole, and every figure below is counted from `cells` alone.
  const racks = useMemo(() => {
    const byRack = new Map<string, Location[]>()
    for (const cell of [...cells, ...retired]) {
      const key = cell.rack ?? "?"
      byRack.set(key, [...(byRack.get(key) ?? []), cell])
    }
    return [...byRack.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [cells, retired])

  // What the room itself is doing, on the line that names it. Three figures
  // and no more: how much is on the shelves, how much of the shelving is
  // spoken for, and how many cells are at capacity — which is the one that
  // decides whether the next sack has anywhere to go.
  //
  // A retired cell is not shelving the shop has. It is in none of these.
  const held = cells.reduce((sum, cell) => sum + cell.units, 0)
  const busy = cells.filter((cell) => cell.units > 0).length
  const full = cells.filter((cell) => cell.fill_percent >= 90).length

  if (!racks.length) {
    return (
      <Empty what="Javonlar hali yaratilmagan — yuqoridagi “Javon qo'shish” tugmasi bilan yarating." />
    )
  }

  return (
    <Panel
      title="Javonlar"
      aside={
        targeting ? (
          <span className="text-micro font-medium text-brand-deep">
            Qayerga? Yacheykani bosing
          </span>
        ) : (
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-micro text-ink-soft">
          <span className="tabular">
            <b className="font-semibold text-ink">{groups(held)}</b> dona
          </span>
          <span className="tabular">
            <b className="font-semibold text-ink">
              {busy}/{cells.length}
            </b>{" "}
            katak band
          </span>
          {full ? (
            <span className="tabular text-danger">{full} ta to'lgan</span>
          ) : cells.length ? (
            <span className="tabular">{percent((busy / cells.length) * 100)} to'la</span>
          ) : null}
        </span>
        )
      }
    >
      {/* Racks flow, they are not dealt three to a row.
          `md:grid-cols-3` gave every unit a third of the width whatever it
          was made of, so a cell in a five-column rack was drawn smaller than
          a cell in a four-column one and a fourth unit dropped onto a row of
          its own with two thirds of the panel empty beside it. A cell is a
          real box of a real size; every one of them is now the same size on
          screen, each rack is exactly as wide as it has columns, and the row
          breaks where the units stop fitting — which is what a plan of a room
          looks like. */}
      <div className="flex flex-wrap items-start gap-x-7 gap-y-6">
        {racks.map(([rack, own]) => (
          <Rack
            key={rack}
            rack={rack}
            cells={own}
            lit={lit}
            onOpen={onOpen}
            targeting={targeting}
          />
        ))}
      </div>
      <Legend targeting={targeting} anyRetired={retired.length > 0} />
    </Panel>
  )
}

/**
 * What the colours under the cells mean.
 *
 * The fill bar was carrying green, amber and red with nothing on the screen
 * saying so — colour that has to be learnt by watching it change is colour
 * that is read wrong on the day it matters.
 */
function Legend({
  targeting,
  anyRetired,
}: {
  targeting: Targeting | null
  /** Only drawn when there is a struck-through tile on screen to explain —
   *  a legend entry for a state the room is not in is a line to read past. */
  anyRetired: boolean
}) {
  // In a move the bars are not drawn and the colours mean something else:
  // what is on the cells is room and whether the model is already there.
  if (targeting) {
    return (
      <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-2 text-micro text-ink-faint">
        <span className="flex items-center gap-1.5">
          <span className="tabular font-semibold text-good">+12</span>
          joy bor
        </span>
        <span className="flex items-center gap-1.5">
          <span className="tabular font-semibold text-danger">0</span>
          joy yo'q — baribir tanlash mumkin
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-brand" />
          shu model shu yerda
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-4 rounded-xs border border-brand bg-brand-soft" />
          shu yerdan
        </span>
      </p>
    )
  }
  return (
    <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-2 text-micro text-ink-faint">
      <span className="flex items-center gap-1.5">
        <span className="h-1 w-4 rounded-full bg-good" />
        joy bor
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-1 w-4 rounded-full bg-warn" />
        to'lib qolyapti
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-1 w-4 rounded-full bg-danger" />
        to'lgan
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-3 w-4 rounded-xs border border-dashed border-line" />
        bo'sh katak
      </span>
      {anyRetired ? (
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-4 rounded-xs border border-dashed border-line bg-line-soft" />
          <span className="line-through">olib tashlangan</span>
        </span>
      ) : null}
    </p>
  )
}

function Rack({
  rack,
  cells,
  lit,
  onOpen,
  targeting,
}: {
  rack: string
  cells: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  const columns = Math.max(...cells.map((cell) => cell.column_no ?? 1))
  const rows = Math.max(...cells.map((cell) => cell.row_no ?? 1))
  const at = (column: number, row: number) =>
    cells.find((cell) => cell.column_no === column && cell.row_no === row)

  return (
    <section className="max-w-full overflow-x-auto">
      <h3 className="mb-1.5 text-micro font-semibold uppercase tracking-wide text-ink-soft">
        {rack} javoni
      </h3>

      {/* A fixed cell width rather than a share of whatever room is going.
          Two cells the same size are two boxes the same size; two cells drawn
          at different widths on one screen say something about the shelves
          that is not true. A rack wider than the panel scrolls on its own
          rather than squeezing — a squeezed rack is unreadable and a scrolled
          one is merely further along. */}
      <div
        className="grid w-max gap-1"
        style={{ gridTemplateColumns: `1.25rem repeat(${columns}, 4.75rem)` }}
      >
        {/* Rows top to bottom on screen, counted bottom-up on the shelf: row 1
            is where a person's eye starts and where the heavy things go. */}
        {Array.from({ length: rows }, (_, index) => rows - index).map((row) => (
          <RowOfCells
            key={row}
            row={row}
            columns={columns}
            at={at}
            lit={lit}
            onOpen={onOpen}
            targeting={targeting}
          />
        ))}

        <span />
        {Array.from({ length: columns }, (_, index) => index + 1).map((column) => (
          <span key={column} className="pt-1 text-center text-micro text-ink-faint">
            {column}
          </span>
        ))}
      </div>

      {/* Where somebody standing in front of this shelf would look for it:
          on the shelf, not in the page's header. */}
      <AddCells rack={rack} columns={columns} rows={rows} />
    </section>
  )
}

function RowOfCells({
  row,
  columns,
  at,
  lit,
  onOpen,
  targeting,
}: {
  row: number
  columns: number
  at: (column: number, row: number) => Location | undefined
  lit: Set<string> | null
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  return (
    <>
      <span className="grid place-items-center text-micro text-ink-faint">{row}</span>
      {Array.from({ length: columns }, (_, index) => index + 1).map((column) => {
        const cell = at(column, row)
        if (!cell) return <span key={column} />
        return (
          <Cell key={column} cell={cell} lit={lit} onOpen={onOpen} targeting={targeting} />
        )
      })}
    </>
  )
}

/**
 * How much more this cell is meant to take, in the three states it has.
 *
 * `free` of `null` is a cell nobody ever measured, and that is not the same
 * as a roomy one — it is drawn quietly and says what it is. Nought is a full
 * cell, which is still a choosable place: capacity in this building is a
 * statement, not a lock.
 */
function room(cell: Location): { figure: string; word: string; tone: string } {
  if (cell.free === null) return { figure: "?", word: "sig'im yo'q", tone: "text-ink-faint" }
  if (cell.free <= 0) return { figure: "0", word: "joy yo'q", tone: "text-danger" }
  // An empty cell is already drawn as empty and says so underneath; green on
  // every one of them is forty identical green figures and no signal. The
  // colour is kept for the cells that are holding something and still have
  // room, which is where the figure is actually a decision.
  return {
    figure: `+${groups(cell.free)}`,
    word: "joy",
    tone: cell.units ? "text-good" : "text-ink-soft",
  }
}

function Cell({
  cell,
  lit,
  onOpen,
  targeting,
}: {
  cell: Location
  lit: Set<string> | null
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  const highlighted = lit?.has(cell.code) ?? false
  const dimmed = lit !== null && !highlighted
  const empty = cell.units === 0

  // A cell that is no longer part of the room. Drawn in the place it used to
  // occupy so the rack keeps its real shape, struck through so it is not
  // mistaken for a shelf with nothing on it, and never a destination.
  if (!cell.is_active) {
    return <RetiredCell cell={cell} onOpen={onOpen} targeting={targeting} />
  }

  // --------------------------------------------------- the cell as a target
  if (targeting) {
    const source = targeting.from === cell.code
    const has = targeting.holds.has(cell.code)
    const space = room(cell)

    return (
      <button
        type="button"
        disabled={source || targeting.pending}
        onClick={() => targeting.onPick(cell.code)}
        title={
          source
            ? `${cell.code} — shu yerdan`
            : `${cell.code} · ${units(cell.units)}${cell.free === null ? "" : ` · ${cell.free} joy`}`
        }
        className={cn(
          "flex min-h-16 flex-col justify-between rounded-control border p-1.5 text-left transition",
          source
            ? "cursor-default border-brand bg-brand-soft"
            : "border-brand/30 hover:border-brand hover:bg-brand-soft hover:ring-2 hover:ring-brand/25",
          !source && empty && "border-dashed",
          !source && targeting.pending && "opacity-50",
        )}
      >
        <span className="flex items-center justify-between gap-1">
          <span className="whitespace-nowrap text-micro tabular leading-none text-ink-faint">
            {cell.code}
          </span>
          {has && !source ? (
            <span className="size-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
          ) : null}
        </span>

        {source ? (
          <span className="text-micro font-medium leading-tight text-brand-deep">
            shu yerdan
          </span>
        ) : (
          <>
            <span className={cn("truncate leading-none", space.tone)}>
              <b className="tabular text-small font-semibold">{space.figure}</b>{" "}
              <span className="text-micro">{space.word}</span>
            </span>
            <span className="truncate text-micro leading-none">
              {has ? (
                <span className="font-medium text-brand-deep">shu model</span>
              ) : (
                <span className="text-ink-faint">
                  {empty ? "bo'sh" : `${groups(cell.units)} dona`}
                </span>
              )}
            </span>
          </>
        )}
      </button>
    )
  }

  // An empty cell is not a cell with nothing in it — it is *space*, which is
  // what somebody carrying a sack is looking for. It was drawn as a full cell
  // holding an em-dash, with a grey fill bar under it that read as a bar at
  // nought rather than as an empty track, so forty-two empty cells looked
  // exactly as busy as the six with goods in them. Dashed and quiet now, and
  // no bar at all: the ink on this grid belongs to the goods.
  return (
    <button
      type="button"
      onClick={() => onOpen(cell.code)}
      title={`${cell.code} · ${units(cell.units)}`}
      className={cn(
        "flex min-h-16 flex-col justify-between rounded-control border p-1.5 text-left transition",
        "hover:border-brand hover:bg-brand-soft",
        empty ? "border-dashed border-line bg-canvas" : "border-line bg-surface",
        highlighted && "border-brand ring-2 ring-brand",
        dimmed && "opacity-25",
      )}
    >
      <span
        className={cn(
          "whitespace-nowrap text-micro tabular leading-none",
          empty ? "text-ink-faint/70" : "text-ink-faint",
        )}
      >
        {cell.code}
      </span>

      {empty ? null : (
        <>
          {/* A cell past its stated capacity says *how far* past, beside the
              count itself. The bar stops at full whatever happens, so without
              the figure a cell holding 68 of a stated 60 is drawn exactly
              like one holding 60 — and the difference between them is a pile
              somebody has to carry somewhere else. */}
          <span className="flex items-baseline justify-between gap-1">
            <span className="tabular text-small font-semibold leading-none">
              {groups(cell.units)}
            </span>
            {cell.fill_percent > 100 ? (
              <span className="tabular text-micro font-medium leading-none text-danger">
                {percent(cell.fill_percent)}
              </span>
            ) : null}
          </span>
          <span className="truncate text-micro text-ink-faint">
            {cell.products ? `${cell.products} xil` : " "}
          </span>
          <Fill percent={cell.fill_percent} />
        </>
      )}
    </button>
  )
}

/**
 * The hole where a cell used to be, with the way back on it.
 *
 * Not a gap. A rack that was built 6×4 by mistake and had two columns taken
 * out of it is a different thing from a rack that was only ever 4×4, and the
 * difference matters the moment somebody asks why A stops at four: one of
 * them can be undone from here and the other cannot. So the tile stays in the
 * grid in the position it owns — which is also what keeps the rack its real
 * size — and says what happened to it.
 *
 * In a move it is inert. The pile door refuses a retired destination, and a
 * tile that takes a click and then explains a refusal is a tile that lied.
 */
function RetiredCell({
  cell,
  onOpen,
  targeting,
}: {
  cell: Location
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  const { staff } = useSession()
  const skin =
    "flex min-h-16 flex-col justify-between rounded-control border border-dashed border-line bg-line-soft p-1.5 text-left"

  if (targeting) {
    return (
      <div
        className={cn(skin, "opacity-40")}
        title={`${cell.code} — olib tashlangan, bu yerga qo'yib bo'lmaydi`}
      >
        <span className="whitespace-nowrap text-micro tabular leading-none text-ink-faint line-through">
          {cell.code}
        </span>
        <span className="truncate text-micro leading-none text-ink-faint">olingan</span>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onOpen(cell.code)}
      title={`${cell.code} — olib tashlangan${
        staff?.role === "admin" ? " · qaytarish uchun bosing" : ""
      }`}
      className={cn(
        skin,
        // Quieter than a live cell and quieter than an empty one: a hole in
        // the shelving is not news every morning. The way back is legible on
        // it and only picks up the accent under the cursor — forty struck
        // tiles each printing a blue word would be the loudest thing in the
        // room, and the goods are what the ink on this grid belongs to.
        "group opacity-60 transition hover:border-brand hover:bg-brand-soft hover:opacity-100",
      )}
    >
      <span className="whitespace-nowrap text-micro tabular leading-none text-ink-faint line-through">
        {cell.code}
      </span>
      <span className="truncate text-micro leading-none text-ink-faint">
        {staff?.role === "admin" ? (
          <span className="group-hover:font-medium group-hover:text-brand-deep">
            qaytarish
          </span>
        ) : (
          "olingan"
        )}
      </span>
    </button>
  )
}

// ------------------------------------------------------------------- staging

/**
 * The states goods pass through, which are not shelves.
 *
 * Six tiles the size of a problem, four of them reading nought, was the whole
 * top of this screen: `QABUL 0 bo'sh`, `YIGIM 0 bo'sh`, and a picker scrolled
 * past all of it every morning to reach the room. A staging area with nothing
 * in it is good news and one word long.
 *
 * So the ones holding goods are cards, and the empty ones are a line of chips
 * underneath — still tappable, because "is there anything in BRAK" is worth
 * being able to check and is not worth a card.
 */
function Staging({
  tiles,
  lit,
  onOpen,
  targeting,
}: {
  tiles: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
  targeting: Targeting | null
}) {
  const holding = tiles.filter((tile) => tile.units > 0)
  const empty = tiles.filter((tile) => tile.units === 0)
  if (!tiles.length) return null

  // A staging area is a place like any other while something is in the hand:
  // goods go back to QABUL, or to BRAK, and refusing that here would only
  // send somebody to type the code somewhere else.
  const pick = (code: string) => {
    if (!targeting || targeting.pending || targeting.from === code) return
    targeting.onPick(code)
  }

  return (
    <div className="space-y-2">
      {holding.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {holding.map((tile) => {
            const shouting =
              tile.kind === "receiving" && tile.oldest_minutes >= SHOUT_AFTER_MINUTES
            const highlighted = lit?.has(tile.code) ?? false
            return (
              <button
                key={tile.code}
                type="button"
                disabled={targeting ? targeting.from === tile.code || targeting.pending : false}
                onClick={() => (targeting ? pick(tile.code) : onOpen(tile.code))}
                className={cn(
                  "flex items-center gap-3 rounded-panel border bg-surface p-4 text-left transition hover:border-brand",
                  shouting ? "border-danger/40" : "border-panel-edge",
                  highlighted && "border-brand ring-2 ring-brand",
                  lit !== null && !highlighted && "opacity-25",
                  targeting && targeting.from === tile.code
                    ? "cursor-default border-brand bg-brand-soft"
                    : targeting && "border-brand/30 hover:ring-2 hover:ring-brand/25",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-micro font-medium uppercase tracking-wide text-ink-soft">
                    {tile.code}
                  </span>
                  <span
                    className={cn(
                      "block text-micro",
                      targeting && targeting.from === tile.code
                        ? "font-medium text-brand-deep"
                        : shouting
                          ? "font-medium text-danger"
                          : "text-ink-faint",
                    )}
                  >
                    {targeting
                      ? targeting.from === tile.code
                        ? "shu yerdan"
                        : "shu yerga"
                      : `${age(tile.oldest_minutes)} turgan`}
                  </span>
                </span>
                <span
                  className={cn("tabular text-figure font-semibold", shouting && "text-danger")}
                >
                  {groups(tile.units)}
                </span>
              </button>
            )
          })}
        </div>
      ) : null}

      {empty.length ? (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="caption">Bo'sh</span>
          {empty.map((tile) => {
            const highlighted = lit?.has(tile.code) ?? false
            return (
              <button
                key={tile.code}
                type="button"
                disabled={targeting ? targeting.from === tile.code || targeting.pending : false}
                onClick={() => (targeting ? pick(tile.code) : onOpen(tile.code))}
                className={cn(
                  "rounded-full border border-line px-2 py-0.5 text-micro text-ink-soft transition-colors hover:border-brand hover:text-ink",
                  highlighted && "border-brand text-ink",
                  lit !== null && !highlighted && "opacity-40",
                  targeting && targeting.from === tile.code
                    ? "cursor-default border-brand bg-brand-soft text-brand-deep"
                    : targeting && "border-brand/40",
                )}
              >
                {tile.code.toLowerCase()}
              </button>
            )
          })}
        </p>
      ) : null}
    </div>
  )
}

// -------------------------------------------------------------------- dialog

/**
 * What is standing in one place, and the start of moving it somewhere else.
 *
 * **It opens in the middle**, which is the one place this application does
 * not follow its own rule that a record read beside its list opens at the
 * side. The map is not a list. It is a picture of a room; a cell is a thing
 * you act on rather than a row you read your way down; and the picture is now
 * the destination picker for a move — a panel down the right-hand edge covers
 * the half of the room somebody is about to point at. It was also, until
 * this, the one overlay in the application that was neither of the two
 * components: a hand-rolled `fixed inset-0` with no focus trap, no `Esc` and
 * a backdrop of its own shade.
 *
 * The dialog is where a move begins and deliberately not where one ends: the
 * destination is a place in the room, so this gets out of the way and the map
 * itself answers. One button carries the ordinary case — the whole cell, in
 * one request — and the tick boxes narrow it to some of the lines without
 * turning the ordinary case into four separate moves.
 */
function CellDialog({
  code,
  onClose,
  onMove,
}: {
  code: string | null
  onClose: () => void
  onMove: (moving: Moving) => void
}) {
  const place = useLocation(code)
  const [chosen, setChosen] = useState<number[]>([])
  // Bolting a cell back into the room. Unconditional on the server's side —
  // nothing can have gone wrong with it while it was empty and closed.
  const back = useSetCellActive()

  // A different cell is a different question; a tick left over from the last
  // one would move the wrong goods, and a refusal left over from the last one
  // would be read as this cell's.
  useEffect(() => {
    setChosen([])
    back.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code])

  const contents = place.data?.contents ?? []
  const picked = contents.filter((line) => chosen.includes(line.variant_id))
  const going = picked.length ? picked : contents
  const some = picked.length > 0
  const retired = Boolean(place.data) && !place.data!.is_active

  return (
    <Dialog open={Boolean(code)} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="tabular">{code ?? ""}</DialogTitle>
          {/* Where to walk, rather than a figure the body repeats underneath:
              the code is on the shelf and the rack letter is on its end. */}
          <DialogDescription>
            {retired
              ? "Xonadan olib tashlangan — bu yerga hech narsa qo'yib bo'lmaydi"
              : place.data
                ? whereItIs(place.data)
                : "Yacheyka tarkibi"}
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-4">
          {place.isLoading ? <Waiting /> : null}
          <Problem error={place.error} />
          <Problem error={back.error} />

          {place.data ? (
            <>
              <dl className="grid grid-cols-3 gap-2 text-micro">
                <Figure label="Dona" value={groups(place.data.units)} />
                <Figure label="Xil" value={groups(place.data.products)} />
                <Figure
                  label="Sig'im"
                  value={place.data.capacity ? groups(place.data.capacity) : "—"}
                  hint={fullness(place.data)}
                />
              </dl>

              {contents.length === 0 ? (
                <Empty bare what={retired ? "Bu joy bo'sh — shuning uchun uni olib tashlash mumkin bo'lgan." : "Bu joy bo'sh."} />
              ) : (
                <ul className="divide-y divide-line">
                  {contents.map((line) => {
                    const on = chosen.includes(line.variant_id)
                    return (
                      <li key={line.variant_id} className="flex items-start gap-2 py-2">
                        <button
                          type="button"
                          role="checkbox"
                          aria-checked={on}
                          aria-label={`${line.variant_label} — tanlash`}
                          onClick={() =>
                            setChosen((was) =>
                              on
                                ? was.filter((id) => id !== line.variant_id)
                                : [...was, line.variant_id],
                            )
                          }
                          className={cn(
                            "mt-0.5 grid size-5 shrink-0 place-items-center rounded-control border transition-colors",
                            on
                              ? "border-brand bg-brand text-brand-ink"
                              : "border-line text-transparent hover:border-brand",
                          )}
                        >
                          <Check className="size-3.5" />
                        </button>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="truncate text-small font-medium">
                              {line.product_title}
                            </span>
                            <span className="tabular text-small font-semibold">
                              {groups(line.qty)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between gap-2 text-micro text-ink-soft">
                            <span>{line.variant_label}</span>
                            <span className="tabular">{line.barcode}</span>
                          </div>
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-micro text-ink-faint">
                              {age(line.minutes_here)} shu yerda
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                onMove({
                                  kind: "line",
                                  from: place.data!.code,
                                  line,
                                  qty: line.qty,
                                })
                              }
                              className="text-micro text-brand-deep underline"
                            >
                              ko'chirish
                            </button>
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}

              {/* The two acts that take something away rather than carry it
                  somewhere. Quiet, at the bottom, each one two steps. */}
              {retired ? null : (
                <div className="space-y-2 border-t border-line pt-3">
                  {contents.length ? (
                    <EmptyCell code={place.data.code} onDone={onClose} />
                  ) : null}
                  <RetireCell place={place.data} onDone={onClose} />
                </div>
              )}
            </>
          ) : null}
        </DialogBody>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="secondary">Yopish</Button>
          </DialogClose>

          {retired ? (
            <RestoreButton
              pending={back.isPending}
              onRestore={() =>
                back.mutate(
                  { code: place.data!.code, active: true, note: "xaritaga qaytarildi" },
                  { onSuccess: onClose },
                )
              }
            />
          ) : contents.length ? (
            /* The one act this dialog exists for. Everything standing here in
               one request — or the ticked lines, which is the same request
               with the list narrowed. */
            <Button
              className="gap-1"
              onClick={() =>
                onMove({
                  kind: "cell",
                  from: place.data!.code,
                  lines: going,
                  variant_ids: some ? going.map((line) => line.variant_id) : [],
                  units: going.reduce((sum, line) => sum + line.qty, 0),
                })
              }
            >
              <ArrowRight className="size-4" />
              {some ? `${picked.length} xilni ko'chirish` : "Hammasini ko'chirish"}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** The way back, and only for whoever can take it. */
function RestoreButton({
  pending,
  onRestore,
}: {
  pending: boolean
  onRestore: () => void
}) {
  const { staff } = useSession()
  if (staff?.role !== "admin") return null
  return (
    <Button className="gap-1" disabled={pending} onClick={onRestore}>
      {pending ? <Loader2 className="size-4 animate-spin" /> : <RotateCcw className="size-4" />}
      Qaytarish
    </Button>
  )
}

/**
 * Take this cell out of the room, and put it back on the same door.
 *
 * A rack extended to 6×4 by mistake carried two dead columns for ever: cells
 * were built and never removed, and the shape of the building was the one
 * thing on this screen nobody could correct. It is **not** a delete — the row
 * keeps its code, its capacity and every movement that ever named it, so a
 * stocktake from March still points at a cell that still exists. What changes
 * is that the room stops offering it, and that nothing may be put into it.
 *
 * **The button is dead while the cell is holding anything, and says why.** The
 * server refuses it — goods in a place nobody can see are goods nobody can
 * find — and a disabled control with no sentence beside it is a control
 * somebody clicks four times and then writes a message about. The sentence
 * names the two ways out, which are the two things the refusal is actually
 * asking for.
 *
 * The office's, like building a rack and like emptying the room: a rack is
 * the shape of the building. `QABUL`, `YIGIM`, `BRAK` and `QAYTGAN` are not
 * shelves but places with a job, so there is no such decision to take and no
 * control drawn for it.
 *
 * The reason is typed rather than picked, and goes into the audit trail: three
 * months later it is the only thing that tells a shelf that was dismantled
 * from a column somebody typed by accident.
 */
function RetireCell({ place, onDone }: { place: LocationDetail; onDone: () => void }) {
  const { staff } = useSession()
  const set = useSetCellActive()
  const [asked, setAsked] = useState(false)
  const [reason, setReason] = useState("")

  if (staff?.role !== "admin") return null
  if (place.kind !== "bin") return null

  const holding = place.units > 0

  if (!asked) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button
          type="button"
          disabled={holding}
          onClick={() => setAsked(true)}
          className={cn(
            "text-micro",
            holding ? "cursor-not-allowed text-ink-faint" : "text-danger underline",
          )}
        >
          Yacheykani olib tashlash
        </button>
        {holding ? (
          <span className="text-micro text-ink-soft">
            Ichida {units(place.units)} bor — avval boshqa yacheykaga ko'chiring
            yoki hisobdan chiqaring
          </span>
        ) : null}
      </div>
    )
  }

  return (
    <form
      className="space-y-2 rounded-control border border-danger bg-danger-soft p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (reason.trim().length < 3) return
        set.mutate(
          { code: place.code, active: false, note: reason.trim() },
          { onSuccess: onDone },
        )
      }}
    >
      <p className="text-micro text-danger">
        {place.code} xaritadan chiqadi va unga hech narsa qo'yib bo'lmaydi.
        Kodi va tarixi qoladi, keyin qaytarish mumkin. Nega?
      </p>
      <Input
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="javon buzildi"
        aria-label="Sabab"
        className="h-control" />
      <div className="flex gap-2">
        <Button
          type="submit"
          size="sm"
          className="bg-danger text-danger-ink hover:bg-danger"
          disabled={reason.trim().length < 3 || set.isPending}
        >
          {set.isPending ? <Loader2 className="size-4 animate-spin" /> : "Olib tashlash"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setAsked(false)}>
          Bekor
        </Button>
      </div>
      <Problem error={set.error} />
    </form>
  )
}

/**
 * Where in the room this place is, in the words written on the shelf itself.
 *
 * A staging area has no shelf and no coordinates — it is a state goods pass
 * through — so it says what it is instead.
 */
function whereItIs(place: Location): string {
  if (place.kind !== "bin" || !place.rack) return "Ish joyi — javon emas"
  return `${place.rack} javoni · ${place.column_no}-ustun, ${place.row_no}-qator`
}

/**
 * How full this place is, in a sentence under the capacity.
 *
 * `free` is the honest one of the three figures: `null` is a place nobody
 * measured, nought is full, and a negative is a cell holding more than it was
 * ever meant to — which the office wants as a count of pieces to carry away,
 * not as a percentage to interpret.
 */
function fullness(place: Location): string {
  if (place.free === null || !place.capacity) return "o'lchanmagan"
  if (place.units > place.capacity) {
    return `${groups(place.units - place.capacity)} dona ortiqcha`
  }
  if (place.free > 0) return `${groups(place.free)} joy bor`
  return "to'la"
}

/**
 * Clear the whole room, which is the office's to decide and nobody else's.
 *
 * For a shop starting again — a stocktake that found nothing where the books
 * said something, or a test catalogue being thrown away before the real one
 * goes in. The bench moves goods; it does not decide they stopped existing, so
 * the server refuses this to anybody but an admin and the button is not drawn
 * for them either.
 *
 * The confirmation is the word itself, typed. A cell asks for a reason and
 * that is enough; the whole room is the kind of thing somebody should have to
 * mean, and "OK" in a dialog is not meaning it.
 */
/**
 * Build a shelf unit, from the screen that draws them.
 *
 * A rack is a grid and is asked for as one: columns across and rows up, which
 * is what makes ``D-03-02`` a code somebody can walk to. A count of cells with
 * no shape to it could not be written on a label. The total is shown as it is
 * typed, because "6 × 4" is how the shelf is built and "24" is what the owner
 * is actually deciding about.
 *
 * The office's, like emptying the room: a rack is the shape of the building.
 * Closed until asked for, because most visits to this screen are to find a pair
 * of shoes.
 */
function AddRack() {
  const { staff } = useSession()
  const add = useAddRack()
  const [open, setOpen] = useState(false)
  const [rack, setRack] = useState("")
  const [columns, setColumns] = useState("4")
  const [rows, setRows] = useState("4")
  const [done, setDone] = useState<string | null>(null)

  if (staff?.role !== "admin") return null

  const across = Number(columns) || 0
  const up = Number(rows) || 0
  const cells = across * up
  const ready = rack.trim().length > 0 && across > 0 && up > 0

  if (!open) {
    return (
      <div className="flex items-center gap-2">
        {/* What was built, in the server's own words and until the next one.
            A rack appears in the grid below either way, but twenty-four new
            cells all of them empty is a change somebody wants confirmed. */}
        {done ? <span className="text-micro text-good">{done}</span> : null}
        <Button
          variant="ghost"
          size="sm"
          className="gap-1"
          onClick={() => {
            setDone(null)
            setOpen(true)
          }}
        >
          <Grid3x3 className="size-4" />
          Javon qo'shish
        </Button>
      </div>
    )
  }

  return (
    <form
      className="flex flex-wrap items-end gap-2 rounded-control border border-line bg-surface p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (!ready) return
        add.mutate(
          { rack: rack.trim().toUpperCase(), columns: across, rows: up },
          {
            onSuccess: (made) => {
              setOpen(false)
              setRack("")
              setDone(made.message)
            },
          },
        )
      }}
    >
      <label>
        <span className="mb-1 block text-micro text-ink-soft">Javon</span>
        <Input
          autoFocus
          value={rack}
          onChange={(event) =>
            // The letter goes on every label in the building, so it is kept to
            // what a label can carry and shown as it will be stored.
            setRack(event.target.value.replace(/[^A-Za-z0-9]/g, "").slice(0, 4).toUpperCase())
          }
          placeholder="D"
          aria-label="Javon harfi"
          className="h-control w-16 tabular" />
      </label>
      <label>
        <span className="mb-1 block text-micro text-ink-soft">Ustun</span>
        <Input
          value={columns}
          onChange={(event) => setColumns(event.target.value.replace(/\D/g, "").slice(0, 2))}
          inputMode="numeric"
          aria-label="Ustunlar soni"
          className="h-control w-16 tabular" />
      </label>
      <label>
        <span className="mb-1 block text-micro text-ink-soft">Qator</span>
        <Input
          value={rows}
          onChange={(event) => setRows(event.target.value.replace(/\D/g, "").slice(0, 2))}
          inputMode="numeric"
          aria-label="Qatorlar soni"
          className="h-control w-16 tabular" />
      </label>

      <span className="pb-2 text-micro text-ink-soft">
        {cells > 0 ? (
          <>
            <b className="tabular font-semibold text-ink">{cells}</b> ta yacheyka
            {rack ? (
              <>
                {" · "}
                <span className="tabular">
                  {rack}-01-01 … {rack}-{String(across).padStart(2, "0")}-
                  {String(up).padStart(2, "0")}
                </span>
              </>
            ) : null}
          </>
        ) : (
          "Ustun × qator"
        )}
      </span>

      <Button type="submit" size="sm" disabled={!ready || add.isPending}>
        {add.isPending ? <Loader2 className="size-4 animate-spin" /> : "Yaratish"}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Bekor
      </Button>
      {add.error ? (
        <div className="w-full">
          <Problem error={add.error} />
        </div>
      ) : null}
    </form>
  )
}

function EmptyRoom() {
  const { staff } = useSession()
  const empty = useEmptyStock()
  const [open, setOpen] = useState(false)
  const [word, setWord] = useState("")
  const [done, setDone] = useState<string | null>(null)

  if (staff?.role !== "admin") return null

  if (done) {
    return <span className="text-micro text-good">{done}</span>
  }

  if (!open) {
    return (
      <Button variant="ghost" size="sm" className="text-danger" onClick={() => setOpen(true)}
      >
        Omborni bo'shatish
      </Button>
    )
  }

  return (
    <form
      className="flex items-center gap-2 rounded-control border border-danger bg-danger-soft p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (word.trim().toUpperCase() !== "BO'SHATISH") return
        empty.mutate(
          { reason: "ombor to'liq bo'shatildi" },
          {
            onSuccess: (out) => {
              setOpen(false)
              setWord("")
              setDone(`${out.cells} yacheyka · ${out.units} dona hisobdan chiqdi`)
            },
          },
        )
      }}
    >
      <span className="text-micro text-danger">
        Hamma yacheyka hisobdan chiqadi. Tasdiqlash uchun <b>BO'SHATISH</b> deb
        yozing:
      </span>
      <Input
        autoFocus
        value={word}
        onChange={(event) => setWord(event.target.value)}
        aria-label="Tasdiqlash so'zi"
        className="h-control w-36" />
      <Button type="submit" size="sm" className="bg-danger text-danger-ink hover:bg-danger" disabled={word.trim().toUpperCase() !=="BO'SHATISH" || empty.isPending} >
        {empty.isPending ? <Loader2 className="size-4 animate-spin" /> : "Bo'shatish"}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
        Bekor
      </Button>
    </form>
  )
}

/**
 * Take everything off this cell, and off the books.
 *
 * Not a move: a move needs somewhere to move to, and this is for a cell whose
 * contents turned out not to exist — a miscount, goods thrown away, a room
 * being cleared to start again. Every line leaves the building the way any
 * other line does, so the ledger still explains the shelf afterwards.
 *
 * The reason is required, and typed rather than picked: three months later it
 * is the only thing that tells a stocktake from a mistake somebody made in a
 * hurry. Two steps, because one tap beside a full cell is a mistake nobody
 * notices until the count is gone.
 */
function EmptyCell({ code, onDone }: { code: string; onDone: () => void }) {
  const empty = useEmptyStock()
  const [asked, setAsked] = useState(false)
  const [reason, setReason] = useState("")

  if (!asked) {
    return (
      <button
        type="button"
        onClick={() => setAsked(true)}
        className="text-micro text-danger underline">
        Yacheykani bo'shatish
      </button>
    )
  }

  return (
    <form
      className="space-y-2 rounded-control border border-danger bg-danger-soft p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (reason.trim().length < 3) return
        empty.mutate({ code, reason: reason.trim() }, { onSuccess: onDone })
      }}
    >
      <p className="text-micro text-danger">
        {code} dagi hamma narsa hisobdan chiqadi. Nega?
      </p>
      <Input
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="sanoqda topilmadi"
        aria-label="Sabab"
        className="h-control" />
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="bg-danger text-danger-ink hover:bg-danger" disabled={reason.trim().length < 3 || empty.isPending} >
          {empty.isPending ? <Loader2 className="size-4 animate-spin" /> : "Bo'shatish"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setAsked(false)}>
          Bekor
        </Button>
      </div>
      <Problem error={empty.error} />
    </form>
  )
}

/**
 * Bolt cells onto a rack that is already standing, from the rack itself.
 *
 * A shelf unit grows the way buildings grow: somebody adds a plank and the
 * shelf is five columns now. Rebuilding it as a new rack would give the goods
 * a new letter and every label in the aisle would be wrong, so this asks for
 * the shape the rack **has** — "A is five by four now" — which is a sentence
 * somebody can say standing in front of it without knowing what the system
 * thought A was. Nothing is ever removed; a smaller shape adds nothing and
 * says so in the server's own words.
 *
 * The two that actually happen — one more column, one more row — are single
 * buttons, because counting the columns of a shelf you are standing in front
 * of is a step that only exists because a form asked for it.
 *
 * The office's, like building a rack and like emptying the room: a rack is
 * the shape of the building.
 */
function AddCells({
  rack,
  columns,
  rows,
}: {
  rack: string
  columns: number
  rows: number
}) {
  const { staff } = useSession()
  const extend = useExtendRack(rack)
  const [open, setOpen] = useState(false)
  const [across, setAcross] = useState("")
  const [up, setUp] = useState("")
  const [done, setDone] = useState<{ message: string; cells: number } | null>(null)

  if (staff?.role !== "admin") return null

  const wantAcross = Number(across) || 0
  const wantUp = Number(up) || 0
  // Nothing is removed, so what is added is the new grid less the part of it
  // the rack already covers.
  const gained =
    wantAcross > 0 && wantUp > 0
      ? wantAcross * wantUp - Math.min(wantAcross, columns) * Math.min(wantUp, rows)
      : 0

  function grow(nextAcross: number, nextUp: number) {
    setDone(null)
    extend.mutate(
      { columns: nextAcross, rows: nextUp },
      {
        onSuccess: (made) => {
          setOpen(false)
          setAcross("")
          setUp("")
          setDone({ message: made.message, cells: made.cells })
        },
      },
    )
  }

  if (!open) {
    return (
      <div className="no-print mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <button
          type="button"
          onClick={() => {
            setDone(null)
            setAcross(String(columns))
            setUp(String(rows))
            setOpen(true)
          }}
          className="flex items-center gap-1 text-micro text-brand-deep underline"
        >
          <Plus className="size-3.5" />
          Katak qo'shish
        </button>
        {done ? (
          <span className={cn("text-micro", done.cells ? "text-good" : "text-ink-soft")}>
            {done.message}
          </span>
        ) : null}
      </div>
    )
  }

  return (
    <form
      className="no-print mt-2 max-w-[19rem] space-y-2 rounded-control border border-line bg-surface p-2"
      onSubmit={(event) => {
        event.preventDefault()
        if (wantAcross < 1 || wantUp < 1) return
        grow(wantAcross, wantUp)
      }}
    >
      <p className="text-micro text-ink-soft">
        Hozir{" "}
        <b className="tabular font-semibold text-ink">
          {columns} × {rows}
        </b>{" "}
        · {columns * rows} katak
      </p>

      {/* The two cases that actually happen, each one click. */}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-1"
          disabled={extend.isPending}
          onClick={() => grow(columns + 1, rows)}
        >
          <Plus className="size-3.5" />
          ustun
        </Button>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-1"
          disabled={extend.isPending}
          onClick={() => grow(columns, rows + 1)}
        >
          <Plus className="size-3.5" />
          qator
        </Button>
        {extend.isPending ? <Loader2 className="size-4 animate-spin text-brand" /> : null}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Ustun</span>
          <Input
            value={across}
            onChange={(event) => setAcross(event.target.value.replace(/\D/g, "").slice(0, 2))}
            inputMode="numeric"
            aria-label={`${rack} javonining ustunlari`}
            className="h-control w-14 tabular" />
        </label>
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Qator</span>
          <Input
            value={up}
            onChange={(event) => setUp(event.target.value.replace(/\D/g, "").slice(0, 2))}
            inputMode="numeric"
            aria-label={`${rack} javonining qatorlari`}
            className="h-control w-14 tabular" />
        </label>
        <Button type="submit" size="sm" disabled={extend.isPending || wantAcross < 1 || wantUp < 1}>
          {extend.isPending ? <Loader2 className="size-4 animate-spin" /> : "Qo'shish"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
          Bekor
        </Button>
      </div>

      <p className="text-micro text-ink-soft">
        {wantAcross > 0 && wantUp > 0 ? (
          gained > 0 ? (
            <>
              {rack} endi{" "}
              <b className="tabular font-semibold text-ink">
                {Math.max(wantAcross, columns)} × {Math.max(wantUp, rows)}
              </b>{" "}
              · <b className="tabular font-semibold text-ink">{gained}</b> ta yangi katak
            </>
          ) : (
            "Bu shakl yangi katak qo'shmaydi — katak hech qachon o'chmaydi"
          )
        ) : (
          "Javonning butun shakli: ustun × qator"
        )}
      </p>

      <Problem error={extend.error} />
    </form>
  )
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-control bg-canvas p-2">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="tabular text-body font-semibold">{value}</dd>
      {hint ? (
        <dd
          className={cn(
            "text-micro",
            hint.endsWith("ortiqcha") ? "text-danger" : "text-ink-faint",
          )}
        >
          {hint}
        </dd>
      ) : null}
    </div>
  )
}

function FoundSummary({ lit, rows }: { lit: Set<string>; rows: { variant_label: string }[] }) {
  if (!rows.length) {
    return (
      <p className="rounded-control bg-canvas p-3 text-small text-ink-soft">
        Hech narsa topilmadi.
      </p>
    )
  }
  return (
    <p className="rounded-control bg-brand-soft p-3 text-small text-brand-deep">
      {rows.length} ta variant, {lit.size} ta joyda:{" "}
      {[...lit].join(", ") || "javonda emas"}
    </p>
  )
}
