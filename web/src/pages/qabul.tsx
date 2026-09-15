/**
 * Qabul — one screen, two moments, in the order the body moves.
 *
 * The owner described the motion: enter → **paper** → stick → carry → put
 * away. The screen before this one asked for the cell at the table, which is
 * asking somebody who has not walked anywhere yet where they are going to end
 * up — they guess, and a guess in the cell field is stock in the wrong place.
 *
 *   Moment 1 · stolda        what came, how many, what it cost → Qabul →
 *                            the stickers print, one per unit
 *   Moment 2 · javon oldida  the one question left — which cell — answered
 *                            by scanning the cell's own label, or typed
 *
 * The screen does not clear between them: after **Qabul** it becomes
 * "N dona · yorliqlangan · javonga qo'yilmagan — Qaysi yacheyka?". Nothing is
 * lost while that question waits — QABUL is a real, sellable place — and the
 * queue of unanswered receipts survives a reload, listed below with its age.
 *
 * One receipt is one colour. White shoes and black shoes are two receipts,
 * one after the other — the second keeps the card, the kind, the brand and
 * the cost, so only the colour and the sizes are retyped.
 *
 * A scanner is always listening (a gun on the bench, the phone camera at the
 * shelf): a goods sticker fills the card in, a cell label finishes moment
 * two in one scan.
 *
 * **Where the card form sits in this** (§5.4, §7.8). "Nima keldi?" has two
 * answers and they are not the same shape. A card the shop already has is
 * *found* — typed, scanned, or narrowed with the learned Tur/Brend chips —
 * and that is the fast path the bench uses all day. A card the shop has never
 * had is *written*, and writing one is the card form's job, not this screen's:
 * **Yangi tavar** opens `<CardForm mode="receiving">`, which asks the category
 * first because it decides everything under it, then the name.
 *
 * The boundary is drawn there, at the card's identity. Everything the *receipt*
 * knows and the card does not — which of its colours came, how many of each
 * size, what one cost, where it was bought — stays here, because those are
 * facts about this morning rather than about the goods. What changed is that
 * the colour is no longer a word typed at the bench: it is picked from §5.3's
 * palette, with its swatch, and the sizes are offered by the run of sizes the
 * card is numbered in.
 */

import {
  ArrowRight,
  Check,
  Loader2,
  MapPin,
  Package,
  Plus,
  Printer,
  Search,
  Sparkles,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { CardForm } from "@/components/card-form"
import { Swatch } from "@/components/card-form/bits"
import { LabelRoll } from "@/components/label-roll"
import { PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { mediaUrl } from "@/components/photo-step"
import { ScanTarget, type ScanAnswer } from "@/components/scan"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, bySize, groups, money, tidySize, units } from "@/lib/format"
import {
  useAddColour,
  useColours,
  useProduct,
  useProducts,
  useProductSizeSystem,
  usePutawayPlan,
  useReceive,
  useRunLabels,
  useSetProductSizeSystem,
  useShelveReceipt,
  useSizeSystems,
  useSupplies,
  useVariants,
  useVocab,
  useWaitingReceipts,
  type Receipt,
  type ReceiptShelved,
  type WaitingReceipt,
} from "@/lib/queries"
import type { AdminProduct, SizeSystem } from "@/lib/types"

// A receipt that has stood this long is the thing this shop actually loses
// money on: goods in the building that the shelf map has not heard of.
const OVERNIGHT_MINUTES = 14 * 60

/** One size and how many of it came. An array, not a map: the order these
 *  were typed is the order the stickers print in and the order the piles sit
 *  on the table, and numeric object keys would be re-sorted by the runtime. */
type SizeLine = { size: string; qty: string }

type Draft = {
  /** The card. Always a real one by the time anything else is asked: found,
   *  scanned, or just written by the card form. */
  product: AdminProduct | null
  kind: string
  /** One colour — the whole receipt's. A second colour is a second receipt. */
  colour: string
  /** The palette's own hex for that colour, carried onto the variant so the
   *  swatch on the card is the one somebody pointed at. */
  colourHex: string
  lines: SizeLine[]
  unitCost: string
  place: string
  /** What the van cost — the whole trip's. Sent once, not per colour. */
  fare: string
}

const EMPTY: Draft = {
  product: null,
  kind: "",
  colour: "",
  colourHex: "",
  lines: [],
  unitCost: "",
  place: "",
  fare: "",
}

/** The receipt whose second moment is on screen. `receipt` is present when it
 *  was booked this minute — it carries the stickers and the full card; a row
 *  reopened from the queue has only what the queue knows. */
type Open = {
  id: number
  code: string
  quantity: number
  product_id: number | null
  product_title: string
  receipt: Receipt | null
}

/** The lines with a count on them, in typed order, as the server takes them. */
function linesOut(lines: SizeLine[]): { size: string; quantity: number }[] {
  return lines
    .map((line) => ({ size: line.size, quantity: Number(line.qty) || 0 }))
    .filter((line) => line.quantity > 0)
}

function countOf(lines: SizeLine[]): number {
  return linesOut(lines).reduce((sum, line) => sum + line.quantity, 0)
}

export function QabulPage() {
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [open, setOpen] = useState<Open | null>(null)
  const [done, setDone] = useState<{ answer: ReceiptShelved; from: Open } | null>(null)
  // What the last scan could not be used for, said beside the scan target —
  // a scan that silently does nothing reads as a broken scanner.
  const [scanSaid, setScanSaid] = useState("")
  // A card named by its id rather than held in the hand: a scanned goods
  // sticker, or a card the form has just written. Both arrive as an id and
  // both want the whole card on the draft, so they share one door.
  const [fillFrom, setFillFrom] = useState<{ id: number; colour: string } | null>(null)

  const receive = useReceive()
  const shelve = useShelveReceipt()
  const named = useProduct(fillFrom?.id ?? null)

  useEffect(() => {
    if (!fillFrom || !named.data || named.data.id !== fillFrom.id) return
    const card = named.data
    setDraft((was) => ({
      ...was,
      product: card,
      kind: card.kind,
      // The sticker knows its colour; presetting it saves a tap and stays
      // editable — more of the white may really be more of the black. A card
      // written this minute knows none, and the palette asks for it.
      colour: fillFrom.colour,
      colourHex: "",
    }))
    setFillFrom(null)
    setDone(null)
  }, [fillFrom, named.data])

  function restart() {
    setDraft(EMPTY)
    setOpen(null)
    setDone(null)
    setScanSaid("")
  }

  /** The second colour of the same goods: the card, the kind, the brand and
   *  the cost stay; only the colour and the sizes are retyped. The fare is
   *  already on the run that was just booked — carrying it over would charge
   *  the same taxi twice. */
  function anotherColour(receipt: Receipt) {
    setOpen(null)
    setDone(null)
    setScanSaid("")
    setDraft((was) => ({
      ...EMPTY,
      product: receipt.product,
      kind: receipt.product.kind,
      unitCost: was.unitCost,
      place: was.place,
    }))
  }

  function putAway(at: Open, code: string) {
    if (shelve.isPending) return
    shelve.mutate(
      { id: at.id, location_code: code.trim().toUpperCase() },
      {
        onSuccess: (answer) => {
          setDone({ answer, from: at })
          setOpen(null)
          setScanSaid("")
        },
      },
    )
  }

  /** One router for whatever was scanned. The component already asked the
   *  server what the code is; this decides what the moment does with it. */
  function onScan(answer: ScanAnswer) {
    setScanSaid("")
    if (answer.kind === "cell" && answer.cell) {
      if (!open) {
        setScanSaid(
          `${answer.cell.code} — yacheyka. Avval qabulni yozing yoki quyidagi navbatdan oching.`,
        )
        return
      }
      // A retired cell is refused loudly, before the request: the server
      // would 409 it anyway, but "scanned and nothing happened" at the shelf
      // reads as a broken scanner, not as a closed cell.
      if (answer.cell.is_active === false) {
        setScanSaid(
          `${answer.cell.code} yopilgan yacheyka — tavar QABULda qoladi. Boshqasini skanerlang.`,
        )
        return
      }
      putAway(open, answer.cell.code)
      return
    }
    if (answer.kind === "variant" && answer.variant) {
      if (open) {
        setScanSaid(
          `${answer.variant.product_title} — avval ochiq qabulni javonga qo'ying yoki «Keyinroq» deng.`,
        )
        return
      }
      setFillFrom({ id: answer.variant.product_id, colour: answer.variant.colour })
      return
    }
    setScanSaid(`«${answer.code}» hech narsaga to'g'ri kelmadi — nomini yozib qidiring.`)
  }

  const busy = receive.isPending || shelve.isPending

  return (
    <div className="space-y-4">
      <PageHeader title="Qabul" subtitle="Stolda yoziladi — yacheyka javon oldida" />

      {/* The scanner, always listening — on both moments, because the two
          things it answers are the two halves of this screen: a goods sticker
          fills the card, a cell label finishes the shelving. */}
      <Panel bare>
        <div className="flex flex-wrap items-center gap-3 p-3">
          <ScanTarget onAnswer={onScan} paused={busy} />
          <p className="min-w-0 flex-1 text-micro text-ink-faint">
            {open
              ? "Yacheyka yorlig'ini skanerlang — tavar o'sha zahoti joylashadi."
              : "Tavar yorlig'ini skanerlang — kartasi o'zi to'ladi."}
          </p>
        </div>
        {scanSaid ? (
          <p className="border-t border-line px-3 py-2 text-micro font-medium text-danger">
            {scanSaid}
          </p>
        ) : null}
      </Panel>

      {open ? (
        <MomentTwo
          open={open}
          pending={shelve.isPending}
          error={shelve.error}
          onPutAway={(code) => putAway(open, code)}
          onAnotherColour={open.receipt ? () => anotherColour(open.receipt!) : undefined}
          onLater={() => setOpen(null)}
        />
      ) : done ? (
        <Shelved
          done={done}
          onAnotherColour={
            done.from.receipt ? () => anotherColour(done.from.receipt!) : undefined
          }
          onNew={restart}
        />
      ) : (
        <MomentOne
          draft={draft}
          setDraft={setDraft}
          receive={receive}
          // The card form answers with an id; the draft wants the whole card,
          // which is the same fetch a scanned sticker needs.
          onCreated={(id) => setFillFrom({ id, colour: "" })}
          onBooked={(receipt) => {
            setDone(null)
            setOpen({
              id: receipt.run_id,
              code: receipt.run_code,
              quantity: receipt.quantity,
              product_id: receipt.product.id,
              product_title: receipt.product.title,
              receipt,
            })
            // The card the receipt wrote, back onto the draft: "yana bir
            // rang" for a brand-new card must land on this card, not open a
            // second one — the exact duplicate this screen warns about.
            setDraft((was) => ({ ...was, product: receipt.product }))
          }}
        />
      )}

      {/* The second moment's queue: receipts whose goods are labelled and
          still standing in QABUL. Each opens straight into its own moment
          two. Hidden while a receipt is open — one question at a time. */}
      {!open ? (
        <WaitingQueue
          onOpen={(row) => {
            setDone(null)
            setScanSaid("")
            setOpen({
              id: row.id,
              code: row.code,
              quantity: row.quantity,
              product_id: row.product_id,
              product_title: row.product_title,
              receipt: null,
            })
          }}
        />
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------ moment 1 · stolda

/** Said under the running total while the bar's button is dead. */
const MISSING_HINT = {
  colour: "rangini tanlang",
  count: "nechta kelganini yozing",
  cost: "tannarx yozilmagan",
}

function MomentOne({
  draft,
  setDraft,
  receive,
  onCreated,
  onBooked,
}: {
  draft: Draft
  setDraft: (next: (was: Draft) => Draft) => void
  receive: ReturnType<typeof useReceive>
  onCreated: (productId: number) => void
  onBooked: (receipt: Receipt) => void
}) {
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((was) => ({ ...was, [key]: value }))

  // The colours this card already comes in. An existing card with colours
  // refuses a colourless receipt on the server — the count would land on a
  // variant no picker is ever sent to — so the form refuses it first.
  const grid = useVariants(draft.product?.id ?? null)
  const own = useMemo(
    () => [...new Set((grid.data ?? []).map((cell) => cell.colour))].filter(Boolean),
    [grid.data],
  )
  // Only a card whose variants are *deliberately* colourless is let through
  // without one — everything else, a new card included, picks from the
  // palette. A colour typed at the bench is how `qora`, `Qora` and `QORA`
  // became three colours, and the palette only stops that if it is the way in.
  const colourless = Boolean(grid.data && grid.data.length > 0 && own.length === 0)
  const needsColour = !colourless

  const total = countOf(draft.lines)
  const cost = Number(draft.unitCost) || 0
  const missing: keyof typeof MISSING_HINT | null =
    needsColour && !draft.colour.trim()
      ? "colour"
      : total === 0
        ? "count"
        : cost <= 0
          ? "cost"
          : null
  const ready = draft.product !== null && !missing && !receive.isPending
  const hint = missing ? MISSING_HINT[missing] : money(total * cost)

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!ready || !draft.product) return
    receive.mutate(
      {
        // Always a card that exists. The door still takes kind/brand and will
        // write a card from them, but §5.4 put that job in the card form —
        // two ways of writing a card is how two cards for one shoe happen.
        product_id: draft.product.id,
        colour: draft.colour.trim(),
        colour_hex: draft.colourHex,
        sizes: linesOut(draft.lines),
        unit_cost: cost,
        place: draft.place.trim(),
        transport_cost: Number(draft.fare) || 0,
      },
      { onSuccess: onBooked },
    )
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      {draft.product ? (
        <Named product={draft.product} onChange={() => setDraft(() => EMPTY)} />
      ) : (
        <IdentifyCard
          onPick={(product) =>
            setDraft((was) => ({ ...was, product, kind: product.kind }))
          }
          onCreated={onCreated}
        />
      )}

      {draft.product ? (
        <>
          <Counts
            product={draft.product}
            kind={draft.kind}
            colour={draft.colour}
            ownColours={own}
            needsColour={needsColour}
            lines={draft.lines}
            onColour={(colour, hex) =>
              setDraft((was) => ({ ...was, colour, colourHex: hex }))
            }
            onLines={(lines) => set("lines", lines)}
          />

          <Panel>
            <div className="grid gap-3 sm:grid-cols-2">
              <label>
                <span className="mb-1 block text-micro text-ink-soft">
                  Tannarx — bir dona
                </span>
                {/* Grouped as it is typed, and stored as digits. A cost is
                    six or seven figures here and `850000` on a screen is read
                    as `85 000` by somebody in a hurry — the one mistake on
                    this form nothing downstream can catch. */}
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
              {/* The trip, in one column: where it was bought and what the
                  van cost. The fare is per trip and the cost above is per
                  piece — not the same kind of number, so they do not sit
                  side by side as though they were. */}
              <div className="space-y-3">
                <Place value={draft.place} onSet={(place) => set("place", place)} />
                <label className="block">
                  <span className="mb-1 block text-micro text-ink-soft">
                    Yo'l puli
                  </span>
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
                    Butun qatnov uchun — ikkinchi rangga qayta yozilmaydi.
                  </span>
                </label>
              </div>
            </div>
          </Panel>
        </>
      ) : null}

      <Problem error={receive.error} />

      {/* The bar stays put: reaching the button must not mean scrolling past
          the whole form with goods in the other hand. No cell on it — the
          cell is the second moment's question, asked at the shelf. */}
      {/* `sticky`, not `fixed`. Fixed meant guessing where the rail ends —
          `md:left-60` was 240px against a 264px rail, so the bar sat under it
          — and on a phone it sat under the bottom navigation as well. Sticky
          inside the page is measured by the layout instead, and `--bottom-nav`
          is the one number that says how much of the foot the navigation has
          taken (zero on a desk). */}
      {draft.product ? (
        <div className="sticky bottom-(--bottom-nav) z-20 -mx-(--gap-page) border-y border-line bg-surface p-3 shadow-raised">
          <div className="mx-auto flex max-w-4xl items-center gap-3">
            <div className="min-w-0 flex-1">
              <div
                className={cn(
                  "truncate text-body font-semibold tabular",
                  total ? "text-ink" : "text-ink-soft",
                )}>
                {total ? units(total) : "Nechta keldi?"}
              </div>
              <div className="truncate text-micro tabular text-ink-faint">{hint}</div>
            </div>
            <Button size="lg" type="submit" disabled={!ready} className="gap-2">
              {receive.isPending ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Printer className="size-5" />
              )}
              Qabul
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  )
}

/**
 * Step one, answered, on one line. A tick, not a green panel: answering
 * "which goods" is the first field of a form, not a success.
 */
function Named({
  product,
  onChange,
}: {
  product: AdminProduct
  onChange: () => void
}) {
  return (
    <Panel>
      <div className="flex items-center gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-control bg-good-soft text-good">
          <Check className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-body font-semibold">{product.title}</div>
          <div className="truncate text-micro tabular text-ink-faint">
            {product.sku} · javonda {product.stock_left} dona
          </div>
        </div>
        <Button type="button" variant="secondary" size="sm" onClick={onChange}>
          O'zgartirish
        </Button>
      </div>
    </Panel>
  )
}

/**
 * Which card. One panel, two answers of different shapes.
 *
 * **Found** is the fast path and what the bench does all day: type a word,
 * scan a sticker already stuck on one of the shoes, or tap the learned
 * `Tur` / `Brend` chips, which narrow the same search rather than opening
 * anything — the server matches every word in any order against the title and
 * the code, so `Krossovka` + `Nike` finds `Krossovka · Nike · Qora`.
 *
 * **Written** is the card form (§5.4). It used to be two chip rows and a
 * photograph here, which wrote a card out of `kind` + `brand` + a colour typed
 * into a box — and the box is the whole reason the palette exists. So the
 * button opens `<CardForm mode="receiving">` instead: category first, then the
 * name. The moment the card exists the form hands back its id and the receipt
 * takes over with the colour, the sizes and the cost.
 */
function IdentifyCard({
  onPick,
  onCreated,
}: {
  onPick: (product: AdminProduct) => void
  onCreated: (productId: number) => void
}) {
  const [needle, setNeedle] = useState("")
  const [kind, setKind] = useState("")
  const [brand, setBrand] = useState("")
  const [writing, setWriting] = useState(false)
  const [made, setMade] = useState(false)
  const vocab = useVocab()
  // The typed words and the tapped chips are one search, not two.
  const asked = [needle, kind, brand]
    .map((word) => word.trim())
    .filter(Boolean)
    .join(" ")
  const found = useProducts(writing ? "" : asked, "")
  const results = asked && !writing ? (found.data?.items ?? []).slice(0, 8) : []

  return (
    <Panel title="Nima keldi?">
      <div className="space-y-3">
        {!writing ? (
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
              <Input
                autoFocus
                value={needle}
                onChange={(event) => setNeedle(event.target.value)}
                placeholder="nom yoki kod — yoki yorlig'ini skanerlang"
                aria-label="Mavjud kartani qidirish"
                className="h-control-lg pl-8 text-body" />
            </div>

            {/* The vocabulary the receipts have taught, as taps. Not a second
                way to write a card any more — a shorter way to find one. */}
            <Chips
              label="Tur"
              options={vocab.data?.kinds ?? []}
              value={kind}
              onChange={setKind} />
            <Chips
              label="Brend"
              options={vocab.data?.brands ?? []}
              value={brand}
              onChange={setBrand} />

            {asked && found.isLoading ? <Waiting what="Kartalar" /> : null}

            {results.length ? (
              <ul className="divide-y">
                {results.map((product) => (
                  <li key={product.id}>
                    <button
                      type="button"
                      onClick={() => onPick(product)}
                      className="flex w-full items-center gap-3 py-2 text-left">
                      <Thumb product={product} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-small font-medium">
                          {product.title}
                        </div>
                        <div className="text-micro tabular text-ink-faint">
                          {product.stock_left} dona · {product.sku}
                        </div>
                      </div>
                      <ArrowRight className="size-4 shrink-0 text-ink-faint" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}

            {asked && found.data?.items.length === 0 ? (
              <p className="text-small text-ink-soft">
                Bunday karta yo'q — quyidan yangi karta oching.
              </p>
            ) : null}

            <button
              type="button"
              onClick={() => setWriting(true)}
              className="group flex w-full items-center gap-3 rounded-control border border-dashed border-line p-3 text-left transition-colors hover:bg-line-soft">
              <span className="grid size-10 shrink-0 place-items-center rounded-control bg-brand-soft text-brand-deep">
                <Sparkles className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-body font-semibold">Yangi tavar</span>
                <span className="block text-micro text-ink-faint">
                  Birinchi marta keldi — kartasi shu yerda ochiladi
                </span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5" />
            </button>
          </>
        ) : (
          <>
            {/* The duplicate guard, kept, and now fed by the words the person
                typed into the search box before giving up on it. It asks
                rather than merges: a kind and a make are not identity — Nike
                sells more than one trainer. */}
            <Maybe kind={asked} onPick={onPick} />

            {/* §5.4's first entrance. `mode="receiving"` draws only what is
                knowable with the goods in your hands, and it is mounted here
                rather than in a modal so the screen stays one column down to
                the Qabul bar.

                Swapped for the wait the moment the card lands: the parent is
                fetching it to put on the draft, and the form's next section
                flashing up in that half-second reads as the screen changing
                its mind about what it is asking. */}
            {made ? (
              <Waiting what="Karta" />
            ) : (
              <CardForm
                mode="receiving"
                onCreated={(id) => {
                  setMade(true)
                  onCreated(id)
                }}
              />
            )}

            <button
              type="button"
              onClick={() => setWriting(false)}
              className="text-micro text-ink-faint hover:text-ink">
              ← Bor kartani qidirish
            </button>
          </>
        )}
      </div>
    </Panel>
  )
}

/**
 * "Was it not this one?" — asked before a second card for the same goods.
 * It asks rather than merges: kind and make are not identity — Nike sells
 * more than one trainer — and a wrong match costs a returned order where a
 * duplicate costs a merge.
 */
function Maybe({ kind, onPick }: { kind: string; onPick: (p: AdminProduct) => void }) {
  const found = useProducts(kind, "")
  const like = kind ? (found.data?.items ?? []).slice(0, 3) : []

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
}: {
  label: string
  options: string[]
  value: string
  onChange: (value: string) => void
}) {
  // Quiet filter pills, not a data entry row. These narrow the search above —
  // they stopped being a way to *write* a card when the card form took that
  // job — so the "+ yangi" free-text they used to carry was a second, blunter
  // search box drawn under the real one, and it is gone. The tint style is on
  // purpose too: a filled-brand pill next to the screen's one primary button
  // reads as a second primary.
  const shown = [
    ...(value && !options.includes(value) ? [value] : []),
    ...options.slice(0, 8),
  ]
  if (!shown.length) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-14 shrink-0 text-small text-ink-soft">{label}</span>
      {shown.map((one) => (
        <button
          key={one}
          type="button"
          onClick={() => onChange(one === value ? "" : one)}
          className={cn(
            "h-control-sm rounded-full bg-line-soft px-3 text-small transition-colors hover:bg-line",
            one === value && "bg-brand-soft font-medium text-brand-deep",
          )}
        >
          {one}
        </button>
      ))}
    </div>
  )
}

// --------------------------------------------------------------------- nechta

/**
 * One colour, and how many of each size of it came.
 *
 * The colour is asked here — beside the counts it belongs to — and there is
 * exactly one of it: a mixed bale is two receipts, one after the other, with
 * the card and the cost carried between them. The size→quantity table stays
 * in the order it is typed, because that is the order the stickers print in
 * and the order the piles sit on the table.
 *
 * **Neither answer is typed any more.** The colour comes off §5.3's palette,
 * with its swatch, and the sizes are offered by the run of sizes the card is
 * numbered in. Those are the two boxes that produced `qora` / `Qora` / `QORA`
 * and a European 43 sitting beside a UK 9 on one card.
 */
function Counts({
  product,
  kind,
  colour,
  ownColours,
  needsColour,
  lines,
  onColour,
  onLines,
}: {
  product: AdminProduct
  kind: string
  colour: string
  ownColours: string[]
  needsColour: boolean
  lines: SizeLine[]
  onColour: (colour: string, hex: string) => void
  onLines: (lines: SizeLine[]) => void
}) {
  const vocab = useVocab()
  const grid = useVariants(product.id)
  const sized = useProductSizeSystem(product.id)
  const [adding, setAdding] = useState("")
  const [typing, setTyping] = useState(false)

  // Some things have no size: a cap, a bag. The question is answered before
  // it is asked — and `chose` is a hand on the wheel: once somebody has said
  // which it is, nothing overrules them.
  //
  // The card's own answer is read in this order because the three sources
  // disagree about what "nothing" means. A named system is the card saying
  // *sized* outright (§6.3). Failing that, variants already on the card are
  // the only evidence that survives a reload. `size_system: null` alone is
  // **not** read as sizeless here: every card written before the systems
  // existed is null, and reading those as sizeless would drop the size column
  // off half the catalogue.
  const [chose, setChose] = useState<boolean | null>(null)
  const system = sized.data?.size_system ?? null
  const cardIsSizeless =
    (grid.data ?? []).length > 0 && (grid.data ?? []).every((cell) => !cell.size)
  const kindIsSizeless = (vocab.data?.sizeless ?? []).includes(kind)
  const sizeless =
    chose ??
    (system ? false : (grid.data ?? []).length > 0 ? cardIsSizeless : kindIsSizeless)

  // What a colour and size already holds, so a second count of the same size
  // reads as an addition rather than a figure about to be overwritten.
  const already = useMemo(() => {
    const map = new Map<string, number>()
    for (const cell of grid.data ?? []) {
      map.set(`${cell.colour} ${cell.size}`, cell.stock_left)
    }
    return map
  }, [grid.data])

  // A sized count left behind after the shape changed would be submitted
  // from behind the sizeless box, where nobody can see it.
  const stale = lines.some((line) => (sizeless ? line.size !== "" : line.size === ""))
  useEffect(() => {
    if (stale) onLines([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stale])

  /** Sizes worth offering: the run this card is numbered in, whatever it
   *  already carries in this colour, and what this kind last arrived in —
   *  minus the ones already on the table. */
  const suggested = useMemo(() => {
    const mine = (grid.data ?? [])
      .filter((cell) => !colour || cell.colour === colour)
      .map((cell) => cell.size)
    const seen = new Set(
      [
        ...(system?.values ?? []),
        ...mine,
        // Only when nothing is named: a card numbered in EUR must not be
        // offered the UK 9 the vocabulary learnt from a different card.
        ...(system ? [] : (vocab.data?.sizes[kind] ?? [])),
      ].map(tidySize),
    )
    seen.delete("")
    for (const line of lines) seen.delete(line.size)
    return [...seen].sort(bySize)
  }, [grid.data, vocab.data, kind, colour, lines, system])

  // One spelling, so `xl` typed in a hurry does not stand beside `XL` as a
  // second size, a second variant and a second barcode. Appended, never
  // sorted: typed order is print order.
  function add(size: string) {
    const wanted = tidySize(size)
    if (wanted && !lines.some((line) => line.size === wanted)) {
      onLines([...lines, { size: wanted, qty: "1" }])
    }
    setAdding("")
  }

  const write = (index: number, qty: string) =>
    onLines(lines.map((line, at) => (at === index ? { ...line, qty } : line)))

  const total = countOf(lines)

  return (
    <Panel title="Nechta keldi?">
      <div className="space-y-3">
        {needsColour ? (
          <ColourPick own={ownColours} value={colour} onPick={onColour} />
        ) : null}

        <SizeRun
          productId={product.id}
          system={system}
          sizeless={sizeless}
          waiting={sized.isLoading}
          mustChoose={
            chose === null &&
            !system &&
            !kindIsSizeless &&
            grid.data !== undefined &&
            grid.data.length === 0
          }
          onSystem={(slug) => {
            setChose(slug === null)
            onLines([])
          }}
        />

        {sizeless ? (
          <label className="flex items-center gap-2">
            <Input
              value={lines[0]?.qty ?? ""}
              onChange={(event) =>
                onLines([{ size: "", qty: event.target.value.replace(/\D/g, "") }])
              }
              inputMode="numeric"
              placeholder="12"
              aria-label="Nechta keldi"
              className="h-control-lg w-28 tabular text-body"
            />
            <span className="text-small text-ink-soft">dona keldi</span>
          </label>
        ) : (
          <>
            {lines.length ? (
              <ul className="divide-y rounded-control border">
                {lines.map((line, index) => (
                  <SizeRow
                    key={line.size}
                    size={line.size}
                    value={line.qty}
                    already={already.get(`${colour} ${line.size}`) ?? 0}
                    onChange={(qty) => write(index, qty)}
                    onDrop={() => onLines(lines.filter((_, at) => at !== index))}
                  />
                ))}
              </ul>
            ) : null}

            <div className="flex flex-wrap items-center gap-1">
              <span className="mr-1 text-micro text-ink-soft">
                {lines.length ? "Yana o'lcham:" : "Qanday o'lchamlar keldi?"}
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

        {total > 0 ? (
          <p className="text-small text-ink-soft">
            Jami <b className="tabular text-ink">{total}</b> dona — {total} ta yorliq
            chiqadi
          </p>
        ) : null}
      </div>
    </Panel>
  )
}

/**
 * The receipt's one colour, off the palette (§5.3).
 *
 * **One, not several.** The card may come in six colours; this morning's sack
 * is one of them, and white shoes and black shoes are two receipts with two
 * sheets of stickers. So this is a row of single-choice chips and never the
 * card form's tick-list — a ticked pair here would print one sheet of labels
 * for two sacks and put both counts on whichever colour was read first.
 *
 * The card's own colours come first and on their own: a card that has only
 * ever come in black is one tap, and the other thirty-one are behind
 * **Boshqa rang**. A card with none — one written a minute ago by the form —
 * gets the whole palette straight away, because there is nothing to shorten.
 */
function ColourPick({
  own,
  value,
  onPick,
}: {
  own: string[]
  value: string
  onPick: (colour: string, hex: string) => void
}) {
  const palette = useColours()
  const add = useAddColour()
  const [wide, setWide] = useState(false)
  const [query, setQuery] = useState("")
  const [adding, setAdding] = useState("")
  const [writing, setWriting] = useState(false)

  const rows = palette.data ?? []
  const hex = useMemo(() => new Map(rows.map((row) => [row.name, row.hex])), [rows])

  // A question with one answer is a tap for nothing: a card that only ever
  // came in black starts with black picked.
  const only = own.length === 1 ? own[0] : null
  useEffect(() => {
    if (only !== null && !value) onPick(only, hex.get(only) ?? "")
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only, hex])

  /** A colour the shop has not sold before, into the palette and onto this
   *  receipt in one act — the second half is the point: nobody adds a colour
   *  for its own sake, they add it because a sack of it is on the table. */
  function keep() {
    const wanted = adding.trim()
    if (!wanted || add.isPending) return
    add.mutate(
      { name: wanted },
      {
        onSuccess: (made) => {
          setAdding("")
          setWriting(false)
          setQuery("")
          onPick(made.name, made.hex)
        },
      },
    )
  }

  const showing = own.length > 0 && !wide
  const shown = useMemo(() => {
    const names = showing ? own : rows.map((row) => row.name)
    // A colour on the card that the palette has never heard of still needs a
    // chip, or a card written before the palette existed could not be received.
    const all = showing ? names : [...own.filter((one) => !hex.has(one)), ...names]
    const wanted = query.trim().toLowerCase()
    return wanted ? all.filter((one) => one.toLowerCase().includes(wanted)) : all
  }, [showing, own, rows, hex, query])

  return (
    <div>
      <span className="mb-1 block text-micro text-ink-soft">
        Rang — bitta qabul, bitta rang
      </span>

      {!showing && rows.length > 12 ? (
        <div className="relative mb-1">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Rang qidirish"
            aria-label="Rang qidirish"
            className="h-control pl-8" />
        </div>
      ) : null}

      <div className="flex flex-wrap gap-1">
        {shown.map((one) => (
          <button
            key={one}
            type="button"
            onClick={() => onPick(one === value ? "" : one, hex.get(one) ?? "")}
            className={cn(
              "flex h-control items-center gap-2 rounded-control border px-3 text-small",
              one === value && "border-brand bg-brand text-brand-ink",
            )}
          >
            <Swatch hex={hex.get(one)} />
            {one}
          </button>
        ))}

        {showing ? (
          <button
            type="button"
            onClick={() => setWide(true)}
            className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
            Boshqa rang
          </button>
        ) : null}

        {!showing && !writing ? (
          <button
            type="button"
            onClick={() => setWriting(true)}
            className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep">
            + yangi rang
          </button>
        ) : null}
      </div>

      {/* Added from here, not from a settings screen. Somebody at a bench with
          a sack of a colour the shop has never sold will not go and find the
          owner — they will type it into whatever box accepts it, which is how
          three spellings of one colour happened. The door is guarded
          `CatalogReader` for exactly this. */}
      {writing ? (
        <div className="mt-2 flex items-end gap-2">
          <label className="min-w-0 flex-1">
            <span className="mb-1 block text-micro text-ink-soft">Yangi rang nomi</span>
            <Input
              autoFocus
              value={adding}
              onChange={(event) => setAdding(event.target.value)}
              onKeyDown={(event) => {
                // Enter adds the colour and stops there — it must not reach
                // the receipt form and submit a half-written receipt.
                if (event.key !== "Enter") return
                event.preventDefault()
                keep()
              }}
              placeholder="Feruza"
              aria-label="Yangi rang nomi"
              className="h-control" />
          </label>
          <Button
            type="button"
            variant="secondary"
            className="gap-1"
            disabled={!adding.trim() || add.isPending}
            onClick={keep}
          >
            {add.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            Qo'shish
          </Button>
        </div>
      ) : null}

      <Problem error={palette.error || add.error} />
    </div>
  )
}

/**
 * Which run of sizes this card is numbered in — §5.3's size systems, at the
 * bench (§7.8).
 *
 * The systems arrive with `family` and `scale` apart, so *Erkaklar poyabzali*
 * is drawn once with EUR / UK / US / RUS under it rather than as four
 * unrelated strings that happen to share a prefix.
 *
 * **O'lchamsiz is one of the answers, not a separate switch.** §6.3 says a
 * card is sized or sizeless and never both, so saying so is the same act as
 * naming a system and writes `slug: null` deliberately. It was a segmented
 * control beside the panel title; two controls for one either/or is two places
 * to answer the same question.
 */
function SizeRun({
  productId,
  system,
  sizeless,
  waiting,
  mustChoose,
  onSystem,
}: {
  productId: number
  system: SizeSystem | null
  sizeless: boolean
  waiting: boolean
  /** A card with nothing to go on — written this minute, no variants, no
   *  learned habit. The run of sizes is the next thing it needs, so it is
   *  asked outright rather than hidden behind a word. */
  mustChoose: boolean
  onSystem: (slug: string | null) => void
}) {
  const systems = useSizeSystems()
  const write = useSetProductSizeSystem(productId)
  const [offering, setOffering] = useState(false)
  const showing = offering || mustChoose

  // Grouped in the server's order, which is the order the picker draws them.
  const families = useMemo(() => {
    const held = new Map<string, SizeSystem[]>()
    for (const one of systems.data ?? []) {
      const family = one.family || one.name
      held.set(family, [...(held.get(family) ?? []), one])
    }
    return [...held]
  }, [systems.data])

  function choose(slug: string | null) {
    setOffering(false)
    onSystem(slug)
    write.mutate(slug)
  }

  const said = system ? system.name : sizeless ? "O'lchamsiz" : "Tanlanmagan"

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-micro text-ink-soft">O'lcham tizimi</span>
        <span className="text-small font-medium">{waiting ? "…" : said}</span>
        {write.isPending ? (
          <Loader2 className="size-4 animate-spin text-ink-faint" />
        ) : null}
        {mustChoose ? (
          <span className="text-micro text-ink-faint">
            o'lchamlar shundan taklif qilinadi
          </span>
        ) : (
          <button
            type="button"
            onClick={() => setOffering((was) => !was)}
            className="text-micro text-brand-deep hover:underline">
            {system || sizeless ? "O'zgartirish" : "Tanlash"}
          </button>
        )}
      </div>

      {showing ? (
        <div className="mt-2 space-y-2 rounded-control border border-line p-3">
          {families.map(([family, runs]) => {
            // One system, no scale: the family label and its chip would be the
            // same word twice ("Kamar  Kamar"), so the chip stands alone.
            const alone = runs.length === 1 && !runs[0].scale
            return (
              <div key={family} className="flex flex-wrap items-center gap-1.5">
                <span className="w-40 shrink-0 text-small text-ink-soft">
                  {alone ? "" : family}
                </span>
                {runs.map((run) => (
                  <button
                    key={run.slug}
                    type="button"
                    onClick={() => choose(run.slug)}
                    className={cn(
                      "h-control rounded-control border border-line px-3 text-small transition-colors hover:bg-line-soft",
                      system?.slug === run.slug &&
                        "border-brand bg-brand-soft font-medium text-brand-deep",
                    )}
                  >
                    {alone
                      ? family
                      : run.scale ||
                        (run.values.length > 1
                          ? `${run.values[0]}–${run.values[run.values.length - 1]}`
                          : (run.values[0] ?? "—"))}
                  </button>
                ))}
              </div>
            )
          })}
          <button
            type="button"
            onClick={() => choose(null)}
            className={cn(
              "h-control rounded-control border border-line px-3 text-small hover:bg-line-soft",
              sizeless && "border-brand bg-brand-soft",
            )}
          >
            O'lchamsiz — bu tavarda o'lcham yo'q
          </button>
          <Problem error={systems.error || write.error} />
        </div>
      ) : null}
    </div>
  )
}

/**
 * One size, and how many of it arrived. Minus and plus are for counting a
 * table out by hand, the box for when the number is already known.
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
  // way — flexbox must never clip the count box on a phone.
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

// ----------------------------------------------------- moment 2 · javon oldida

/**
 * The screen become one line and one question. The goods exist, they are in
 * QABUL, they have stickers — the only thing left is the one thing nobody
 * could know at the bench.
 */
function MomentTwo({
  open,
  pending,
  error,
  onPutAway,
  onAnotherColour,
  onLater,
}: {
  open: Open
  pending: boolean
  error: unknown
  onPutAway: (code: string) => void
  /** Only for a receipt booked this minute — the card and cost are still on
   *  the form to be kept. */
  onAnotherColour?: () => void
  onLater: () => void
}) {
  const [code, setCode] = useState("")
  // Where this model already lives, offered as taps — the person at the
  // shelf should not have to remember which cell held the 42s.
  const plan = usePutawayPlan(open.product_id, open.quantity)

  return (
    <div className="space-y-3">
      <Panel>
        <div className="flex items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-control bg-warn-soft text-warn-ink">
            <Package className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-body font-semibold tabular">
              {units(open.quantity)} · yorliqlangan · javonga qo'yilmagan
            </div>
            <div className="truncate text-micro tabular text-ink-faint">
              {open.product_title || "—"} · {open.code}
            </div>
          </div>
          {onAnotherColour ? (
            <Button type="button" variant="secondary" size="sm" className="gap-1" onClick={onAnotherColour}>
              <Plus className="size-4" />
              Yana bir rang
            </Button>
          ) : null}
        </div>
      </Panel>

      <Labels open={open} />

      <Panel title="Qaysi yacheyka?">
        <div className="space-y-3">
          <p className="text-small text-ink-soft">
            Yacheyka yorlig'ini <b>skanerlang</b> — bitta skaner, tavar joyida.
            Yoki kodini yozing:
          </p>

          {plan.data?.lines.length ? (
            <div className="flex flex-wrap items-center gap-1">
              <span className="mr-1 text-micro text-ink-soft">Taklif:</span>
              {plan.data.lines.map((line) => (
                <button
                  key={line.code}
                  type="button"
                  disabled={pending}
                  onClick={() => onPutAway(line.code)}
                  className="flex h-control items-center gap-1.5 rounded-control border border-brand bg-brand-soft px-3 text-small font-medium tabular text-brand-deep transition-colors hover:bg-brand hover:text-brand-ink">
                  <MapPin className="size-3.5" />
                  {line.code}
                  <span className="text-micro opacity-80">
                    {line.holds_this_model ? "shu model shu yerda" : "bo'sh joy"}
                  </span>
                </button>
              ))}
            </div>
          ) : null}

          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              if (code.trim()) onPutAway(code)
            }}
          >
            <Input
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              placeholder="B-01-02"
              aria-label="Yacheyka kodi"
              className="h-control-lg w-40 tabular text-body" />
            <Button size="lg" type="submit" disabled={!code.trim() || pending} className="gap-2">
              {pending ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Check className="size-5" />
              )}
              Javonga qo'ydim
            </Button>
          </form>

          <Problem error={error} />

          {/* The question may wait: QABUL is a sellable place, nothing is
              lost, and the queue below holds it with its age. */}
          <button
            type="button"
            onClick={onLater}
            className="text-micro text-ink-faint hover:text-ink">
            Keyinroq — navbatda qoladi
          </button>
        </div>
      </Panel>
    </div>
  )
}

/**
 * The stickers, offered the moment the receipt lands — printing them and
 * booking the goods are the same minute of work, on the same screen.
 *
 * A fresh receipt prints itself (`autoPrint`): pressing Qabul *is* the
 * decision to print, and every unit gets one. Reprint is always available —
 * printers jam, and the alternative is a barcode written by hand. A receipt
 * reopened from the queue fetches its lines from the label door first.
 */
function Labels({ open }: { open: Open }) {
  // Remount to print again: the roll prints on mount, so a bumped key is a
  // second run of the same pages.
  const [printSeq, setPrintSeq] = useState(1)
  const [wanted, setWanted] = useState(false)
  const sheet = useRunLabels(!open.receipt && wanted ? open.id : null)
  const labels = open.receipt ? open.receipt.labels : (sheet.data?.products ?? [])

  return (
    <Panel
      title={
        open.receipt
          ? `${open.receipt.quantity} ta yorliq — chop etilmoqda`
          : "Yorliqlar"
      }
      aside={
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="gap-1.5"
          disabled={sheet.isFetching}
          onClick={() => {
            setWanted(true)
            setPrintSeq((was) => was + 1)
          }}
        >
          {sheet.isFetching ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Printer className="size-4" />
          )}
          {open.receipt ? "Qayta chop etish" : "Yorliqlarni chop etish"}
        </Button>
      }
    >
      <div className="space-y-2">
        {labels.length && (open.receipt || wanted) ? (
          <LabelRoll
            key={printSeq}
            labels={labels}
            autoPrint
          />
        ) : null}
        {/* The five-minute support call every shop makes once, answered in
            the screen's own words. */}
        <p className="text-micro text-ink-faint">
          Birinchi marta chop etishda brauzer oynasida: <b>Headers and footers</b>{" "}
          belgisini oling, <b>Margins</b> ni <b>None</b> qiling. Har dona uchun
          bitta yorliq — 58 × 40 mm.
        </p>
      </div>
    </Panel>
  )
}

// --------------------------------------------------------------- va joyida

/**
 * The plain confirmation: how much, where, what it cost — with the cell as a
 * way into the shelf map, because "omborda ko'rinmayapti" was one of the
 * three complaints this screen was rebuilt for.
 */
function Shelved({
  done,
  onAnotherColour,
  onNew,
}: {
  done: { answer: ReceiptShelved; from: Open }
  onAnotherColour?: () => void
  onNew: () => void
}) {
  const { answer, from } = done
  const unready = from.receipt?.product.unready ?? []

  return (
    <div className="space-y-3 rounded-panel border border-good bg-good-soft p-3">
      <div className="flex items-start gap-2">
        <Check className="mt-0.5 size-5 shrink-0 text-good" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-body font-semibold">
            {from.product_title || answer.run_code}
          </div>
          {answer.quantity > 0 ? (
            <div className="text-body tabular">
              {units(answer.quantity)} ·{" "}
              <a
                href={`/ombor?q=${encodeURIComponent(answer.location_code)}`}
                className="font-semibold text-brand-deep underline underline-offset-2">
                {answer.location_code}
              </a>{" "}
              · {money(answer.total_cost)}
            </div>
          ) : (
            // A second tap at the shelf is not a mistake to shout about: the
            // goods are exactly where the person wanted them.
            <div className="text-small text-ink-soft">{answer.message}</div>
          )}
        </div>
      </div>

      {unready.length ? (
        <p className="text-micro text-ink-soft">
          Do'konga chiqarish kartaning o'zida — kerak:{" "}
          {unready.map((gap) => gap.label).join(", ")}.{" "}
          <a
            href="/mahsulotlar?status=draft"
            className="font-medium text-brand-deep underline">
            Kartani ochish
          </a>
        </p>
      ) : null}

      <div className="flex gap-2">
        {onAnotherColour ? (
          <Button size="lg" className="flex-1 gap-2" onClick={onAnotherColour}>
            <Plus className="size-5" />
            Yana bir rang
          </Button>
        ) : null}
        <Button
          size="lg"
          variant={onAnotherColour ? "ghost" : "secondary"}
          className={onAnotherColour ? "" : "flex-1"}
          onClick={onNew}
        >
          Yangi qabul
        </Button>
      </div>
    </div>
  )
}

// -------------------------------------------------- the second moment's queue

/**
 * Receipts whose goods are labelled and still standing in QABUL — the
 * question that was left for later, kept with its age. Each row opens
 * straight into its own moment two; reprint lives there too.
 */
function WaitingQueue({ onOpen }: { onOpen: (row: WaitingReceipt) => void }) {
  const waiting = useWaitingReceipts()
  const rows = waiting.data ?? []

  if (!rows.length) return null

  return (
    <Panel title="Javonga qo'yilmaganlar" bare>
      <ul className="divide-y">
        {rows.map((row) => {
          const overnight = row.age_minutes >= OVERNIGHT_MINUTES
          return (
            <li key={row.id}>
              <button
                type="button"
                onClick={() => onOpen(row)}
                className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 p-3 text-left transition-colors hover:bg-line-soft">
                <span
                  className={cn(
                    "grid size-9 shrink-0 place-items-center rounded-control",
                    overnight
                      ? "bg-danger-soft text-danger"
                      : "bg-warn-soft text-warn-ink",
                  )}>
                  <Package className="size-4" />
                </span>
                {/* `basis-40` with a wrapping row: on a desk the prompt sits
                    at the end of the line, and on a phone it drops under the
                    goods rather than squeezing the name that says which
                    receipt this is down to `Krossovka · Walk0…`. */}
                <span className="min-w-0 flex-1 basis-40">
                  <span className="block text-small font-medium">
                    {row.product_title || row.code}
                  </span>
                  <span
                    className={cn(
                      "block text-micro tabular",
                      overnight ? "text-danger" : "text-ink-faint",
                    )}>
                    {units(row.quantity)} · {row.code} · {age(row.age_minutes)} turgan
                  </span>
                </span>
                <span className="ms-auto flex shrink-0 items-center gap-1 text-micro font-medium text-brand-deep">
                  Qaysi yacheyka?
                  <ArrowRight className="size-3.5" />
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
