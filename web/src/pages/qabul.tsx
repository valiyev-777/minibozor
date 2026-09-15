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

import { LabelRoll } from "@/components/label-roll"
import { PageHeader, Panel, Problem, Segmented, Waiting } from "@/components/page"
import { Capture, mediaUrl } from "@/components/photo-step"
import { ScanTarget, type ScanAnswer } from "@/components/scan"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, bySize, groups, money, tidySize, units } from "@/lib/format"
import {
  useProduct,
  useProducts,
  usePutawayPlan,
  useReceive,
  useRunLabels,
  useShelveReceipt,
  useSupplies,
  useVariants,
  useVocab,
  useWaitingReceipts,
  type Receipt,
  type ReceiptShelved,
  type WaitingReceipt,
} from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

// A receipt that has stood this long is the thing this shop actually loses
// money on: goods in the building that the shelf map has not heard of.
const OVERNIGHT_MINUTES = 14 * 60

/** One size and how many of it came. An array, not a map: the order these
 *  were typed is the order the stickers print in and the order the piles sit
 *  on the table, and numeric object keys would be re-sorted by the runtime. */
type SizeLine = { size: string; qty: string }

type Draft = {
  product: AdminProduct | null
  kind: string
  brand: string
  snapshot: string
  /** One colour — the whole receipt's. A second colour is a second receipt. */
  colour: string
  lines: SizeLine[]
  unitCost: string
  place: string
  /** What the van cost — the whole trip's. Sent once, not per colour. */
  fare: string
  /** Whether moment one's first half is answered — the goods have a card. */
  named: boolean
}

const EMPTY: Draft = {
  product: null,
  kind: "",
  brand: "",
  snapshot: "",
  colour: "",
  lines: [],
  unitCost: "",
  place: "",
  fare: "",
  named: false,
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
  // A scanned goods sticker names a product; the full card is fetched and
  // filled in — even when the variant has no places yet.
  const [scanFill, setScanFill] = useState<{ id: number; colour: string } | null>(null)

  const receive = useReceive()
  const shelve = useShelveReceipt()
  const scanned = useProduct(scanFill?.id ?? null)

  useEffect(() => {
    if (!scanFill || !scanned.data || scanned.data.id !== scanFill.id) return
    const card = scanned.data
    setDraft((was) => ({
      ...was,
      product: card,
      kind: card.kind,
      brand: "",
      snapshot: "",
      // The sticker knows its colour; presetting it saves a tap and stays
      // editable — more of the white may really be more of the black.
      colour: scanFill.colour,
      named: true,
    }))
    setScanFill(null)
    setDone(null)
  }, [scanFill, scanned.data])

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
      named: true,
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
      setScanFill({ id: answer.variant.product_id, colour: answer.variant.colour })
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
  onBooked,
}: {
  draft: Draft
  setDraft: (next: (was: Draft) => Draft) => void
  receive: ReturnType<typeof useReceive>
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
  const needsColour = draft.product !== null && own.length > 0

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
  const ready = draft.named && !missing && !receive.isPending
  const hint = missing ? MISSING_HINT[missing] : money(total * cost)

  function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!ready) return
    receive.mutate(
      {
        // Either the card that exists, or the words a new one is written
        // from — never both, so a scan cannot half-overwrite a typed card.
        ...(draft.product
          ? { product_id: draft.product.id }
          : {
              kind: draft.kind.trim(),
              brand: draft.brand.trim(),
              snapshot_url: draft.snapshot,
            }),
        colour: draft.colour.trim(),
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
      {draft.named ? (
        <Named draft={draft} onChange={() => setDraft(() => EMPTY)} />
      ) : (
        <IdentifyCard
          draft={draft}
          onSet={set}
          onPick={(product) =>
            setDraft((was) => ({ ...was, product, kind: product.kind, named: true }))
          }
          onNamed={() => set("named", true)}
        />
      )}

      {draft.named ? (
        <>
          <Counts
            product={draft.product}
            kind={draft.kind}
            colour={draft.colour}
            ownColours={own}
            lines={draft.lines}
            onColour={(colour) => set("colour", colour)}
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
      {draft.named ? (
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
function Named({ draft, onChange }: { draft: Draft; onChange: () => void }) {
  const title =
    draft.product?.title ?? [draft.kind, draft.brand].filter(Boolean).join(" · ")

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

/**
 * Which card. One panel for both answers: goods we have had are a search —
 * or a scan, which lands here already filled — and goods we have not are a
 * card written from kind + brand. The colour is not asked here: it belongs
 * to the count, and it is the part "yana bir rang" retypes.
 */
function IdentifyCard({
  draft,
  onSet,
  onPick,
  onNamed,
}: {
  draft: Draft
  onSet: <K extends keyof Draft>(key: K, value: Draft[K]) => void
  onPick: (product: AdminProduct) => void
  onNamed: () => void
}) {
  const [needle, setNeedle] = useState("")
  const [writing, setWriting] = useState(false)
  const vocab = useVocab()
  const found = useProducts(writing ? "" : needle, "")
  const results = needle.trim() && !writing ? (found.data?.items ?? []).slice(0, 8) : []

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

            {needle.trim() && found.isLoading ? <Waiting what="Kartalar" /> : null}

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

            {needle.trim() && found.data?.items.length === 0 ? (
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

            {draft.kind.trim() ? (
              <>
                <Maybe kind={draft.kind} brand={draft.brand} onPick={onPick} />
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
function Maybe({
  kind,
  brand,
  onPick,
}: {
  kind: string
  brand: string
  onPick: (product: AdminProduct) => void
}) {
  const needle = [kind, brand].filter(Boolean).join(" ")
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
  // The value first, always, even when it is not one of the learned options —
  // a word typed into "+ yangi" that is then drawn nowhere reads as the field
  // having eaten it.
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
            // Enter finishes the word, and nothing else — it must not reach
            // the form and submit a half-written receipt.
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

// --------------------------------------------------------------------- nechta

/**
 * One colour, and how many of each size of it came.
 *
 * The colour is asked here — beside the counts it belongs to — and there is
 * exactly one of it: a mixed bale is two receipts, one after the other, with
 * the card and the cost carried between them. The size→quantity table stays
 * in the order it is typed, because that is the order the stickers print in
 * and the order the piles sit on the table.
 */
function Counts({
  product,
  kind,
  colour,
  ownColours,
  lines,
  onColour,
  onLines,
}: {
  product: AdminProduct | null
  kind: string
  colour: string
  ownColours: string[]
  lines: SizeLine[]
  onColour: (colour: string) => void
  onLines: (lines: SizeLine[]) => void
}) {
  const vocab = useVocab()
  const grid = useVariants(product?.id ?? null)
  const [adding, setAdding] = useState("")
  const [typing, setTyping] = useState(false)

  // Some things have no size: a cap, a bag. The question is answered before
  // it is asked — from the card when there is one, otherwise from what this
  // kind has always arrived as — and `chose` is a hand on the wheel: once
  // somebody has said which it is, nothing overrules them.
  const [chose, setChose] = useState<boolean | null>(null)
  const cardIsSizeless =
    (grid.data ?? []).length > 0 && (grid.data ?? []).every((cell) => !cell.size)
  const kindIsSizeless = (vocab.data?.sizeless ?? []).includes(kind)
  const sizeless = chose ?? (product ? cardIsSizeless : kindIsSizeless)

  // A question with one answer is a tap for nothing: a card that only ever
  // came in black starts with black picked.
  const only = ownColours.length === 1 ? ownColours[0] : null
  useEffect(() => {
    if (only !== null && !colour) onColour(only)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only])

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

  const colourOptions = useMemo(() => {
    const seen = new Set([...ownColours, ...(vocab.data?.colours ?? [])])
    return [...seen].slice(0, 12)
  }, [ownColours, vocab.data])

  /** Sizes worth offering: the card's own in this colour, and what this kind
   *  last arrived in — minus the ones already on the table. */
  const suggested = useMemo(() => {
    const mine = (grid.data ?? [])
      .filter((cell) => !colour || cell.colour === colour)
      .map((cell) => cell.size)
    const seen = new Set([...mine, ...(vocab.data?.sizes[kind] ?? [])].map(tidySize))
    seen.delete("")
    for (const line of lines) seen.delete(line.size)
    return [...seen].sort(bySize)
  }, [grid.data, vocab.data, kind, colour, lines])

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
    <Panel
      title="Nechta keldi?"
      aside={
        <Segmented
          label="O'lcham bormi?"
          value={sizeless ? "sizeless" : "sized"}
          onChange={(next) => {
            const on = next === "sizeless"
            if (on === sizeless) return
            setChose(on)
            onLines([])
          }}
          options={[
            { key: "sized", label: "O'lchamli" },
            { key: "sizeless", label: "O'lchamsiz" },
          ]}
        />
      }
    >
      <div className="space-y-3">
        <Chips
          label="Rang — bitta qabul, bitta rang"
          options={colourOptions}
          value={colour}
          onChange={onColour}
          placeholder="Oq" />

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
