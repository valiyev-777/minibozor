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
 * there is no scanner yet, and the racks are small enough to draw. A pile that
 * does not fit one cell takes the next: "the rest into another cell" keeps the
 * goods, the sizes and the cost, and asks only where.
 */

import {
  ArrowRight,
  Check,
  Loader2,
  Package,
  Plus,
  Search,
  Sparkles,
  X,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Capture, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, money, units } from "@/lib/format"
import {
  useBookInPile,
  useLocation,
  useProducts,
  useSackSorted,
  useShelfMap,
  useSuggestedCell,
  useStartRun,
  useSupplies,
  useVariants,
  useVocab,
} from "@/lib/queries"
import type { AdminProduct, Location, Pile as BookedPile, PileSize } from "@/lib/types"

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
            // Another colour out of the same sack, which is the case this form
            // did not have an answer for: a sack of shirts that is 20 black
            // and 20 white meant filling the whole thing in twice. The kind,
            // the make, the cost and the cell stay — only the colour and the
            // counts are asked again.
            //
            // **Onto the card that was just written.** Without carrying the
            // product through, the second colour walked the new-card path
            // again and opened a *second* card for the same goods — the exact
            // duplicate this screen warns about everywhere else.
            const card = booked.product
            setBooked(null)
            setDraft((was) => ({
              ...was,
              product: card,
              kind: card.kind || was.kind,
              colour: "",
              sizes: {},
              snapshot: "",
            }))
          }}
          onAnotherCell={() => {
            // The rest of *this* colour into another cell. The counts are
            // cleared, and that is not tidiness: keeping them meant one tap
            // booked the same nine pairs a second time.
            setBooked(null)
            setDraft((was) => ({ ...was, cell: "", sizes: {} }))
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
  const steps = [
    { n: 1, label: "Tavar keldi", hint: "nima, nechta" },
    { n: 2, label: "Javonga joylashtirildi", hint: "qaysi yacheykaga" },
    {
      n: 3,
      label: "Telefonga chiqardik",
      hint: "rasm, narx, kategoriya",
      href: "/sotuvga-chiqarish",
    },
  ]

  return (
    <ol className="flex flex-wrap gap-2">
      {steps.map((step) => {
        const here = step.n === at
        const done = step.n < at
        const body = (
          <>
            <span
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full text-micro font-semibold tabular",
                here && "bg-brand text-brand-ink",
                done && "bg-good text-good-ink",
                !here && !done && "bg-canvas text-ink-faint",
              )}
            >
              {done ? <Check className="size-3.5" /> : step.n}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-small font-medium">{step.label}</span>
              <span className="block truncate text-micro text-ink-faint">{step.hint}</span>
            </span>
          </>
        )
        return (
          <li key={step.n} className="min-w-44 flex-1">
            {step.href ? (
              <a
                href={step.href}
                className="flex h-full items-center gap-2 rounded-panel border border-dashed bg-surface p-2 hover:border-brand"
              >
                {body}
                <ArrowRight className="size-4 shrink-0 text-ink-faint" />
              </a>
            ) : (
              <div
                className={cn(
                  "flex h-full items-center gap-2 rounded-panel border bg-surface p-2",
                  here && "border-brand",
                )}
              >
                {body}
              </div>
            )}
          </li>
        )
      })}
    </ol>
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
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <button
        type="button"
        onClick={() => onPick("existing")}
        className="flex flex-col items-start gap-1 rounded-panel border-2 bg-surface p-4 text-left hover:border-brand"
      >
        <Search className="size-6 text-brand" />
        <span className="text-body font-semibold">Bor tavar yana keldi</span>
        <span className="text-small text-ink-soft">
          Kartasi bor — faqat nechta va qaysi javonga
        </span>
      </button>

      <button
        type="button"
        onClick={() => onPick("new")}
        className="flex flex-col items-start gap-1 rounded-panel border-2 bg-surface p-4 text-left hover:border-brand"
      >
        <Sparkles className="size-6 text-brand" />
        <span className="text-body font-semibold">Yangi tavar</span>
        <span className="text-small text-ink-soft">
          Birinchi marta keldi — kartasi shu yerda ochiladi
        </span>
      </button>
    </div>
  )
}

// ------------------------------------------------------------------- the pile

type Draft = {
  product: AdminProduct | null
  kind: string
  brand: string
  colour: string
  snapshot: string
  sizes: Record<string, string>
  unitCost: string
  cell: string
  place: string
  /** Whether step one is answered — the goods have a name. */
  named: boolean
}

const EMPTY: Draft = {
  product: null,
  kind: "",
  brand: "",
  colour: "",
  snapshot: "",
  sizes: {},
  unitCost: "",
  cell: "",
  place: "",
  named: false,
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
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((was) => ({ ...was, [key]: value }))

  const lines: PileSize[] = Object.entries(draft.sizes)
    .map(([size, qty]) => ({ size, quantity: Number(qty) || 0 }))
    .filter((line) => line.quantity > 0)
  const total = lines.reduce((sum, line) => sum + line.quantity, 0)
  const ready =
    draft.named && total > 0 && Number(draft.unitCost) > 0 && Boolean(draft.cell)

  return (
    <form
      className="space-y-3 pb-28"
      onSubmit={(event) => {
        event.preventDefault()
        if (!ready) return
        book.mutate(
          {
            product_id: draft.product?.id,
            kind: draft.kind,
            brand: draft.brand,
            colour: draft.colour,
            snapshot_url: draft.snapshot,
            sizes: lines,
            unit_cost: Number(draft.unitCost),
            location_code: draft.cell,
            place: draft.place.trim(),
          },
          { onSuccess: onBooked },
        )
      }}
    >
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
            colour={draft.colour}
            kind={draft.kind}
            sizes={draft.sizes}
            onSet={(sizes) => set("sizes", sizes)}
            onColour={(colour) => set("colour", colour)}
          />

          <div className="grid gap-3 rounded-panel border bg-surface p-3 sm:grid-cols-2">
            <label>
              <span className="mb-1 block text-micro text-ink-soft">
                Tannarx — bir dona
              </span>
              <Input
                value={draft.unitCost}
                onChange={(event) => set("unitCost", event.target.value.replace(/\D/g, ""))}
                inputMode="numeric"
                placeholder="85 000"
                aria-label="Tannarx"
                className="h-control-lg tabular text-body"
              />
            </label>
            <Place value={draft.place} onSet={(place) => set("place", place)} />
          </div>

          <Cells
            chosen={draft.cell}
            productId={draft.product?.id ?? null}
            onChoose={(code) => set("cell", code)}
          />
        </>
      ) : null}

      <Problem error={book.error} />

      {/* The bar stays put. Reaching the button used to mean scrolling past
          nine fields with a sack in the other hand. */}
      {draft.named ? (
        <div className="fixed inset-x-0 bottom-0 border-t bg-surface p-3 md:left-60">
          <div className="mx-auto flex max-w-4xl items-center gap-3">
            <div className="min-w-0 flex-1">
              <div className="truncate text-small font-semibold">
                {total ? units(total) : "nechta?"}
                {draft.cell ? ` → ${draft.cell}` : ""}
              </div>
              <div className="text-micro tabular text-ink-faint">
                {money(total * (Number(draft.unitCost) || 0))}
              </div>
            </div>
            <Button
              type="submit"
              disabled={!ready || book.isPending}
              className="h-control-lg gap-2 text-body"
            >
              {book.isPending ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Check className="size-5" />
              )}
              {draft.cell ? `${draft.cell} ga qo'ydim` : "Yacheykani tanlang"}
            </Button>
          </div>
        </div>
      ) : null}
    </form>
  )
}

/** Step one, answered, on one line. */
function Named({ draft, onChange }: { draft: Draft; onChange: () => void }) {
  const title =
    draft.product?.title ?? [draft.kind, draft.brand, draft.colour].filter(Boolean).join(" · ")

  return (
    <div className="flex items-center gap-3 rounded-panel border border-good bg-good-soft p-3">
      <Check className="size-5 shrink-0 text-good" />
      <div className="min-w-0 flex-1">
        <div className="truncate text-body font-semibold">{title}</div>
        {draft.product ? (
          <div className="text-micro tabular text-ink-soft">
            {draft.product.sku} · javonda {draft.product.stock_left} dona
          </div>
        ) : null}
      </div>
      <Button type="button" variant="ghost" size="sm" onClick={onChange}>
        o'zgartirish
      </Button>
    </div>
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
    <section className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-small font-semibold">Qaysi tavar keldi?</h2>
        <Button type="button" variant="ghost" size="sm" onClick={onBack} aria-label="Orqaga">
          <X className="size-4" />
        </Button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
        <Input
          autoFocus
          value={needle}
          onChange={(event) => setNeedle(event.target.value)}
          placeholder="nom yoki kod"
          aria-label="Mavjud kartani qidirish"
          className="h-control-lg pl-8 text-body"
        />
      </div>

      {found.isLoading ? <Waiting what="Kartalar" /> : null}

      <ul className="divide-y">
        {(found.data?.items ?? []).slice(0, 8).map((product) => (
          <li key={product.id}>
            <button
              type="button"
              onClick={() => onPick(product)}
              className="flex w-full items-center gap-3 py-2 text-left"
            >
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
    </section>
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
    <section className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-small font-semibold">Qanday tavar?</h2>
        <Button type="button" variant="ghost" size="sm" onClick={onBack} aria-label="Orqaga">
          <X className="size-4" />
        </Button>
      </div>

      <Chips
        label="Tur"
        options={vocab.data?.kinds ?? []}
        value={draft.kind}
        onChange={(value) => onSet("kind", value)}
        placeholder="Krossovka"
      />
      <Chips
        label="Brend"
        options={vocab.data?.brands ?? []}
        value={draft.brand}
        onChange={(value) => onSet("brand", value)}
        placeholder="Nike"
        none="brendsiz"
      />
      <Chips
        label="Rang"
        options={vocab.data?.colours ?? []}
        value={draft.colour}
        onChange={(value) => onSet("colour", value)}
        placeholder="Qora"
      />

      {draft.kind.trim() ? (
        <>
          <Maybe draft={draft} onPick={onPick} />
          <Capture
            colour=""
            current={draft.snapshot || undefined}
            onTaken={(_, url) => onSet("snapshot", url)}
            guide="tanish uchun — mijozga ko'rinmaydi"
            placeholder="rasm"
          />
          <Button type="button" className="h-control-lg w-full gap-2" onClick={onNamed}>
            Davom etish
            <ArrowRight className="size-5" />
          </Button>
        </>
      ) : null}
    </section>
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
              className="flex w-full items-center gap-2 rounded-control bg-surface p-2 text-left"
            >
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
      className="size-11 shrink-0 rounded-control object-cover"
    />
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
            className="h-control w-40"
          />
        ) : (
          <button
            type="button"
            onClick={() => setWriting(true)}
            className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep"
          >
            + yangi
          </button>
        )}
      </div>
    </div>
  )
}

// -------------------------------------------------------------------- how many

function Counts({
  product,
  colour,
  kind,
  sizes,
  onSet,
  onColour,
}: {
  product: AdminProduct | null
  colour: string
  kind: string
  sizes: Record<string, string>
  onSet: (sizes: Record<string, string>) => void
  onColour: (colour: string) => void
}) {
  const vocab = useVocab()
  const grid = useVariants(product?.id ?? null)
  const [adding, setAdding] = useState("")
  const [naming, setNaming] = useState(false)
  const [sizeless, setSizeless] = useState(false)

  // Which colour of an existing card arrived. Auto-picked when there is only
  // one, because a question with one answer is a tap for nothing.
  const own = useMemo(() => {
    const seen = new Set((grid.data ?? []).map((cell) => cell.colour))
    return [...seen]
  }, [grid.data])
  const only = own.length === 1 ? own[0] : null
  useEffect(() => {
    if (only !== null && !colour && !naming) onColour(only)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only])

  // What this colour and size already holds, so a second count of the same
  // size reads as an addition rather than as a figure about to be overwritten.
  const already = useMemo(() => {
    const map = new Map<string, number>()
    for (const cell of grid.data ?? []) {
      map.set(`${cell.colour} ${cell.size}`, cell.stock_left)
    }
    return map
  }, [grid.data])

  const offered = useMemo(() => {
    const mine = (grid.data ?? [])
      .filter((cell) => !colour || cell.colour === colour)
      .map((cell) => cell.size)
    const seen = new Set([
      ...mine,
      ...(vocab.data?.sizes[kind] ?? []),
      ...Object.keys(sizes),
    ])
    seen.delete("")
    return [...seen]
  }, [grid.data, colour, kind, vocab.data, sizes])

  function add(size: string) {
    const wanted = size.trim()
    if (wanted) onSet({ ...sizes, [wanted]: sizes[wanted] ?? "" })
    setAdding("")
  }

  return (
    <section className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-small font-semibold">Nechta keldi?</h2>
        <button
          type="button"
          onClick={() => {
            setSizeless(!sizeless)
            onSet({})
          }}
          className="text-micro text-brand-deep"
        >
          {sizeless ? "o'lchamlari bor" : "o'lchamsiz"}
        </button>
      </div>

      {/* Which colour of an existing card arrived — its own colours, **or a
          new one**. Drawn even where the card has a single colour, which looks
          like a question with one answer and is not: a card that arrived in
          black had no way at all to receive a pile of white, because the row
          was hidden precisely when there was one colour, which is exactly when
          a second one turns up. */}
      {product ? (
        <div className="flex flex-wrap gap-1">
          {[...own, ...(colour && !own.includes(colour) ? [colour] : [])].map((one) => (
            <button
              key={one}
              type="button"
              onClick={() => onColour(one)}
              className={cn(
                "h-control rounded-control border px-3 text-small",
                one === colour && "border-brand bg-brand text-brand-ink",
              )}
            >
              {one || "rangsiz"}
            </button>
          ))}
          {naming ? (
            <Input
              autoFocus
              value={colour}
              onChange={(event) => onColour(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return
                event.preventDefault()
                setNaming(false)
                event.currentTarget.blur()
              }}
              onBlur={() => setNaming(false)}
              placeholder="Oq"
              aria-label="Yangi rang"
              className="h-control w-32"
            />
          ) : (
            <button
              type="button"
              onClick={() => {
                onColour("")
                setNaming(true)
              }}
              className="h-control rounded-control border border-dashed px-3 text-small text-brand-deep"
            >
              + yangi rang
            </button>
          )}
        </div>
      ) : null}

      {sizeless ? (
        <Input
          value={sizes[""] ?? ""}
          onChange={(event) => onSet({ "": event.target.value.replace(/\D/g, "") })}
          inputMode="numeric"
          placeholder="12"
          aria-label="Nechta"
          className="h-control-lg w-28 tabular text-body"
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          {offered.map((size) => (
            <SizeBox
              key={size}
              size={size}
              value={sizes[size] ?? ""}
              already={already.get(`${colour} ${size}`) ?? 0}
              onChange={(value) => onSet({ ...sizes, [size]: value })}
            />
          ))}
          {/* Dashed, and it says what it is. It used to be a bare box the
              same size and shape as the quantity boxes beside it, sitting
              under the word "o'lcham" — so a count typed into the wrong one
              became a *size* called "5", and the row grew nonsense. */}
          <label className="w-24 rounded-control border border-dashed border-brand/50 p-1">
            <span className="mb-0.5 block text-center text-micro text-brand-deep">
              + o'lcham
            </span>
            <Input
              value={adding}
              onChange={(event) => setAdding(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== "Enter") return
                event.preventDefault()
                add(adding)
              }}
              onBlur={() => add(adding)}
              placeholder="XL"
              aria-label="Yangi o'lcham"
              className="h-control text-center"
            />
          </label>
        </div>
      )}
    </section>
  )
}

/**
 * One size and its count.
 *
 * Tapping the size adds one, which covers most of what comes off a van — two
 * of a size, three of the next — and typing is there for the rest. No mode to
 * choose between them.
 */
function SizeBox({
  size,
  value,
  already,
  onChange,
}: {
  size: string
  value: string
  already: number
  onChange: (value: string) => void
}) {
  const count = Number(value) || 0
  return (
    <div className="w-20">
      <button
        type="button"
        onClick={() => onChange(String(count + 1))}
        aria-label={`${size} — bittasini qo'shish`}
        className={cn(
          "mb-0.5 block w-full rounded-control border py-0.5 text-center text-small font-medium",
          count > 0 ? "border-brand bg-brand-soft text-brand-deep" : "text-ink-soft",
        )}
      >
        {size}
      </button>
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
        inputMode="numeric"
        aria-label={`${size} — nechta`}
        className={cn(
          "h-control-lg text-center tabular text-body",
          count > 0 && "border-brand",
        )}
      />
      {already > 0 && count > 0 ? (
        <span className="mt-0.5 block text-center text-micro text-ink-faint">
          {already} + {count} = {already + count}
        </span>
      ) : null}
    </div>
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
        className="h-control-lg"
      />
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
 * What is already in the cell that was picked.
 *
 * One model per cell is the working discipline, and the software supports it
 * rather than enforcing it — so this is the thing that makes a wrong choice
 * visible: a picker reaching into a cell of black shirts to fetch a red one is
 * the mistake nobody catches until the parcel is at a door. A valid code for
 * the wrong cell is exactly what a grid of 48 identical squares invites.
 */
function Inside({ code }: { code: string }) {
  const cell = useLocation(code || null)
  if (!code) return null
  if (!cell.data) return null

  if (!cell.data.contents.length) {
    return (
      <p className="rounded-control bg-good-soft p-2 text-micro text-good">
        {code} — bo'sh
      </p>
    )
  }
  // Counted by *model*, not by cell of the grid. A shirt in two sizes is two
  // rows of contents and one thing on the shelf, so counting rows said "and 1
  // other kind" about the goods the person was holding — and the whole point
  // of the line is to warn that something *else* is in there.
  const models = [...new Set(cell.data.contents.map((row) => row.product_title))]
  const units = cell.data.contents.reduce((sum, row) => sum + row.qty, 0)
  const others = models.length - 1
  return (
    <p
      className={cn(
        "rounded-control p-2 text-micro",
        others ? "bg-warn-soft text-warn-ink" : "bg-canvas text-ink-soft",
      )}
    >
      {code} da bor: <b>{models[0]}</b>
      {others ? ` — va yana ${others} xil tovar` : ""} · {units} dona
    </p>
  )
}

function Cells({
  chosen,
  productId,
  onChoose,
}: {
  chosen: string
  productId: number | null
  onChoose: (code: string) => void
}) {
  const map = useShelfMap()
  // Where the rest of this model already is. One model per cell is what keeps
  // picking short, so the useful cell is rarely a free one — and the person
  // would otherwise have to remember which.
  const suggested = useSuggestedCell(productId).data?.code ?? ""

  const racks = useMemo(() => {
    const byRack = new Map<string, Location[]>()
    for (const cell of map.data?.cells ?? []) {
      const key = cell.rack ?? "?"
      byRack.set(key, [...(byRack.get(key) ?? []), cell])
    }
    return [...byRack.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [map.data])

  return (
    <section className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-small font-semibold">Qaysi yacheykaga?</h2>
        {chosen ? (
          <span className="tabular text-small font-semibold text-brand-deep">{chosen}</span>
        ) : suggested ? (
          <button
            type="button"
            onClick={() => onChoose(suggested)}
            className="tabular text-small font-medium text-brand-deep underline"
          >
            {suggested} — shu model shu yerda
          </button>
        ) : (
          <span className="text-micro text-ink-faint">bo'sh katak — punktir</span>
        )}
      </div>

      {map.isLoading ? <Waiting what="Javonlar" /> : null}

      <Inside code={chosen} />

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
                    className="pb-0.5 text-center text-micro tabular text-ink-faint"
                  >
                    {column}
                  </span>
                ))}
                {/* Bottom row at the bottom, the way a person reads a shelf. */}
                {Array.from({ length: rows }, (_, index) => rows - index).flatMap((row) => [
                  <span
                    key={`row-${rack}-${row}`}
                    className="self-center text-center text-micro tabular text-ink-faint"
                  >
                    {row}
                  </span>,
                  ...Array.from({ length: columns }, (_, index) => index + 1).map((column) => {
                    const cell = cells.find(
                      (one) => one.row_no === row && one.column_no === column,
                    )
                    if (!cell) return <span key={`${rack}-${row}-${column}`} />
                    const picked = cell.code === chosen
                    return (
                      <button
                        key={cell.code}
                        type="button"
                        onClick={() => onChoose(picked ? "" : cell.code)}
                        title={`${cell.code} · ${cell.units} dona`}
                        className={cn(
                          "rounded-control border py-1.5 text-center text-micro tabular",
                          picked && "border-brand bg-brand text-brand-ink",
                          !picked && cell.code === suggested && "border-brand bg-brand-soft",
                          !picked && cell.code !== suggested && cell.units === 0
                            && "border-dashed text-ink-faint",
                          !picked && cell.code !== suggested && cell.units > 0 && "bg-canvas",
                        )}
                      >
                        <span className="block font-medium">{cell.code.slice(2)}</span>
                        <span className="block opacity-70">{cell.units || "bo'sh"}</span>
                      </button>
                    )
                  }),
                ])}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// -------------------------------------------------------------- and it is in

function Booked({
  pile,
  onAnotherColour,
  onAnotherCell,
  onDone,
}: {
  pile: BookedPile
  onAnotherColour: () => void
  onAnotherCell: () => void
  onDone: () => void
}) {
  return (
    <div className="space-y-3 rounded-panel border border-good bg-good-soft p-3">
      <div className="flex items-start gap-2">
        <Check className="mt-0.5 size-5 shrink-0 text-good" />
        <div className="min-w-0">
          <div className="text-body font-semibold">{pile.product.title}</div>
          <div className="text-small text-ink-soft">
            {units(pile.quantity)} · {pile.location_code} · {money(pile.total_cost)}
          </div>
        </div>
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

      {/* Two ways on, because a sack has two ways of not being finished: it
          holds another colour, or this colour did not fit one cell. */}
      <div className="space-y-2">
        <Button className="h-control-lg w-full gap-2" onClick={onAnotherColour}>
          <Plus className="size-5" />
          Shu qopdan yana bir rang
        </Button>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            className="h-control flex-1"
            onClick={onAnotherCell}
          >
            Qolganini boshqa yacheykaga
          </Button>
          <Button variant="ghost" className="h-control" onClick={onDone}>
            Tugadi
          </Button>
        </div>
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

  const waiting = drafts.data?.length ?? 0

  return (
    <section className="rounded-panel border bg-surface p-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-baseline justify-between"
      >
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
                { sacks: Number(sacks) || 1, place: place.trim(), transport_cost: 0 },
                { onSuccess: () => setSacks("1") },
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
                className="h-control tabular"
              />
            </label>
            <label className="min-w-32 flex-1">
              <span className="mb-1 block text-micro text-ink-soft">Qayerdan</span>
              <Input
                value={place}
                onChange={(event) => setPlace(event.target.value)}
                placeholder="Chorsu"
                aria-label="Qop qayerdan"
                className="h-control"
              />
            </label>
            <Button type="submit" variant="secondary" className="h-control">
              Keldi
            </Button>
          </form>

          {waiting === 0 ? <Empty what="Hamma qop saralangan." /> : null}

          <ul className="space-y-2">
            {(drafts.data ?? []).map((sack) => (
              <Sack key={sack.id} sack={sack} />
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

function Sack({
  sack,
}: {
  sack: { id: number; code: string; place: string; age_minutes: number }
}) {
  const sorted = useSackSorted(sack.id)
  const overnight = sack.age_minutes >= OVERNIGHT_MINUTES

  return (
    <li
      className={cn(
        "flex items-center gap-2 rounded-control border p-2",
        overnight && "border-danger bg-danger-soft",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-small font-medium">
          {sack.code} · {sack.place || "joyi yozilmagan"}
        </div>
        <div className={cn("text-micro tabular", overnight ? "text-danger" : "text-ink-faint")}>
          {age(sack.age_minutes)} turgan
        </div>
      </div>
      <Button
        variant="ghost"
        size="sm"
        disabled={sorted.isPending}
        onClick={() => sorted.mutate()}
      >
        {sorted.isPending ? <Loader2 className="size-4 animate-spin" /> : <X className="size-4" />}
        Saralandi
      </Button>
    </li>
  )
}
