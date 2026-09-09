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
 * from the API, and a fourth one appears because somebody seeded it.
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
 */

import { Loader2, Search, X } from "lucide-react"
import { useMemo, useState } from "react"

import { Empty, Fill, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, groups, units } from "@/lib/format"
import { useLocation, useMove, useShelfMap, useWhereIs } from "@/lib/queries"
import type { CellContent, Location } from "@/lib/types"

// A tile that has been standing this long is the one thing on the screen that
// should be impossible to ignore. An hour, because a sack that arrived before
// lunch and is still there is goods nobody has counted.
const SHOUT_AFTER_MINUTES = 60

export function ShelfMapPage() {
  const room = useShelfMap()
  const [needle, setNeedle] = useState("")
  const found = useWhereIs(needle)
  const [open, setOpen] = useState<string | null>(null)

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

  return (
    <div className="space-y-4">
      <PageHeader title="Ombor xaritasi" subtitle="Nima qayerda turibdi">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={needle}
            onChange={(event) => setNeedle(event.target.value)}
            placeholder="Nomi yoki shtrix-kod"
            className="h-control w-56 pl-8"
            aria-label="Qidirish"
          />
          {needle ? (
            <button
              type="button"
              onClick={() => setNeedle("")}
              aria-label="Tozalash"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-faint"
            >
              <X className="size-4" />
            </button>
          ) : null}
        </div>
      </PageHeader>

      <Problem error={room.error} />

      {searching ? <FoundSummary lit={lit} rows={found.data ?? []} /> : null}

      {room.isLoading ? <Waiting what="Xona" /> : null}

      {room.data ? (
        <>
          <Staging
            tiles={[...room.data.staging, ...room.data.couriers]}
            lit={searching ? lit : null}
            onOpen={setOpen}
          />
          <Racks
            cells={room.data.cells}
            lit={searching ? lit : null}
            onOpen={setOpen}
          />
        </>
      ) : null}

      <CellSheet code={open} onClose={() => setOpen(null)} />
    </div>
  )
}

// --------------------------------------------------------------------- racks

function Racks({
  cells,
  lit,
  onOpen,
}: {
  cells: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
}) {
  // Grouped from the data, so a fourth rack is a seed change and not a code
  // change — and so is a rack with five columns.
  const racks = useMemo(() => {
    const byRack = new Map<string, Location[]>()
    for (const cell of cells) {
      const key = cell.rack ?? "?"
      byRack.set(key, [...(byRack.get(key) ?? []), cell])
    }
    return [...byRack.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [cells])

  if (!racks.length) return <Empty what="Javonlar hali yaratilmagan." />

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {racks.map(([rack, own]) => (
        <Rack key={rack} rack={rack} cells={own} lit={lit} onOpen={onOpen} />
      ))}
    </div>
  )
}

function Rack({
  rack,
  cells,
  lit,
  onOpen,
}: {
  rack: string
  cells: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
}) {
  const columns = Math.max(...cells.map((cell) => cell.column_no ?? 1))
  const rows = Math.max(...cells.map((cell) => cell.row_no ?? 1))
  const at = (column: number, row: number) =>
    cells.find((cell) => cell.column_no === column && cell.row_no === row)

  return (
    <section className="rounded-panel border bg-surface p-3">
      <h2 className="mb-2 text-small font-semibold">{rack} javoni</h2>

      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `1.25rem repeat(${columns}, minmax(0, 1fr))` }}
      >
        {/* Rows top to bottom on screen, counted bottom-up on the shelf: row 1
            is where a person's eye starts and where the heavy things go. */}
        {Array.from({ length: rows }, (_, index) => rows - index).map((row) => (
          <RowOfCells key={row} row={row} columns={columns} at={at} lit={lit} onOpen={onOpen} />
        ))}

        <span />
        {Array.from({ length: columns }, (_, index) => index + 1).map((column) => (
          <span key={column} className="pt-1 text-center text-micro text-ink-faint">
            {column}
          </span>
        ))}
      </div>
    </section>
  )
}

function RowOfCells({
  row,
  columns,
  at,
  lit,
  onOpen,
}: {
  row: number
  columns: number
  at: (column: number, row: number) => Location | undefined
  lit: Set<string> | null
  onOpen: (code: string) => void
}) {
  return (
    <>
      <span className="grid place-items-center text-micro text-ink-faint">{row}</span>
      {Array.from({ length: columns }, (_, index) => index + 1).map((column) => {
        const cell = at(column, row)
        if (!cell) return <span key={column} />
        return <Cell key={column} cell={cell} lit={lit} onOpen={onOpen} />
      })}
    </>
  )
}

function Cell({
  cell,
  lit,
  onOpen,
}: {
  cell: Location
  lit: Set<string> | null
  onOpen: (code: string) => void
}) {
  const highlighted = lit?.has(cell.code) ?? false
  const dimmed = lit !== null && !highlighted

  return (
    <button
      type="button"
      onClick={() => onOpen(cell.code)}
      title={`${cell.code} · ${units(cell.units)}`}
      className={cn(
        "flex min-h-16 flex-col justify-between rounded-control border p-1.5 text-left transition",
        "hover:border-brand hover:bg-brand-soft",
        cell.units === 0 && "bg-canvas",
        highlighted && "border-brand ring-2 ring-brand",
        dimmed && "opacity-25",
      )}
    >
      <span className="whitespace-nowrap text-[0.6875rem] tabular leading-none text-ink-faint">
        {cell.code}
      </span>
      <span className="tabular text-small font-semibold leading-none">
        {cell.units ? groups(cell.units) : "—"}
      </span>
      <span className="text-micro text-ink-faint">
        {cell.products ? `${cell.products} xil` : " "}
      </span>
      <Fill percent={cell.fill_percent} />
    </button>
  )
}

// ------------------------------------------------------------------- staging

function Staging({
  tiles,
  lit,
  onOpen,
}: {
  tiles: Location[]
  lit: Set<string> | null
  onOpen: (code: string) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      {tiles.map((tile) => {
        const shouting =
          tile.kind === "receiving" &&
          tile.units > 0 &&
          tile.oldest_minutes >= SHOUT_AFTER_MINUTES
        const highlighted = lit?.has(tile.code) ?? false
        return (
          <button
            key={tile.code}
            type="button"
            onClick={() => onOpen(tile.code)}
            className={cn(
              "rounded-panel border bg-surface p-3 text-left transition hover:border-brand",
              shouting && "border-danger bg-danger-soft",
              highlighted && "border-brand ring-2 ring-brand",
              lit !== null && !highlighted && "opacity-25",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-micro font-semibold tracking-wide">{tile.code}</span>
              {shouting ? (
                <span className="rounded-full bg-danger px-1.5 text-micro text-danger-ink">
                  !
                </span>
              ) : null}
            </div>
            <div className="figure">{groups(tile.units)}</div>
            <div className="text-micro text-ink-soft">
              {tile.units ? age(tile.oldest_minutes) : "bo'sh"}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// --------------------------------------------------------------------- sheet

function CellSheet({ code, onClose }: { code: string | null; onClose: () => void }) {
  const place = useLocation(code)
  if (!code) return null

  return (
    <div className="fixed inset-0 z-40 flex" role="dialog" aria-label={`${code} tarkibi`}>
      <button
        type="button"
        aria-label="Yopish"
        onClick={onClose}
        className="flex-1 bg-black/30"
      />
      {/* A side sheet at a desk and a bottom sheet on a phone, which is where
          the thumb is. */}
      <aside className="flex max-h-[75vh] w-full flex-col overflow-auto rounded-t-panel border bg-surface p-4 sm:max-h-none sm:w-96 sm:rounded-none sm:rounded-l-panel self-end sm:self-auto">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-body font-semibold tabular">{code}</h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Yopish">
            <X className="size-4" />
          </Button>
        </div>

        {place.isLoading ? <Waiting /> : null}
        <Problem error={place.error} />

        {place.data ? (
          <>
            <dl className="mb-4 grid grid-cols-3 gap-2 text-micro">
              <Figure label="Dona" value={groups(place.data.units)} />
              <Figure label="Xil" value={groups(place.data.products)} />
              <Figure
                label="Sig'im"
                value={place.data.capacity ? groups(place.data.capacity) : "—"}
              />
            </dl>

            {place.data.contents.length === 0 ? (
              <Empty what="Bu joy bo'sh." />
            ) : (
              <ul className="divide-y">
                {place.data.contents.map((line) => (
                  <li key={line.variant_id} className="py-2">
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
                      {place.data ? (
                        <MoveLine line={line} from={place.data.code} />
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : null}
      </aside>
    </div>
  )
}

/**
 * Carry some of this line somewhere else.
 *
 * The only way a mis-shelved pile gets found again. Goods land on a shelf in
 * one action at the receiving desk — right, because whoever opened the sack is
 * standing at the shelf — but that means the cell is typed once, and a wrong
 * one leaves the ledger and the room disagreeing with nobody to notice. It
 * also brings a model back together when it has ended up split across two
 * cells, which is what keeps picking short.
 */
function MoveLine({ line, from }: { line: CellContent; from: string }) {
  const move = useMove()
  const [open, setOpen] = useState(false)
  const [to, setTo] = useState("")
  const [qty, setQty] = useState(String(line.qty))

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-micro text-brand-deep underline"
      >
        ko'chirish
      </button>
    )
  }

  return (
    <form
      className="flex items-center gap-1"
      onSubmit={(event) => {
        event.preventDefault()
        const wanted = to.trim().toUpperCase()
        if (!wanted) return
        move.mutate(
          {
            variant_id: line.variant_id,
            qty: Number(qty) || 1,
            from_code: from,
            to_code: wanted,
          },
          { onSuccess: () => setOpen(false) },
        )
      }}
    >
      <Input
        value={qty}
        onChange={(event) => setQty(event.target.value.replace(/\D/g, ""))}
        inputMode="numeric"
        aria-label="Nechta ko'chirish"
        className="h-control w-14 text-center tabular"
      />
      <Input
        autoFocus
        value={to}
        onChange={(event) => setTo(event.target.value.toUpperCase())}
        placeholder="A-01-01"
        aria-label="Qaysi yacheykaga"
        className="h-control w-24 tabular"
      />
      <Button type="submit" size="sm" disabled={move.isPending}>
        {move.isPending ? <Loader2 className="size-4 animate-spin" /> : "OK"}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
        <X className="size-4" />
      </Button>
    </form>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control bg-canvas p-2">
      <dt className="text-ink-faint">{label}</dt>
      <dd className="tabular text-body font-semibold">{value}</dd>
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
