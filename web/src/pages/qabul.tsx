/**
 * Tavar keldi — javonga qo'yamiz.
 *
 * The screen before this one was a form. It had every field on it at once —
 * search, chips, photograph, sizes, cost, cell — in one grey panel of equal
 * weight, and the owner's verdict was that you could not tell what the screen
 * was *for*. That was right: it looked like settings, not like a job.
 *
 * So the shape follows the job, and the job is said out loud at the top:
 *
 *   1 · Tavar keldi              what it is, and how many
 *   2 · Javonga joylashtirildi   which cell it went into
 *   3 · Telefonga chiqardik      photograph, price, category — elsewhere
 *
 * Step three is on another screen and is drawn here anyway, because the
 * confusion this fixes was at the beginning: somebody looking for "where do
 * the photographs go" needs to see, on the first screen, that the answer is
 * later and elsewhere.
 *
 * **It opens with two buttons, not with a form.** Goods we have had before are
 * a search and a count; goods we have never had are a card somebody writes.
 * Two different jobs, and showing both at once was the single biggest source
 * of the muddle. After that one tap the screen holds only what the answer
 * needs.
 *
 * **Cells are tapped, not typed.** `A-03-11` is one keystroke from `A-03-01`,
 * there is no scanner yet, and the racks are small enough to draw.
 *
 * **And a sack off the market is bigger than one cell.** It used to hold one
 * code for the whole pile, and the only way to use a second cell was a button
 * on the success panel that cleared the cell *and every count* — so the pile
 * was counted twice to be shelved twice. Now the destination is a **list** of
 * cells with a quantity each: the screen offers a plan as soon as it knows the
 * card and the count, one tap takes it, and the grid adds or drops cells from
 * it. One cell is still one tap and no arithmetic, because most sacks fit.
 */

import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  Loader2,
  MapPin,
  Package,
  Plus,
  Search,
  Sparkles,
  X,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Empty, PageHeader, Panel, Problem, Segmented, Waiting } from "@/components/page"
import { Capture, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, bySize, groups, money, tidySize, units } from "@/lib/format"
import {
  useBookInPile,
  useCancelSupply,
  useLocation,
  useProducts,
  usePutawayPlan,
  useSackSorted,
  useShelfMap,
  useStartRun,
  useSupplies,
  useVariants,
  useVocab,
} from "@/lib/queries"
import type {
  AdminProduct,
  Location,
  LocationDetail,
  Pile as BookedPile,
  PileSize,
} from "@/lib/types"

// A sack that has stood this long is the thing this shop actually loses money
// on: goods in the building that nothing has heard of.
const OVERNIGHT_MINUTES = 14 * 60

type Mode = "choose" | "existing" | "new"

export function QabulPage() {
  const [mode, setMode] = useState<Mode>("choose")
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [booked, setBooked] = useState<BookedPile | null>(null)

  function restart() {
    setBooked(null)
    setDraft(EMPTY)
    setMode("choose")
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Tavar keldi" subtitle="Javonga qo'yamiz" />

      <Steps at={booked || draft.named ? 2 : 1} />

      {booked ? (
        <Booked
          pile={booked}
          onAnotherColour={() => {
            // A colour that turned up after the sack was booked — the counting
            // screen takes several at once now, so this is the afterthought
            // case rather than the normal one. The kind, the make, the cost
            // and the cell stay; the colours and their counts start again.
            //
            // **Onto the card that was just written.** Without carrying the
            // product through, the next colour walked the new-card path again
            // and opened a *second* card for the same goods — the exact
            // duplicate this screen warns about everywhere else.
            const card = booked.product
            setBooked(null)
            setDraft((was) => ({
              ...was,
              product: card,
              kind: card.kind || was.kind,
              lots: [{ colour: "", sizes: {} }],
              snapshot: "",
              // The fare is already on the run that was just booked. Carrying
              // it over would charge the same taxi again for the second half
              // of the same sack.
              fare: "",
              // One cell takes whatever is counted into it, so it survives the
              // next colour. A split is a set of quantities that belonged to
              // the *last* count, and carrying it over would draw a division
              // of goods that are no longer on the form.
              spots: was.spots.length === 1 ? was.spots : [],
            }))
          }}
          onDone={restart}
        />
      ) : mode === "choose" ? (
        <Choose onPick={setMode} />
      ) : (
        <PileForm
          mode={mode}
          draft={draft}
          setDraft={setDraft}
          onBooked={setBooked}
          onBack={restart}
        />
      )}

      {mode === "choose" && !booked ? <Sacks /> : null}
    </div>
  )
}

// -------------------------------------------------------------- the three steps

/**
 * The job, said out loud. Three is the whole process rather than this screen's
 * progress: the third belongs to another screen, and saying so here is the
 * point — "where do the photographs go" is answered before it is asked.
 */
function Steps({ at }: { at: 1 | 2 }) {
  // Two spellings of each name. The whole value of the third step being
  // drawn here is that somebody sees it without being told, and on a phone
  // the long names pushed it off the end of the row — where it is exactly as
  // useful as not being there at all.
  const steps = [
    { n: 1, label: "Tavar keldi", short: "Keldi", hint: "nima, nechta" },
    {
      n: 2,
      label: "Javonga joylashtirildi",
      short: "Javonda",
      hint: "qaysi yacheykaga",
    },
    {
      n: 3,
      label: "Telefonga chiqardik",
      short: "Telefonda",
      hint: "rasm, narx, kategoriya",
      href: "/sotuvga-chiqarish",
    },
  ]

  // One line, not three cards. Three panels the height of a control, each
  // with a heading and a caption in it, took the top third of the screen to
  // say something the person doing the job already knows by the second sack
  // — and pushed the actual work below the fold on a phone. The hint is kept
  // for the step being worked, where it is an instruction, and dropped from
  // the other two, where it was decoration.
  return (
    <Panel bare>
      <ol className="flex items-center gap-1 overflow-x-auto px-4 py-2.5">
      {steps.map((step, index) => {
        const here = step.n === at
        const done = step.n < at
        const body = (
          <>
            <span
              className={cn(
                "grid size-5 shrink-0 place-items-center rounded-full text-micro font-semibold tabular",
                here && "bg-brand text-brand-ink",
                done && "bg-good text-good-ink",
                !here && !done && "bg-line-soft text-ink-faint",
              )}>
              {done ? <Check className="size-3" /> : step.n}
            </span>
            <span
              className={cn(
                "whitespace-nowrap text-small",
                here ? "font-semibold text-ink" : "text-ink-soft",
              )}>
              <span className="sm:hidden">{step.short}</span>
              <span className="hidden sm:inline">{step.label}</span>
            </span>
            {here ? (
              <span className="hidden whitespace-nowrap text-micro text-ink-faint sm:inline">
                · {step.hint}
              </span>
            ) : null}
          </>
        )
        return (
          <li key={step.n} className="flex shrink-0 items-center gap-2">
            {index ? <span className="h-px w-4 shrink-0 bg-line sm:w-6" /> : null}
            {step.href ? (
              <a
                href={step.href}
                className="group flex items-center gap-2 rounded-control px-1 py-0.5 transition-colors hover:bg-line-soft">
                {body}
                <ArrowRight className="size-3.5 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
              </a>
            ) : (
              <span className="flex items-center gap-2 px-1 py-0.5">{body}</span>
            )}
          </li>
        )
      })}
      </ol>
    </Panel>
  )
}

// ---------------------------------------------------------- one question first

/**
 * Two jobs, and you say which before anything else appears.
 *
 * Goods that have been here before are a search and a count. Goods that have
 * not are a card somebody writes. Both on screen at once was the muddle, and
 * this is the whole fix.
 */
function Choose({ onPick }: { onPick: (mode: Mode) => void }) {
  // Two rows, not two hoardings. They were a pair of half-screen boxes with
  // an icon floating at the top of each and a metre of white under the
  // words: an enormous target for a question that is answered once, in a
  // second, by somebody who already knows which of the two they are holding.
  // The row is the same object the rest of the app uses to say "go here and
  // do this", and it leaves the room for the work underneath.
  return (
    <Panel bare>
      <div className="grid gap-px bg-line sm:grid-cols-2">
        <Pick
          icon={Search}
          label="Bor tavar yana keldi"
          hint="Kartasi bor — faqat nechta va qaysi javonga"
          onClick={() => onPick("existing")}
        />
        <Pick
          icon={Sparkles}
          label="Yangi tavar"
          hint="Birinchi marta keldi — kartasi shu yerda ochiladi"
          onClick={() => onPick("new")}
        />
      </div>
    </Panel>
  )
}

function Pick({
  icon: Face,
  label,
  hint,
  onClick,
}: {
  icon: typeof Search
  label: string
  hint: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex items-center gap-3 bg-surface p-3 text-left transition-colors hover:bg-line-soft">
      <span className="grid size-10 shrink-0 place-items-center rounded-control bg-brand-soft text-brand-deep">
        <Face className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-body font-semibold">{label}</span>
        <span className="block truncate text-micro text-ink-faint">{hint}</span>
      </span>
      <ArrowRight className="size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
    </button>
  )
}

// ------------------------------------------------------------------- the pile

/** Said under the running total while the bar's button is dead. */
const MISSING_HINT = {
  count: "nechta kelganini yozing",
  cost: "tannarx yozilmagan",
  cell: "yacheyka tanlanmagan",
}

/**
 * One colour out of the sack, and how many of each size of it came.
 *
 * A sack from the market is usually one thing, and the form was built for
 * exactly that: one colour, then its sizes. But "usually" is not "always" — a
 * bale of shirts that is twenty black and twenty white is one sack, one cost
 * and one cell, and the only way to book it was to fill the whole form in,
 * shelve it, and start again with "shu qopdan yana bir rang". While counting
 * the white you could no longer see what you had written for the black, and
 * the running total at the bottom of the screen was the total of half a sack.
 *
 * So counting is a **list of colours** now. Each one is still booked as its
 * own pile — the receipt, the ledger and the API are exactly as they were,
 * and a pile is still one colour — but they are counted, checked and sent
 * together, and the person can see the whole sack while they count it.
 */
type Lot = { colour: string; sizes: Record<string, string> }

/**
 * One cell the sack is going into, and how much of it.
 *
 * `qty` is a string because it is typed. It is only read when there is more
 * than one spot: a single cell takes everything that was counted, whatever
 * that turns out to be, and asking somebody to type the number they have just
 * finished counting is a second chance to get it wrong.
 */
type Spot = { code: string; qty: string }

type Draft = {
  product: AdminProduct | null
  kind: string
  brand: string
  snapshot: string
  /** Never empty: there is always a colour being counted, even a nameless one. */
  lots: Lot[]
  unitCost: string
  /** Where it goes. Empty until somebody says; one cell for the ordinary
   *  sack; several, with a quantity each, for the sack that does not fit. */
  spots: Spot[]
  place: string
  /** What the van cost — the whole trip's, not this colour's. It is booked
   *  against the first pile of the sack, the way the server books the whole
   *  fare against the first sack of a run. */
  fare: string
  /** Whether step one is answered — the goods have a name. */
  named: boolean
}

const EMPTY: Draft = {
  product: null,
  kind: "",
  brand: "",
  snapshot: "",
  lots: [{ colour: "", sizes: {} }],
  unitCost: "",
  spots: [],
  place: "",
  fare: "",
  named: false,
}

/** What one spot actually takes: everything, when it is the only one. */
function takes(spots: Spot[], index: number, total: number): number {
  if (spots.length === 1) return total
  return Number(spots[index]?.qty) || 0
}

/** How much of the pile the split accounts for. */
function placed(spots: Spot[], total: number): number {
  if (!spots.length) return 0
  if (spots.length === 1) return total
  return spots.reduce((sum, spot) => sum + (Number(spot.qty) || 0), 0)
}

/**
 * The slice of the split that belongs to one colour.
 *
 * A pile is one colour on the server, and the split is written over the whole
 * sack — because that is how a sack is packed: you fill the first cell, then
 * the next, and what is in your hands when the first cell fills is whatever
 * colour you had got to. So the colours are laid end to end in the order they
 * are counted, and each one takes the part of the split it lands on. A colour
 * may straddle two cells, exactly as a size may inside one colour.
 *
 * Every slice sums to its own colour's count, which is what the server
 * demands of `placements`.
 */
function sliceFor(
  spots: Spot[],
  total: number,
  offset: number,
  count: number,
): { code: string; quantity: number }[] {
  const out: { code: string; quantity: number }[] = []
  let at = 0
  for (let index = 0; index < spots.length; index += 1) {
    const size = takes(spots, index, total)
    const from = Math.max(at, offset)
    const to = Math.min(at + size, offset + count)
    if (to > from) out.push({ code: spots[index].code, quantity: to - from })
    at += size
  }
  return out
}

/** The sizes of one colour that actually have a count on them. */
function linesOf(lot: Lot): PileSize[] {
  return Object.entries(lot.sizes)
    .map(([size, qty]) => ({ size, quantity: Number(qty) || 0 }))
    .filter((line) => line.quantity > 0)
}

/** How many pieces of one colour came. */
function countOf(lot: Lot): number {
  return linesOf(lot).reduce((sum, line) => sum + line.quantity, 0)
}

/**
 * The colour a card is written under when it is new.
 *
 * A card is one model in however many colours, so the first one entered is
 * the one the card is born with; the rest arrive as further variants of it.
 */
function firstColour(draft: Draft): string {
  return draft.lots[0]?.colour ?? ""
}

function PileForm({
  mode,
  draft,
  setDraft,
  onBooked,
  onBack,
}: {
  mode: Mode
  draft: Draft
  setDraft: (next: (was: Draft) => Draft) => void
  onBooked: (pile: BookedPile) => void
  onBack: () => void
}) {
  const book = useBookInPile()
  // The mutation's own `isPending` goes false between colours, so a
  // two-colour sack made the button flicker back to life mid-save — and a
  // second press would have booked the first colour twice.
  const [saving, setSaving] = useState(false)
  const [failed, setFailed] = useState<unknown>(null)
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((was) => ({ ...was, [key]: value }))

  const filled = draft.lots.filter((lot) => countOf(lot) > 0)
  const total = filled.reduce((sum, lot) => sum + countOf(lot), 0)
  const spots = draft.spots
  // A split that does not add up is not a destination. The server refuses it
  // in so many words, and being told at the shelf by a red panel after the
  // button is worse than being told before it.
  const spread = placed(spots, total)
  const over = spread - total
  const ready =
    draft.named &&
    total > 0 &&
    Number(draft.unitCost) > 0 &&
    spots.length > 0 &&
    over === 0 &&
    !saving
  // What is still wanted, in the order the screen asks for it — and null
  // once nothing is. It is said under the running total rather than written
  // on the button: a bar reading "Yacheykani tanlang" while the cell is
  // already picked and the cost is not sends somebody back to the grid to
  // tap a cell that is already blue.
  const missing: keyof typeof MISSING_HINT | "split" | null =
    total === 0
      ? "count"
      : !(Number(draft.unitCost) > 0)
        ? "cost"
        : !spots.length
          ? "cell"
          : over !== 0
            ? "split"
            : null
  const hint =
    missing === "split"
      ? over < 0
        ? `yana ${-over} dona joylanmadi`
        : `${over} dona ortiqcha bo'lindi`
      : missing
        ? MISSING_HINT[missing]
        : money(total * Number(draft.unitCost))

  /**
   * One request per colour, in order, and the card carried between them.
   *
   * A pile is one colour on the server and that is right — it is a receipt
   * line, and two colours bought at two prices are two lines. What was wrong
   * was making a person re-enter the cost, the cell and the market for the
   * second half of the same sack.
   *
   * The card matters more than it looks: for goods we have never had, the
   * first colour *creates* the card, and without handing its id to the next
   * one a two-colour sack wrote two cards for one thing — the exact
   * duplicate this screen warns about everywhere else.
   *
   * The split is cut the same way: the colours are laid end to end and each
   * takes the part of the split it lands on, so one cell goes in as one code
   * and several go in as `placements`. Whatever it is to the network, the
   * person pressed one button once.
   */
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!ready) return
    setSaving(true)
    setFailed(null)

    let card = draft.product
    const done: BookedPile[] = []
    let offset = 0
    try {
      for (const lot of filled) {
        const count = countOf(lot)
        const mine = sliceFor(spots, total, offset, count)
        offset += count
        const pile = await book.mutateAsync({
          product_id: card?.id,
          kind: draft.kind,
          brand: draft.brand,
          colour: lot.colour,
          snapshot_url: draft.snapshot,
          sizes: linesOf(lot),
          unit_cost: Number(draft.unitCost),
          // Exactly one of the two, and one cell is said as one cell —
          // `placements` of length one is the same shelf with more words in
          // the request.
          ...(mine.length === 1
            ? { location_code: mine[0].code }
            : { placements: mine }),
          place: draft.place.trim(),
          // Once. Every pile opens its own supply row, so a fare sent with
          // each colour would multiply one taxi by the number of colours in
          // the sack — and the run total would read two or three trips. The
          // whole of it goes against the first, which is what the server
          // itself does when a run is declared as five sacks.
          transport_cost: done.length === 0 ? Number(draft.fare) || 0 : 0,
        })
        card = pile.product
        done.push(pile)
      }
      onBooked(merge(done))
    } catch (problem) {
      // Half a sack can be on the shelf by the time something refuses, and
      // the goods that went in are *in*. So what was booked is taken off the
      // form — pressing the button again must not book it a second time —
      // and the message says plainly how far it got.
      if (done.length) {
        const shelved = new Set(done.map((_, index) => filled[index]))
        setDraft((was) => ({
          ...was,
          lots: was.lots.filter((lot) => !shelved.has(lot)),
        }))
      }
      setFailed(
        done.length
          ? new Error(
              `${done.length} ta rang javonga qo'yildi, keyingisida xato: ${
                problem instanceof Error ? problem.message : "noma'lum xato"
              }`,
            )
          : problem,
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="space-y-3 pb-28" onSubmit={submit}>
      {draft.named ? (
        <Named draft={draft} onChange={onBack} />
      ) : mode === "existing" ? (
        <FindCard
          onPick={(product) =>
            setDraft((was) => ({ ...was, product, kind: product.kind, named: true }))
          }
          onBack={onBack}
        />
      ) : (
        <WriteCard
          draft={draft}
          onSet={set}
          onNamed={() => set("named", true)}
          onPick={(product) =>
            setDraft((was) => ({ ...was, product, kind: product.kind, named: true }))
          }
          onBack={onBack}
        />
      )}

      {draft.named ? (
        <>
          <Counts
            product={draft.product}
            kind={draft.kind}
            lots={draft.lots}
            onSet={(lots) => set("lots", lots)}
          />

          <Panel>
            <div className="grid gap-3 sm:grid-cols-2">
              <label>
                <span className="mb-1 block text-micro text-ink-soft">
                  Tannarx — bir dona
                </span>
                {/* Grouped as it is typed, and stored as digits. A cost is
                    six or seven figures here and `850000` on a screen is read
                    as `85 000` by somebody in a hurry — which is the one
                    mistake on this form that nothing downstream can catch. */}
                <Input
                  value={draft.unitCost ? groups(Number(draft.unitCost)) : ""}
                  onChange={(event) =>
                    set("unitCost", event.target.value.replace(/\D/g, ""))
                  }
                  inputMode="numeric"
                  placeholder="85 000"
                  aria-label="Tannarx"
                  className="h-control-lg tabular text-body" />
              </label>
              {/* The trip, in one column: where the sack came from and what
                  the van cost to bring it. The fare is per run and the cost
                  above is per piece, so they are not the same kind of number
                  and do not sit side by side as though they were. */}
              <div className="space-y-3">
                <Place value={draft.place} onSet={(place) => set("place", place)} />
                <label className="block">
                  <span className="mb-1 block text-micro text-ink-soft">
                    Yo'l puli
                  </span>
                  {/* Nothing collected this, so `supplies.transport_cost` was
                      nought in every row and every "what went out to the
                      market" figure was 5–10% short of what was paid. */}
                  <Input
                    value={draft.fare ? groups(Number(draft.fare)) : ""}
                    onChange={(event) =>
                      set("fare", event.target.value.replace(/\D/g, ""))
                    }
                    inputMode="numeric"
                    placeholder="30 000"
                    aria-label="Yo'l puli"
                    className="h-control tabular" />
                  <span className="mt-1 block text-micro text-ink-faint">
                    Butun qatnov uchun — ranglarga bo'linmaydi.
                  </span>
                </label>
              </div>
            </div>
          </Panel>

          <Cells
            spots={spots}
            total={total}
            productId={draft.product?.id ?? null}
            onSet={(next) => set("spots", next)}
          />
        </>
      ) : null}

      <Problem error={failed} />

      {/* The bar stays put. Reaching the button used to mean scrolling past
          nine fields with a sack in the other hand. */}
      {draft.named ? (
        <div className="fixed inset-x-0 bottom-0 border-t bg-surface p-3 md:left-60">
          <div className="mx-auto flex max-w-4xl items-center gap-3">
            <div className="min-w-0 flex-1">
              <div
                className={cn(
                  "truncate text-body font-semibold tabular",
                  total ? "text-ink" : "text-ink-soft",
                )}>
                {total ? units(total) : "Nechta keldi?"}
                {spots.length ? (
                  <span className="text-ink-soft"> → {where(spots)}</span>
                ) : null}
              </div>
              <div
                className={cn(
                  "truncate text-micro tabular",
                  missing === "split" ? "text-danger" : "text-ink-faint",
                )}>
                {hint}
              </div>
            </div>
            {/* The button says what is missing rather than saying the last
                thing that is missing. A bar that reads "Yacheykani tanlang"
                while the cell is already picked and the cost is not sends
                somebody back to the grid to tap a cell that is already
                blue. */}
            <Button size="lg" type="submit" disabled={!ready} className="gap-2">
              {saving ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Check className="size-5" />
              )}
              {spots.length === 1
                ? `${spots[0].code} ga qo'ydim`
                : spots.length > 1
                  ? `${spots.length} ta yacheykaga qo'ydim`
                  : "Javonga qo'ydim"}
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  )
}

/**
 * Several colours booked in one go, said as one thing.
 *
 * They are separate piles and separate receipt lines, and the person who
 * emptied the sack does not care: what they want to read is that the sack
 * went in, how many that was, and every code to write on the box.
 */
function merge(piles: BookedPile[]): BookedPile {
  const last = piles[piles.length - 1]
  // Two colours into the same cell is one line on the success panel, not two
  // — what it answers is "how much went where", and the shelf does not know
  // which colour got there first.
  const byCell = new Map<string, number>()
  for (const pile of piles) {
    for (const spot of pile.placements ?? []) {
      byCell.set(spot.code, (byCell.get(spot.code) ?? 0) + spot.quantity)
    }
  }
  const placements = [...byCell.entries()].map(([code, quantity]) => ({ code, quantity }))
  return {
    ...last,
    quantity: piles.reduce((sum, one) => sum + one.quantity, 0),
    total_cost: piles.reduce((sum, one) => sum + one.total_cost, 0),
    labels: piles.flatMap((one) => one.labels),
    placements,
    location_code: placements.map((one) => one.code).join(", ") || last.location_code,
  }
}

/** The destination on one line, for a bar that is one line high. */
function where(spots: Spot[]): string {
  if (spots.length === 1) return spots[0].code
  if (spots.length === 2) return spots.map((spot) => spot.code).join(" + ")
  return `${spots.length} ta yacheyka`
}

/**
 * Step one, answered, on one line.
 *
 * It was a green panel the width of the screen with a green border round it,
 * which is the treatment this app gives a thing that has just *happened* —
 * and nothing had happened yet. Answering "which goods" is not a success, it
 * is the first field of a form; the tick is enough to say it is settled, and
 * the loud green now belongs to the booking at the end where it means
 * something.
 */
function Named({ draft, onChange }: { draft: Draft; onChange: () => void }) {
  const title =
    draft.product?.title ??
    [draft.kind, draft.brand, firstColour(draft)].filter(Boolean).join(" · ")

  return (
    <Panel>
      <div className="flex items-center gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-control bg-good-soft text-good">
          <Check className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-body font-semibold">{title}</div>
          {draft.product ? (
            <div className="truncate text-micro tabular text-ink-faint">
              {draft.product.sku} · javonda {draft.product.stock_left} dona
            </div>
          ) : null}
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={onChange}>
          O'zgartirish
        </Button>
      </div>
    </Panel>
  )
}

// ------------------------------------------------------- goods we have had

function FindCard({
  onPick,
  onBack,
}: {
  onPick: (product: AdminProduct) => void
  onBack: () => void
}) {
  const [needle, setNeedle] = useState("")
  const found = useProducts(needle, "")

  return (
    <Panel
      title="Qaysi tavar keldi?"
      aside={
        <Button type="button" variant="ghost" size="sm" onClick={onBack} aria-label="Orqaga">
          <X className="size-4" />
        </Button>
      }
    >
      <div className="space-y-3">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
        <Input
          autoFocus
          value={needle}
          onChange={(event) => setNeedle(event.target.value)}
          placeholder="nom yoki kod"
          aria-label="Mavjud kartani qidirish"
          className="h-control-lg pl-8 text-body" />
      </div>

      {found.isLoading ? <Waiting what="Kartalar" /> : null}

      <ul className="divide-y">
        {(found.data?.items ?? []).slice(0, 8).map((product) => (
          <li key={product.id}>
            <button
              type="button"
              onClick={() => onPick(product)}
              className="flex w-full items-center gap-3 py-2 text-left">
              <Thumb product={product} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-small font-medium">{product.title}</div>
                <div className="text-micro tabular text-ink-faint">
                  {product.stock_left} dona · {product.sku}
                </div>
              </div>
              <ArrowRight className="size-4 shrink-0 text-ink-faint" />
            </button>
          </li>
        ))}
      </ul>

      {needle.trim() && found.data?.items.length === 0 ? (
        <p className="text-small text-ink-soft">
          Bunday karta yo'q — orqaga qaytib "Yangi tavar"ni tanlang.
        </p>
      ) : null}
      </div>
    </Panel>
  )
}

// ------------------------------------------------------ goods we have not

function WriteCard({
  draft,
  onSet,
  onNamed,
  onPick,
  onBack,
}: {
  draft: Draft
  onSet: <K extends keyof Draft>(key: K, value: Draft[K]) => void
  onNamed: () => void
  onPick: (product: AdminProduct) => void
  onBack: () => void
}) {
  const vocab = useVocab()

  return (
    <Panel
      title="Qanday tavar?"
      aside={
        <Button type="button" variant="ghost" size="sm" onClick={onBack} aria-label="Orqaga">
          <X className="size-4" />
        </Button>
      }
    >
      <div className="space-y-3">
      <Chips
        label="Tur"
        options={vocab.data?.kinds ?? []}
        value={draft.kind}
        onChange={(value) => onSet("kind", value)}
        placeholder="Krossovka" />
      <Chips
        label="Brend"
        options={vocab.data?.brands ?? []}
        value={draft.brand}
        onChange={(value) => onSet("brand", value)}
        placeholder="Nike"
        none="brendsiz" />
      {/* The colour the card is born with. Further colours out of the same
          sack are added under "Nechta keldi?" — they are counts against this
          card, not a second card. */}
      <Chips
        label="Rang"
        options={vocab.data?.colours ?? []}
        value={firstColour(draft)}
        onChange={(value) =>
          onSet("lots", [
            { colour: value, sizes: draft.lots[0]?.sizes ?? {} },
            ...draft.lots.slice(1),
          ])
        }
        placeholder="Qora" />

      {draft.kind.trim() ? (
        <>
          <Maybe draft={draft} onPick={onPick} />
          <Capture
            colour=""
            current={draft.snapshot || undefined}
            onTaken={(_, url) => onSet("snapshot", url)}
            guide="tanish uchun — mijozga ko'rinmaydi"
            placeholder="rasm" />
          <Button size="lg" type="button" className="w-full gap-2" onClick={onNamed}>
            Davom etish
            <ArrowRight className="size-5" />
          </Button>
        </>
      ) : null}
      </div>
    </Panel>
  )
}

/**
 * "Was it not this one?" — asked before a second card for the same goods.
 *
 * Nothing stopped "Yangi tavar" writing a card that already existed, and the
 * dev database ended up holding `nike · qora`, `nike · Qora` and `Nike · Qora`
 * for one pair of trainers. Tidying the spelling does not fix that: the same
 * goods typed the same way twice is still two cards.
 *
 * It asks rather than merges. Kind and make are not identity — Nike sells more
 * than one trainer — so collapsing them automatically would put two models on
 * one card, and a picker sent to that cell could not tell which the order
 * meant. A duplicate costs a merge; a wrong match costs a returned order.
 */
function Maybe({
  draft,
  onPick,
}: {
  draft: Draft
  onPick: (product: AdminProduct) => void
}) {
  const needle = [draft.kind, draft.brand].filter(Boolean).join(" ")
  const found = useProducts(needle, "")
  const like = (found.data?.items ?? []).slice(0, 3)

  if (!like.length) return null

  return (
    <div className="space-y-2 rounded-control bg-warn-soft p-2">
      <p className="text-micro text-warn-ink">
        Bunga o'xshash karta bor — <b>shu emasmi?</b> Bo'lsa, bosing: yangi
        karta ochilmaydi, shunga qo'shiladi.
      </p>
      <ul className="space-y-1">
        {like.map((product) => (
          <li key={product.id}>
            <button
              type="button"
              onClick={() => onPick(product)}
              className="flex w-full items-center gap-2 rounded-control bg-surface p-2 text-left">
              <Thumb product={product} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-small font-medium">{product.title}</div>
                <div className="text-micro tabular text-ink-faint">
                  {product.stock_left} dona · {product.sku}
                </div>
              </div>
              <ArrowRight className="size-4 shrink-0 text-ink-faint" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Thumb({ product }: { product: AdminProduct }) {
  if (!product.snapshot_url) {
    return (
      <span className="grid size-11 shrink-0 place-items-center rounded-control bg-canvas text-ink-faint">
        <Package className="size-5" />
      </span>
    )
  }
  return (
    <img
      src={mediaUrl(product.snapshot_url)}
      alt=""
      className="size-11 shrink-0 rounded-control object-cover" />
  )
}

/** A chip row that grows. One spelling per thing — the server tidies them. */
function Chips({
  label,
  options,
  value,
  onChange,
  placeholder,
  none,
}: {
  label: string
  options: string[]
  value: string
  onChange: (value: string) => void
  placeholder: string
  none?: string
}) {
  const [writing, setWriting] = useState(false)
  // The value first, always, even when it is not one of the learned options.
  // A word typed into "+ yangi" and finished with Enter was held in state and
  // drawn nowhere: the chip row showed the six old kinds, none of them lit,
  // and the person who had just typed "Palto" saw no sign of it. It read as
  // the field having eaten what they wrote.
  const shown = [
    ...(value && !options.includes(value) ? [value] : []),
    ...options.slice(0, 10),
  ]
  const typing = writing || (shown.length === 0 && !value)

  return (
    <div>
      <span className="mb-1 block text-micro text-ink-soft">{label}</span>
      <div className="flex flex-wrap gap-1">
        {shown.map((one) => (
          <button
            key={one}
            type="button"
            onClick={() => onChange(one === value ? "" : one)}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              one === value && "border-brand bg-brand text-brand-ink",
            )}
          >
            {one}
          </button>
        ))}
        {none && !value ? (
          <span className="inline-flex h-control items-center rounded-control border border-dashed px-3 text-small text-ink-faint">
            {none}
          </span>
        ) : null}
        {typing ? (
          <Input
            autoFocus={writing}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            // Enter finishes the word, and nothing else. Without this it
            // reached the form around this field and submitted the pile —
            // typing a new kind and pressing Enter, which is what anybody
            // does, either booked goods or bounced off a disabled button.
            onKeyDown={(event) => {
              if (event.key !== "Enter") return
              event.preventDefault()
              setWriting(false)
              event.currentTarget.blur()
            }}
            onBlur={() => setWriting(false)}
            placeholder={placeholder}
            aria-label={label}
            className="h-control w-40" />
        ) : (
          <button
            type="button"
            onClick={() => setWriting(true)}
            className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
            + yangi
          </button>
        )}
      </div>
    </div>
  )
}

// -------------------------------------------------------------------- how many

/**
 * What came out of the sack, colour by colour.
 *
 * The screen used to ask for **one** colour and its sizes, because a market
 * sack usually is one thing. When it was not — twenty black shirts and twenty
 * white in the same bale — there was no way to say so: you booked the black,
 * shelved it, and started the form again for the white, with the running
 * total at the bottom of the screen showing half a sack the whole time. The
 * question "oqdan nechta, qoradan nechta keldi" had no answer on this screen
 * at all.
 *
 * Now each colour is a block: its name, its sizes, its own total. "+ yana
 * rang" adds another, and the sack's total is under the lot. Sizes stay
 * *inside* a colour rather than becoming a grid of colours × sizes, because
 * a grid of empty boxes is a form to fill in, and this is a list of what is
 * in your hands: you count the black shirts, you write them down, you pick up
 * the white ones.
 */
function Counts({
  product,
  kind,
  lots,
  onSet,
}: {
  product: AdminProduct | null
  kind: string
  lots: Lot[]
  onSet: (lots: Lot[]) => void
}) {
  const vocab = useVocab()
  const grid = useVariants(product?.id ?? null)
  const [naming, setNaming] = useState(false)

  // Some things have no size: a cap, a bag, a wristwatch. The form asked
  // every kind for sizes, and a person holding a sack of caps types
  // *something* into a box that will not go away — which is how a size called
  // "KS" was born, and how one card ended up holding both a sizeless grey cap
  // and a grey cap in M. So the question is answered before it is asked: from
  // the card when there is one, and otherwise from what this kind has always
  // arrived as. `chose` is a hand on the wheel — once somebody has said which
  // it is, nothing overrules them.
  const [chose, setChose] = useState<boolean | null>(null)
  const cardIsSizeless =
    (grid.data ?? []).length > 0 && (grid.data ?? []).every((cell) => !cell.size)
  const kindIsSizeless = (vocab.data?.sizeless ?? []).includes(kind)
  const sizeless = chose ?? (product ? cardIsSizeless : kindIsSizeless)

  // The colours this card already comes in. Auto-picked into the first block
  // when there is only one, because a question with one answer is a tap for
  // nothing.
  const own = useMemo(() => {
    const seen = new Set((grid.data ?? []).map((cell) => cell.colour))
    return [...seen]
  }, [grid.data])
  const only = own.length === 1 ? own[0] : null
  useEffect(() => {
    if (only !== null && !lots[0]?.colour && lots.length === 1 && !naming) {
      onSet([{ ...lots[0], colour: only }])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only])

  // What a colour and size already holds, so a second count of the same size
  // reads as an addition rather than as a figure about to be overwritten.
  const already = useMemo(() => {
    const map = new Map<string, number>()
    for (const cell of grid.data ?? []) {
      map.set(`${cell.colour} ${cell.size}`, cell.stock_left)
    }
    return map
  }, [grid.data])

  // A sized count left behind after the shape changed would be submitted from
  // behind the sizeless box, where nobody can see it. The shape on screen and
  // the counts underneath it are the same thing or they are a bug.
  const stale = lots.some((lot) =>
    sizeless
      ? Object.keys(lot.sizes).some((size) => size !== "")
      : lot.sizes[""] !== undefined,
  )
  useEffect(() => {
    if (stale) onSet(lots.map((lot) => ({ ...lot, sizes: {} })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stale])

  const total = lots.reduce((sum, lot) => sum + countOf(lot), 0)
  const named = lots.filter((lot) => lot.colour || countOf(lot) > 0).length

  /** Sizes worth offering for one colour: the card's own, and what this kind
   *  last arrived in — minus the ones already on that colour's list. */
  function suggest(lot: Lot): string[] {
    const mine = (grid.data ?? [])
      .filter((cell) => !lot.colour || cell.colour === lot.colour)
      .map((cell) => cell.size)
    const seen = new Set([...mine, ...(vocab.data?.sizes[kind] ?? [])].map(tidySize))
    seen.delete("")
    for (const size of Object.keys(lot.sizes)) seen.delete(size)
    return [...seen].sort(bySize)
  }

  const write = (index: number, next: Lot) =>
    onSet(lots.map((lot, at) => (at === index ? next : lot)))

  return (
    <Panel
      title="Nechta keldi?"
      /* Two visible choices. It was one faint word in the corner reading
         "o'lchamsiz", which is both the name of a state and the name of the
         act of leaving it — nobody found it, and the sack of caps got a
         size typed into it instead.
         One control with two halves rather than two buttons side by side:
         a pair of equally-weighted outlined buttons reads as two things
         you can do, and this is one thing that is either on or off. */
      aside={
        <Segmented
          label="O'lcham bormi?"
          value={sizeless ? "sizeless" : "sized"}
          onChange={(next) => {
            const on = next === "sizeless"
            if (on === sizeless) return
            setChose(on)
            onSet(lots.map((lot) => ({ ...lot, sizes: {} })))
          }}
          options={[
            { key: "sized", label: "O'lchamli" },
            { key: "sizeless", label: "O'lchamsiz" },
          ]}
        />
      }
    >
      <div className="space-y-3">
      {lots.map((lot, index) => (
        <LotBlock
          key={index}
          lot={lot}
          sizeless={sizeless}
          // A colour already being counted is not offered again: two blocks
          // of black are two piles of the same thing and one of them is a
          // miscount waiting to happen.
          colours={(own.length ? own : (vocab.data?.colours ?? [])).filter(
            (one) => one === lot.colour || !lots.some((other) => other.colour === one),
          )}
          suggested={suggest(lot)}
          already={already}
          alone={lots.length === 1}
          onChange={(next) => write(index, next)}
          onDrop={() => onSet(lots.filter((_, at) => at !== index))}
          onNaming={setNaming}
        />
      ))}

      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Only once the colour in hand has a name. An "+ yana rang" tapped
            twice in a row leaves two nameless blocks and no way to tell them
            apart. */}
        {lots.every((lot) => lot.colour) ? (
          <button
            type="button"
            onClick={() => onSet([...lots, { colour: "", sizes: {} }])}
            className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
            + yana rang
          </button>
        ) : (
          <span />
        )}

        {total > 0 ? (
          <p className="text-small text-ink-soft">
            {named > 1 ? "Qopdan jami " : "Jami "}
            <b className="tabular text-ink">{total}</b> dona
          </p>
        ) : null}
      </div>
      </div>
    </Panel>
  )
}

/**
 * One colour, and everything that came in it.
 *
 * Its own box with its own total, because that total is the thing being
 * checked: somebody counts a pile of black shirts into the phone and looks up
 * to see whether the phone agrees with the pile. A row of sizes under a
 * shared heading cannot be checked against anything.
 */
function LotBlock({
  lot,
  sizeless,
  colours,
  suggested,
  already,
  alone,
  onChange,
  onDrop,
  onNaming,
}: {
  lot: Lot
  sizeless: boolean
  colours: string[]
  suggested: string[]
  already: Map<string, number>
  /** The only colour on the form — it cannot be removed, only emptied. */
  alone: boolean
  onChange: (next: Lot) => void
  onDrop: () => void
  onNaming: (writing: boolean) => void
}) {
  const [picking, setPicking] = useState(!lot.colour)
  const [writing, setWriting] = useState(false)
  const [adding, setAdding] = useState("")
  const [typing, setTyping] = useState(false)

  const count = countOf(lot)
  const chosen = Object.keys(lot.sizes).sort(bySize)

  // One spelling, so `xl` typed in a hurry does not stand beside `XL` as a
  // second size, a second variant and a second barcode.
  function add(size: string) {
    const wanted = tidySize(size)
    if (wanted)
      onChange({
        ...lot,
        sizes: { ...lot.sizes, [wanted]: lot.sizes[wanted] || "1" },
      })
    setAdding("")
  }

  function drop(size: string) {
    const rest = { ...lot.sizes }
    delete rest[size]
    onChange({ ...lot, sizes: rest })
  }

  function name(colour: string) {
    onChange({ ...lot, colour })
    setPicking(false)
  }

  return (
    <div className="overflow-hidden rounded-control border border-line">
      {/* ----------------------------------------------------- which colour */}
      <div className="flex items-center gap-2 border-b border-line bg-canvas px-2 py-1.5">
        {lot.colour && !picking ? (
          <>
            {/* The name is the control. A word saying "rangni almashtirish"
                beside it is a second thing to read on a line whose whole job
                is to say which colour this block is. */}
            <button
              type="button"
              onClick={() => setPicking(true)}
              className="flex min-w-0 flex-1 items-center gap-1 rounded-control px-1 py-0.5 text-left transition-colors hover:bg-line-soft">
              <span className="truncate text-small font-semibold">{lot.colour}</span>
              <ChevronDown className="size-3.5 shrink-0 text-ink-faint" />
            </button>
            <span className="tabular text-micro text-ink-soft">{count} dona</span>
          </>
        ) : (
          <span className="min-w-0 flex-1 text-micro font-medium text-ink-soft">
            Qaysi rang keldi?
          </span>
        )}
        {!alone ? (
          <button
            type="button"
            onClick={onDrop}
            aria-label={`${lot.colour || "rang"} — ro'yxatdan olib tashlash`}
            className="rounded-control p-1 text-ink-faint hover:bg-line-soft hover:text-danger">
            <X className="size-3.5" />
          </button>
        ) : null}
      </div>

      {picking ? (
        <div className="flex flex-wrap gap-1 border-b border-line p-2">
          {colours.map((one) => (
            <button
              key={one}
              type="button"
              onClick={() => name(one)}
              className={cn(
                "h-control rounded-control border px-3 text-small",
                one === lot.colour && "border-brand bg-brand text-brand-ink",
              )}>
              {one || "rangsiz"}
            </button>
          ))}
          {writing ? (
            <Input
              autoFocus
              value={lot.colour}
              onChange={(event) => onChange({ ...lot, colour: event.target.value })}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return
                event.preventDefault()
                setWriting(false)
                onNaming(false)
                if (lot.colour) setPicking(false)
                event.currentTarget.blur()
              }}
              onBlur={() => {
                setWriting(false)
                onNaming(false)
                if (lot.colour) setPicking(false)
              }}
              placeholder="Oq"
              aria-label="Yangi rang"
              className="h-control w-32" />
          ) : (
            <button
              type="button"
              onClick={() => {
                onChange({ ...lot, colour: "" })
                setWriting(true)
                onNaming(true)
              }}
              className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
              + yangi rang
            </button>
          )}
        </div>
      ) : null}

      {/* --------------------------------------------------------- how many
          Not before the colour has a name: a block of counts belonging to
          nothing in particular is the muddle this whole screen exists to
          undo, and "which colour" is one tap. */}
      <div className={cn("space-y-2 p-2", !lot.colour && "hidden")}>
        {sizeless ? (
          <label className="flex items-center gap-2">
            <Input
              value={lot.sizes[""] ?? ""}
              onChange={(event) =>
                onChange({
                  ...lot,
                  sizes: { "": event.target.value.replace(/\D/g, "") },
                })
              }
              inputMode="numeric"
              placeholder="12"
              aria-label={`${lot.colour || "Rang"} — nechta`}
              className="h-control-lg w-28 tabular text-body"
            />
            <span className="text-small text-ink-soft">dona keldi</span>
          </label>
        ) : (
          <>
            {/* What arrived, one row per size — the size named on the left,
                the count in the middle, "dona" after it, and a way off the
                list. This used to be a grid of chips with a bare box under
                each, so nothing on screen said which half was a size and
                which was a count. */}
            {chosen.length ? (
              <ul className="divide-y rounded-control border">
                {chosen.map((size) => (
                  <SizeRow
                    key={size}
                    size={size}
                    value={lot.sizes[size] ?? ""}
                    already={already.get(`${lot.colour} ${size}`) ?? 0}
                    onChange={(value) =>
                      onChange({
                        ...lot,
                        sizes: { ...lot.sizes, [size]: value },
                      })
                    }
                    onDrop={() => drop(size)}
                  />
                ))}
              </ul>
            ) : null}

            <div className="flex flex-wrap items-center gap-1">
              <span className="mr-1 text-micro text-ink-soft">
                {chosen.length ? "Yana o'lcham:" : "Qanday o'lchamlar keldi?"}
              </span>
              {suggested.map((size) => (
                <button
                  key={size}
                  type="button"
                  onClick={() => add(size)}
                  className="h-control rounded-control border px-3 text-small">
                  {size}
                </button>
              ))}
              {typing ? (
                <Input
                  autoFocus
                  value={adding}
                  onChange={(event) => setAdding(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter") return
                    event.preventDefault()
                    add(adding)
                  }}
                  onBlur={() => {
                    add(adding)
                    setTyping(false)
                  }}
                  placeholder="XL"
                  aria-label="Yangi o'lcham"
                  className="h-control w-24 text-center"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setTyping(true)}
                  className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
                  + boshqa
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

/**
 * One size, and how many of it arrived.
 *
 * A row rather than a column, because a row can be read: the size, the count,
 * the word dona. Minus and plus are for counting a sack out by hand, the box
 * for when the number is already known, and the cross is for the size that
 * should never have been on the list.
 */
function SizeRow({
  size,
  value,
  already,
  onChange,
  onDrop,
}: {
  size: string
  value: string
  already: number
  onChange: (value: string) => void
  onDrop: () => void
}) {
  const count = Number(value) || 0

  // Everything the hand touches is `shrink-0`, and the words are what give
  // way. Without it, flexbox took the width out of the *count box* on a
  // phone — 26 pixels of it, twelve of them padding — so the number somebody
  // had just typed was clipped out of sight while "omborda 6 → 12" beside it
  // was printed in full. The box is the whole row.
  const shelf = already > 0 && count > 0 ? `omborda ${already} → ${already + count}` : ""

  return (
    <li className="p-2">
      <div className="flex items-center gap-2">
        <span className="w-10 shrink-0 text-body font-medium">{size}</span>
        <button
          type="button"
          onClick={() => onChange(count > 1 ? String(count - 1) : "")}
          aria-label={`${size} — bittasini ayirish`}
          className="h-control w-11 shrink-0 rounded-control border text-body">
          −
        </button>
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
          inputMode="numeric"
          aria-label={`${size} — nechta`}
          className={cn(
            "h-control-lg w-16 shrink-0 px-1 text-center tabular text-body",
            count > 0 && "border-brand",
          )}
        />
        <button
          type="button"
          onClick={() => onChange(String(count + 1))}
          aria-label={`${size} — bittasini qo'shish`}
          className="h-control w-11 shrink-0 rounded-control border text-body">
          +
        </button>
        {/* The unit and the running shelf figure. On a phone the sentence
          moves under the row rather than being squeezed into "ombor…",
          which is a word that tells nobody anything. */}
        <span className="hidden shrink text-small text-ink-soft sm:inline">dona</span>
        <span className="hidden min-w-0 flex-1 truncate text-micro text-ink-faint sm:inline">
          {shelf}
        </span>
        <span className="flex-1 sm:hidden" />
        <button
          type="button"
          onClick={onDrop}
          aria-label={`${size} — ro'yxatdan olib tashlash`}
          className="h-control w-9 shrink-0 rounded-control text-small text-ink-faint hover:bg-line-soft hover:text-danger">
          ✕
        </button>
      </div>
      {shelf ? (
        <div className="mt-1 pl-1 text-micro text-ink-faint sm:hidden">{shelf} dona</div>
      ) : null}
    </li>
  )
}

function Place({ value, onSet }: { value: string; onSet: (place: string) => void }) {
  const runs = useSupplies()
  // Spelt the same way twice. A market is not an entity anybody maintains, so
  // the list is simply the ones already written down.
  const places = useMemo(() => {
    const seen = new Set<string>()
    for (const run of runs.data ?? []) if (run.place) seen.add(run.place)
    return [...seen].slice(0, 10)
  }, [runs.data])

  return (
    <label className="block">
      <span className="mb-1 block text-micro text-ink-soft">Qayerdan</span>
      <Input
        value={value}
        onChange={(event) => onSet(event.target.value)}
        placeholder="Chorsu"
        aria-label="Qayerdan"
        list="mb-places"
        className="h-control-lg" />
      <datalist id="mb-places">
        {places.map((one) => (
          <option key={one} value={one} />
        ))}
      </datalist>
    </label>
  )
}

// ----------------------------------------------------------------- which cell

/**
 * The racks, tapped rather than typed.
 *
 * `A-03-11` is one keystroke away from `A-03-01`, there is no scanner yet, and
 * the room is small enough to draw. Nothing here is hard-coded to three units
 * of four by four: the racks come from the data, so a fourth one is a seed
 * change.
 */
/**
 * What is already in a cell, in one sentence.
 *
 * One model per cell is the working discipline, and the software supports it
 * rather than enforcing it — so this is the thing that makes a wrong choice
 * visible: a picker reaching into a cell of black shirts to fetch a red one is
 * the mistake nobody catches until the parcel is at a door. A valid code for
 * the wrong cell is exactly what a grid of 48 identical squares invites.
 *
 * Counted by *model*, not by row of contents. A shirt in two sizes is two rows
 * and one thing on the shelf, so counting rows said "and 1 other kind" about
 * the goods the person was holding — and the whole point of the line is to
 * warn that something *else* is in there.
 */
function inside(cell: LocationDetail | undefined): { text: string; odd: boolean } {
  if (!cell) return { text: "", odd: false }
  if (!cell.contents.length) return { text: "bo'sh", odd: false }
  const models = [...new Set(cell.contents.map((row) => row.product_title))]
  const held = cell.contents.reduce((sum, row) => sum + row.qty, 0)
  const others = models.length - 1
  return {
    text: `${models[0]}${others ? ` va yana ${others} xil` : ""} · ${held} dona`,
    odd: others > 0,
  }
}

/** How much more this cell was meant to take, said in words. */
function roomWord(free: number | null | undefined): string {
  if (free === null || free === undefined) return "hajmi yozilmagan"
  if (free <= 0) return "joy qolmagan"
  return `yana ${free} sig'adi`
}

/**
 * One cell the sack is going into.
 *
 * What it holds now, how much room is left in it, and how much of this pile
 * goes here. The quantity is a box only when there is something to divide: a
 * single cell takes the whole pile and says so, because the number is already
 * on the screen twice and typing it a third time is a third chance to be
 * wrong.
 */
function SpotRow({
  spot,
  room,
  mine,
  alone,
  onQty,
  onDrop,
}: {
  spot: Spot
  room: Location | undefined
  /** How many pieces land here. */
  mine: number
  alone: boolean
  onQty: (qty: string) => void
  onDrop: () => void
}) {
  const detail = useLocation(spot.code)
  const held = inside(detail.data)
  // Capacity is never enforced — a cell that turns away the last pair at nine
  // in the evening is a cell somebody works around. So this is a sentence, not
  // a stop.
  const free = room?.free ?? null
  const spill = free !== null ? mine - free : 0

  return (
    <li className="flex items-start gap-2 p-2">
      <span
        className={cn(
          "mt-0.5 grid size-8 shrink-0 place-items-center rounded-control",
          spill > 0 ? "bg-warn-soft text-warn-ink" : "bg-brand-soft text-brand-deep",
        )}>
        <MapPin className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate tabular text-body font-semibold">{spot.code}</span>
        {/* The title is the part allowed to give way. On a phone one plain
            line ended at "Erkaklar futbolkasi …" and swallowed the half that
            decides the split — how much room is left in the cell. */}
        <span className="flex items-baseline gap-1 text-micro">
          <span className={cn("truncate", held.odd ? "text-warn-ink" : "text-ink-faint")}>
            {held.text || "…"}
          </span>
          <span className="shrink-0 text-ink-faint">· {roomWord(free)}</span>
        </span>
        {spill > 0 ? (
          <span className="mt-1 flex items-center gap-1 text-micro font-medium text-warn-ink">
            <AlertTriangle className="size-3 shrink-0" />
            {spill} dona sig'may qoladi — baribir shu yerga
          </span>
        ) : null}
      </span>
      {alone ? (
        <span className="shrink-0 self-center tabular text-body font-semibold">
          {mine} dona
        </span>
      ) : (
        <span className="flex shrink-0 items-center gap-1 self-center">
          <Input
            value={spot.qty}
            onChange={(event) => onQty(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            aria-label={`${spot.code} ga nechta`}
            className={cn(
              "h-control-lg w-16 shrink-0 px-1 text-center tabular text-body",
              mine > 0 && "border-brand",
            )}
          />
          <span className="hidden text-small text-ink-soft sm:inline">dona</span>
        </span>
      )}
      <button
        type="button"
        onClick={onDrop}
        aria-label={`${spot.code} — ro'yxatdan olib tashlash`}
        className="h-control w-9 shrink-0 self-center rounded-control text-small text-ink-faint hover:bg-line-soft hover:text-danger">
        ✕
      </button>
    </li>
  )
}

/**
 * Where these N pieces would go if nobody thought about it.
 *
 * Offered, not applied. The plan knows two things the person on the bench does
 * not — which cells already hold this model, and how much room each has left —
 * and until now they were guessing at both. But goods landing in a cell nobody
 * looked at is how a shelf stops matching the screen, so it is still a tap.
 */
function PlanOffer({
  lines,
  message,
  overCapacity,
  onTake,
}: {
  lines: { code: string; quantity: number; free: number | null; holds_this_model: boolean }[]
  message: string
  overCapacity: boolean
  onTake: () => void
}) {
  const one = lines.length === 1
  return (
    <button
      type="button"
      onClick={onTake}
      className={cn(
        "group block w-full rounded-control border border-brand bg-brand-soft p-2.5 text-left transition-colors hover:bg-brand hover:text-brand-ink",
        one && "sm:w-80",
      )}>
      <span className="flex items-center gap-3">
        <MapPin className="size-4 shrink-0" />
        <span className="min-w-0 flex-1">
          <span className="block tabular text-body font-semibold">
            {one ? lines[0].code : `${lines.length} ta yacheykaga bo'linadi`}
          </span>
          <span className="block text-micro opacity-80">
            {one
              ? lines[0].holds_this_model
                ? "shu model shu yerda turibdi"
                : "eng bo'sh yacheyka, shu yerga"
              : "shu model turgan yacheykalardan boshlab"}
          </span>
        </span>
        <ArrowRight className="size-4 shrink-0 transition-transform group-hover:translate-x-0.5" />
      </span>

      {one ? null : (
        <span className="mt-2 block space-y-1">
          {lines.map((line) => (
            <span key={line.code} className="flex items-baseline gap-2">
              <span className="tabular text-small font-semibold">{line.code}</span>
              <span className="min-w-0 flex-1 truncate text-micro opacity-80">
                {line.holds_this_model ? "shu model" : "bo'sh"} · {roomWord(line.free)}
              </span>
              <span className="shrink-0 tabular text-small font-semibold">
                {line.quantity} dona
              </span>
            </span>
          ))}
        </span>
      )}

      {overCapacity && message ? (
        <span className="mt-2 flex items-start gap-1 text-micro font-medium">
          <AlertTriangle className="mt-0.5 size-3 shrink-0" />
          {message}
        </span>
      ) : null}
    </button>
  )
}

function Cells({
  spots,
  total,
  productId,
  onSet,
}: {
  spots: Spot[]
  total: number
  productId: number | null
  onSet: (next: Spot[]) => void
}) {
  const map = useShelfMap()
  // Where the pile would go if nobody thought about it: the model's own cells
  // first, each to its free room, then the emptiest nearest them. It replaces
  // the old one-code suggestion, which happily named a cell with room for four
  // more pairs and left the other forty to the eye.
  const plan = usePutawayPlan(productId, total)

  const rooms = useMemo(() => {
    const byCode = new Map<string, Location>()
    for (const cell of map.data?.cells ?? []) byCode.set(cell.code, cell)
    return byCode
  }, [map.data])

  const racks = useMemo(() => {
    const byRack = new Map<string, Location[]>()
    for (const cell of map.data?.cells ?? []) {
      const key = cell.rack ?? "?"
      byRack.set(key, [...(byRack.get(key) ?? []), cell])
    }
    return [...byRack.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [map.data])

  const chosen = useMemo(() => new Set(spots.map((spot) => spot.code)), [spots])
  const planned = useMemo(
    () => new Set((plan.data?.lines ?? []).map((line) => line.code)),
    [plan.data],
  )
  const spread = placed(spots, total)

  /**
   * A tap on the grid: the cell joins the destination, or leaves it.
   *
   * The second cell is where the arithmetic starts, and the screen does it:
   * the first cell keeps what it has room for and the new one takes the rest,
   * which is what happens with your hands. Every box stays editable.
   */
  function tap(code: string) {
    if (chosen.has(code)) {
      const left = spots.filter((spot) => spot.code !== code)
      onSet(left)
      return
    }
    if (!spots.length) {
      onSet([{ code, qty: String(total) }])
      return
    }
    if (spots.length === 1) {
      // As much as the first cell has room for, and the rest next door. When
      // the room is not stated, or is enough for the lot and somebody is
      // dividing it anyway, half is a starting point rather than a claim —
      // handing the new cell a nought would mean editing two boxes to say
      // anything at all.
      const free = rooms.get(spots[0].code)?.free ?? null
      const keep =
        free !== null && free > 0 && free < total ? free : Math.ceil(total / 2)
      onSet([
        { code: spots[0].code, qty: String(keep) },
        { code, qty: String(total - keep) },
      ])
      return
    }
    onSet([...spots, { code, qty: String(Math.max(0, total - spread)) }])
  }

  /** The difference, into the last cell. One tap out of any mismatch. */
  function balance() {
    if (spots.length < 2) return
    const others = spots
      .slice(0, -1)
      .reduce((sum, spot) => sum + (Number(spot.qty) || 0), 0)
    onSet(
      spots.map((spot, index) =>
        index === spots.length - 1
          ? { ...spot, qty: String(Math.max(0, total - others)) }
          : spot,
      ),
    )
  }

  const over = spread - total
  const last = spots[spots.length - 1]

  return (
    <Panel
      title="Qaysi yacheykaga?"
      aside={
        spots.length ? (
          <span
            className={cn(
              "rounded-full px-2.5 py-1 text-micro font-semibold tabular",
              over === 0 ? "bg-good-soft text-good" : "bg-danger-soft text-danger",
            )}>
            {spread} / {total} dona
          </span>
        ) : null
      }
    >
      <div className="space-y-3">
      {/* The plan, offered before it is asked for, and only while nothing has
          been chosen: once somebody has tapped a cell the destination is
          theirs, and a machine still arguing for its own answer underneath is
          a thing to read past. */}
      {!spots.length && plan.data?.lines.length ? (
        <PlanOffer
          lines={plan.data.lines}
          message={plan.data.message}
          overCapacity={plan.data.over_capacity}
          onTake={() =>
            onSet(
              plan.data.lines.map((line) => ({
                code: line.code,
                qty: String(line.quantity),
              })),
            )
          }
        />
      ) : null}

      {map.isLoading ? <Waiting what="Javonlar" /> : null}

      {spots.length ? (
        <div className="space-y-2">
          <ul className="divide-y rounded-control border">
            {spots.map((spot, index) => (
              <SpotRow
                key={spot.code}
                spot={spot}
                room={rooms.get(spot.code)}
                mine={takes(spots, index, total)}
                alone={spots.length === 1}
                onQty={(qty) =>
                  onSet(spots.map((one, at) => (at === index ? { ...one, qty } : one)))
                }
                onDrop={() => onSet(spots.filter((_, at) => at !== index))}
              />
            ))}
          </ul>

          {/* An unfinished split says so where the split is, not only on the
              bar — and says it with the way out beside it. */}
          {over !== 0 && last ? (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-control bg-danger-soft p-2">
              <p className="text-micro font-medium text-danger">
                {over < 0
                  ? `Yana ${-over} dona joylanmadi`
                  : `${over} dona ortiqcha bo'lindi`}
              </p>
              <button
                type="button"
                onClick={balance}
                className="h-control rounded-control border border-danger px-3 text-small font-medium text-danger">
                {over < 0
                  ? `${-over} donani ${last.code} ga`
                  : `${over} donani ${last.code} dan`}
              </button>
            </div>
          ) : null}

          <p className="text-micro text-ink-faint">
            Yana yacheyka kerak bo'lsa — quyidan tanlang.
          </p>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3">
        {racks.map(([rack, cells]) => {
          const columns = Math.max(...cells.map((cell) => cell.column_no ?? 1))
          const rows = Math.max(...cells.map((cell) => cell.row_no ?? 1))
          return (
            <div key={rack}>
              <div className="mb-1 text-micro text-ink-soft">{rack} javoni</div>
              {/* The column numbers along the top and the row numbers down the
                  side, the way a shelf is labelled — the codes on the cells
                  alone left somebody counting across to work out where
                  "A-03-02" actually is. */}
              <div
                className="grid gap-1"
                style={{
                  gridTemplateColumns: `1.1rem repeat(${columns}, minmax(0, 1fr))`,
                }}
              >
                <span />
                {Array.from({ length: columns }, (_, index) => index + 1).map((column) => (
                  <span
                    key={`head-${rack}-${column}`}
                    className="pb-0.5 text-center text-micro tabular text-ink-faint">
                    {column}
                  </span>
                ))}
                {/* Bottom row at the bottom, the way a person reads a shelf. */}
                {Array.from({ length: rows }, (_, index) => rows - index).flatMap((row) => [
                  <span
                    key={`row-${rack}-${row}`}
                    className="self-center text-center text-micro tabular text-ink-faint">
                    {row}
                  </span>,
                  ...Array.from({ length: columns }, (_, index) => index + 1).map((column) => {
                    const cell = cells.find(
                      (one) => one.row_no === row && one.column_no === column,
                    )
                    if (!cell) return <span key={`${rack}-${row}-${column}`} />
                    const at = spots.findIndex((spot) => spot.code === cell.code)
                    const picked = at >= 0
                    // Only while the offer is still standing. Once somebody has
                    // chosen, three other squares glowing with a plan nobody
                    // took are three squares to read past.
                    const suggests = !spots.length && planned.has(cell.code)
                    const empty = cell.units === 0
                    return (
                      <button
                        key={cell.code}
                        type="button"
                        onClick={() => tap(cell.code)}
                        title={`${cell.code} · ${cell.units} dona · ${roomWord(cell.free)}`}
                        className={cn(
                          "rounded-control border py-1.5 text-center text-micro tabular transition",
                          picked && "border-brand bg-brand font-semibold text-brand-ink",
                          suggests && "border-brand bg-brand-soft text-brand-deep",
                          !picked && !suggests && empty
                            && "border-dashed border-line text-ink-faint/70 hover:border-brand hover:text-ink",
                          !picked && !suggests && !empty
                            && "border-line bg-canvas hover:border-brand",
                        )}
                      >
                        <span className="block font-medium">{cell.code.slice(2)}</span>
                        {/* A chosen cell says what is going into it, a cell
                            with goods says how many are in it, and an empty
                            one says nothing at all — forty-two squares each
                            printing "bo'sh" is forty-two words to read past to
                            find the six that matter. */}
                        <span className="block opacity-70">
                          {picked
                            ? `+${takes(spots, at, total)}`
                            : empty
                              ? " "
                              : cell.units}
                        </span>
                      </button>
                    )
                  }),
                ])}
              </div>
            </div>
          )
        })}
      </div>
      </div>
    </Panel>
  )
}

// -------------------------------------------------------------- and it is in

function Booked({
  pile,
  onAnotherColour,
  onDone,
}: {
  pile: BookedPile
  onAnotherColour: () => void
  onDone: () => void
}) {
  // Where the goods actually are. A split used to be two bookings and two of
  // these panels; now it is one, and the one thing the person needs off it is
  // which cells to walk to and with how much.
  const spread = pile.placements ?? []
  return (
    <div className="space-y-3 rounded-panel border border-good bg-good-soft p-3">
      <div className="flex items-start gap-2">
        <Check className="mt-0.5 size-5 shrink-0 text-good" />
        <div className="min-w-0">
          <div className="text-body font-semibold">{pile.product.title}</div>
          <div className="text-small text-ink-soft">
            {units(pile.quantity)}
            {spread.length > 1 ? ` · ${spread.length} ta yacheyka` : ""} ·{" "}
            {money(pile.total_cost)}
          </div>
        </div>
      </div>

      <div className="rounded-control bg-surface p-2">
        <p className="mb-1 text-micro text-ink-soft">Qayerga qo'yildi</p>
        <ul className="space-y-1">
          {(spread.length
            ? spread
            : [{ code: pile.location_code, quantity: pile.quantity }]
          ).map((spot) => (
            <li key={spot.code} className="flex items-baseline justify-between gap-2">
              <span className="flex min-w-0 items-center gap-1.5">
                <MapPin className="size-3.5 shrink-0 text-good" />
                <span className="truncate tabular text-body font-semibold">{spot.code}</span>
              </span>
              <span className="shrink-0 tabular text-small text-ink-soft">
                {spot.quantity} dona
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* No printer yet, so the codes are big enough to copy onto the box with
          a marker. A print button is additive when hardware arrives, and none
          of these codes change when it does. */}
      <div className="rounded-control bg-surface p-2">
        <p className="mb-1 text-micro text-ink-soft">Qutiga yozib qo'ying</p>
        <ul className="space-y-1">
          {pile.labels.map((one) => (
            <li key={one.variant_id} className="flex items-baseline justify-between gap-2">
              <span className="text-small text-ink-soft">{one.variant_label || "—"}</span>
              <span className="tabular text-body font-semibold">{one.sku}</span>
            </li>
          ))}
        </ul>
      </div>

      {pile.product.unready.length ? (
        <p className="text-micro text-ink-soft">
          3-qadam qoldi — kerak: {pile.product.unready.map((gap) => gap.label).join(", ")}.{" "}
          <a href="/sotuvga-chiqarish" className="font-medium text-brand-deep underline">
            Telefonga chiqarish
          </a>
        </p>
      ) : (
        <p className="text-micro text-good">Do'konda ham bor — sotuvda turibdi.</p>
      )}

      {/* One way on. A sack used to have two ways of not being finished —
          another colour, or a colour that did not fit one cell — and the
          second one, "Qolganini boshqa yacheykaga", cleared every count to do
          it: the pile was counted twice to be shelved twice. Not fitting one
          cell is now answered before the button, where it belongs. */}
      <div className="flex gap-2">
        <Button size="lg" className="flex-1 gap-2" onClick={onAnotherColour}>
          <Plus className="size-5" />
          Shu qopdan yana bir rang
        </Button>
        <Button size="lg" variant="ghost" onClick={onDone}>
          Tugadi
        </Button>
      </div>
    </div>
  )
}

// ------------------------------------------------------ sacks nobody has opened

/**
 * The reminder, and it is only a reminder.
 *
 * Its whole value is the age: goods are standing in the building and nobody
 * knows what they are. Tipping one out produces piles, which go in above — a
 * sack is not one pile, so there is no arrangement of lines on this row that
 * would describe what came out of it. "Saralandi" dismisses it.
 */
function Sacks() {
  const drafts = useSupplies("draft")
  const start = useStartRun()
  const [open, setOpen] = useState(false)
  const [sacks, setSacks] = useState("1")
  const [place, setPlace] = useState("")
  const [fare, setFare] = useState("")

  const waiting = drafts.data?.length ?? 0

  return (
    <Panel>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-baseline justify-between">
        <span className="text-small font-semibold">Ochilmagan qoplar</span>
        <span className={cn("text-small tabular", waiting && "font-semibold text-warn-ink")}>
          {waiting || "yo'q"}
        </span>
      </button>

      {open ? (
        <div className="mt-3 space-y-3">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              start.mutate(
                {
                  sacks: Number(sacks) || 1,
                  place: place.trim(),
                  // Was hard-coded nought, so the column existed and was
                  // never anything but zero. The server puts the whole fare
                  // on the first sack rather than dividing it by five.
                  transport_cost: Number(fare) || 0,
                },
                {
                  onSuccess: () => {
                    setSacks("1")
                    setFare("")
                  },
                },
              )
            }}
          >
            <label className="w-24">
              <span className="mb-1 block text-micro text-ink-soft">Nechta qop</span>
              <Input
                value={sacks}
                onChange={(event) => setSacks(event.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                aria-label="Nechta qop"
                className="h-control tabular" />
            </label>
            <label className="min-w-32 flex-1">
              <span className="mb-1 block text-micro text-ink-soft">Qayerdan</span>
              <Input
                value={place}
                onChange={(event) => setPlace(event.target.value)}
                placeholder="Chorsu"
                aria-label="Qop qayerdan"
                className="h-control" />
            </label>
            <label className="w-28">
              <span className="mb-1 block text-micro text-ink-soft">Yo'l puli</span>
              <Input
                value={fare ? groups(Number(fare)) : ""}
                onChange={(event) => setFare(event.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                placeholder="30 000"
                aria-label="Yo'l puli — butun qatnov uchun"
                className="h-control tabular" />
            </label>
            <Button type="submit" variant="secondary">
              Keldi
            </Button>
            <p className="w-full text-micro text-ink-faint">
              Yo'l puli butun qatnov uchun bir marta yoziladi — qop soniga
              bo'linmaydi.
            </p>
          </form>

          {waiting === 0 ? <Empty bare what="Hamma qop saralangan." /> : null}

          <ul className="space-y-2">
            {(drafts.data ?? []).map((sack) => (
              <Sack key={sack.id} sack={sack} />
            ))}
          </ul>
        </div>
      ) : null}
    </Panel>
  )
}

/**
 * One sack, and the two different things that can be true of it.
 *
 * "Saralandi" asserts something: the goods went in, as piles, above. There was
 * no way to say the other thing — **that this sack was never goods**: a
 * miscount at the door, a sack that went straight back to the market. The
 * ledger distinguishes them and the row did not, so the only way to clear the
 * dashboard's red tile was to claim goods had been booked in that never were.
 *
 * Quieter than "Saralandi" because it is the rarer of the two, and it asks for
 * a reason before it will go: a sack that disappeared with nothing written
 * against it is indistinguishable from one nobody bothered to sort.
 */
function Sack({
  sack,
}: {
  sack: { id: number; code: string; place: string; age_minutes: number }
}) {
  const sorted = useSackSorted(sack.id)
  const cancel = useCancelSupply(sack.id)
  const [asked, setAsked] = useState(false)
  const [reason, setReason] = useState("")
  const overnight = sack.age_minutes >= OVERNIGHT_MINUTES
  const said = reason.trim()

  return (
    <li
      className={cn(
        "rounded-control border p-2",
        overnight && "border-danger bg-danger-soft",
      )}
    >
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate text-small font-medium">
            {sack.code} · {sack.place || "joyi yozilmagan"}
          </div>
          <div className={cn("text-micro tabular", overnight ? "text-danger" : "text-ink-faint")}>
            {age(sack.age_minutes)} turgan
          </div>
        </div>
        <Button variant="ghost" size="sm" disabled={sorted.isPending} onClick={() => sorted.mutate()}
        >
          {sorted.isPending ? <Loader2 className="size-4 animate-spin" /> : <X className="size-4" />}
          Saralandi
        </Button>
        <button
          type="button"
          onClick={() => setAsked((was) => !was)}
          className={cn(
            "shrink-0 px-1 text-micro text-ink-faint hover:text-danger",
            asked && "font-medium text-danger",
          )}>
          Bekor
        </button>
      </div>

      {asked ? (
        <div className="mt-2 space-y-2 border-t pt-2">
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-40 flex-1">
              <span className="mb-1 block text-micro text-ink-soft">
                Nega bekor qilinyapti
              </span>
              <Input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Eshikda noto'g'ri sanalgan"
                aria-label="Bekor qilish sababi"
                className="h-control" />
            </label>
            <Button
              variant="danger"
              size="sm"
              disabled={!said || cancel.isPending}
              onClick={() => cancel.mutate(said)}
            >
              {cancel.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                "Ha, bekor"
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAsked(false)}>
              Yo'q
            </Button>
          </div>
          {/* The two sentences side by side, because the difference between
              them is the whole reason this button exists. */}
          <p className="text-micro text-ink-faint">
            «Saralandi» — qopdagi tavar javonga yozildi. «Bekor» — bu qop tavar
            bo'lmagan: kirimga yozilmaydi.
          </p>
          <Problem error={cancel.error} />
        </div>
      ) : null}
    </li>
  )
}
