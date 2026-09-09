/**
 * Qabul — a pile off the van, booked in and shelved in one action.
 *
 * The screen this replaced had a dead end in it. Writing a card needed a
 * category, the categories start empty on purpose, and the warehouse role
 * cannot write one — so the button was never going to enable, and the person
 * who found that out was the owner with two sacks on the floor. It also asked
 * for the goods one variant at a time: four of a size, then back round the
 * loop for the next, twelve times for a sack of shoes.
 *
 * So the two jobs are apart now. **Getting goods onto a shelf** is physical,
 * urgent, and done with the sack open — that is this screen, and it asks for
 * the six things somebody standing at a bench actually knows. **Getting them
 * into the shop** is desk work in daylight — that is `/sotuvga-chiqarish`,
 * and nothing here waits for it.
 *
 * Three things this form does deliberately:
 *
 * **It is one row, not a matrix.** A sack from the market is usually one
 * thing — only black trainers, only white shirts. A second colour is the form
 * filled in twice, which keeps the kind, the make, the cell and the cost.
 *
 * **It saves nothing until you submit it.** The old one wrote to the server on
 * every keystroke, which deleted and reinserted every line each time; clearing
 * a quantity to retype it produced a red error, and out-of-order responses
 * could lose the figure you had just typed.
 *
 * **Counts add.** Four of a size and then two more found in the bottom of the
 * sack is six. The old screen replaced the earlier line and said nothing.
 */

import { Check, Loader2, Package, Plus, Search, Sparkles, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Capture, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, money } from "@/lib/format"
import {
  useBookInPile,
  useLocation,
  useProducts,
  useSackSorted,
  useStartRun,
  useSupplies,
  useVariants,
  useVocab,
} from "@/lib/queries"
import type { AdminProduct, Pile, PileSize } from "@/lib/types"

// A sack that has stood this long is the thing this shop actually loses money
// on: goods in the building that nothing has heard of.
const OVERNIGHT_MINUTES = 14 * 60

export function QabulPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="Qabul" subtitle="Tavar keldi — nima, nechta, qaysi javonga" />
      <PileForm />
      <Sacks />
    </div>
  )
}

// --------------------------------------------------------------------- the form

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
}

function PileForm() {
  const vocab = useVocab()
  const book = useBookInPile()
  // Spelt the same way twice. A market is not an entity anybody maintains, so
  // the list is simply the ones already written down.
  const runs = useSupplies()
  const places = useMemo(() => {
    const seen = new Set<string>()
    for (const run of runs.data ?? []) if (run.place) seen.add(run.place)
    return [...seen].slice(0, 10)
  }, [runs.data])
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [booked, setBooked] = useState<Pile | null>(null)

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((was) => ({ ...was, [key]: value }))

  // Sizes offered for this kind: what it last arrived in. Nobody configures a
  // size list before receiving anything, and the market brings what it brings.
  const remembered = vocab.data?.sizes[draft.kind] ?? []
  const lines: PileSize[] = Object.entries(draft.sizes)
    .map(([size, qty]) => ({ size, quantity: Number(qty) || 0 }))
    .filter((line) => line.quantity > 0)

  const named = Boolean(draft.product) || Boolean(draft.kind.trim())
  const ready = named && lines.length > 0 && Number(draft.unitCost) > 0

  if (booked) {
    return (
      <Booked
        pile={booked}
        onAgain={() => {
          // The kind, the make, the cell and the cost survive: the next pile
          // out of the same sack is usually the same goods in another colour.
          setBooked(null)
          setDraft((was) => ({ ...was, colour: "", sizes: {}, snapshot: "" }))
        }}
        onDone={() => {
          setBooked(null)
          setDraft(EMPTY)
        }}
      />
    )
  }

  return (
    <form
      className="space-y-4 rounded-panel border bg-surface p-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (!ready) return
        book.mutate(
          {
            product_id: draft.product?.id,
            kind: draft.kind.trim(),
            brand: draft.brand.trim(),
            colour: draft.colour.trim(),
            snapshot_url: draft.snapshot,
            sizes: lines,
            unit_cost: Number(draft.unitCost),
            location_code: draft.cell.trim().toUpperCase(),
            place: draft.place.trim(),
          },
          { onSuccess: setBooked },
        )
      }}
    >
      <Identify
        draft={draft}
        vocab={vocab.data}
        onPick={(product) =>
          setDraft((was) => ({
            ...was,
            product,
            kind: product?.kind ?? was.kind,
            colour: "",
            sizes: {},
          }))
        }
        onSet={set}
      />

      <Sizes
        remembered={remembered}
        sizes={draft.sizes}
        product={draft.product}
        colour={draft.colour}
        onSet={(sizes) => set("sizes", sizes)}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className="mb-1 block text-micro text-ink-soft">
            Tannarx — bir dona
          </span>
          <Input
            value={draft.unitCost}
            onChange={(event) => set("unitCost", event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="85000"
            aria-label="Tannarx"
            className="h-control-lg tabular text-body"
          />
          <span className="mt-1 block text-micro text-ink-faint">
            Hozir yozilmasa kechga borib esdan chiqadi — foyda hisoblanmaydi
          </span>
        </label>
        <Cell code={draft.cell} onSet={(code) => set("cell", code)} />
      </div>

      {/* Optional, and it stays filled between piles. Nobody delivers to us —
          the owner buys at the market — so this is not a supplier, it is where
          it was bought. Three months on it is the only thing that answers
          "which stall does the damaged stock keep coming from". */}
      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Qayerdan — majburiy emas
        </span>
        <Input
          value={draft.place}
          onChange={(event) => set("place", event.target.value)}
          placeholder="Chorsu"
          aria-label="Qayerdan"
          list="mb-places"
          className="h-control"
        />
        <datalist id="mb-places">
          {places.map((one) => (
            <option key={one} value={one} />
          ))}
        </datalist>
      </label>

      <Problem error={book.error} />

      <div className="flex items-baseline justify-between text-small">
        <span className="text-ink-soft">
          {lines.reduce((sum, line) => sum + line.quantity, 0)} dona
        </span>
        <span className="figure">
          {money(
            lines.reduce((sum, line) => sum + line.quantity, 0) *
              (Number(draft.unitCost) || 0),
          )}
        </span>
      </div>

      <Button
        type="submit"
        disabled={!ready || book.isPending}
        className="h-control-lg w-full gap-2 text-body"
      >
        {book.isPending ? (
          <Loader2 className="size-5 animate-spin" />
        ) : (
          <Check className="size-5" />
        )}
        {draft.cell.trim() ? "Javonga qo'ydim" : "QABULga qo'ydim"}
      </Button>
      {!ready ? (
        <p className="text-center text-micro text-ink-faint">
          {!named
            ? "Tavar nomi kerak"
            : lines.length === 0
              ? "Nechta kelganini yozing"
              : "Tannarx kerak"}
        </p>
      ) : null}
    </form>
  )
}

// ------------------------------------------------------------ what is this?

function Identify({
  draft,
  vocab,
  onPick,
  onSet,
}: {
  draft: Draft
  vocab: { kinds: string[]; brands: string[]; colours: string[] } | undefined
  onPick: (product: AdminProduct | null) => void
  onSet: <K extends keyof Draft>(key: K, value: Draft[K]) => void
}) {
  const [needle, setNeedle] = useState("")
  const found = useProducts(needle, "")

  if (draft.product) {
    return (
      <div className="space-y-2 rounded-control border border-brand bg-brand-soft p-2">
        <div className="flex items-center gap-3">
          <Thumb product={draft.product} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-body font-semibold">{draft.product.title}</div>
            <div className="text-micro tabular text-ink-soft">
              {draft.product.sku} · {draft.product.variant_count} variant
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onPick(null)
              setNeedle("")
            }}
          >
            Boshqasi
          </Button>
        </div>
        {/* Which colour of it arrived. Required, and it is the card's own
            colours rather than a free field: leaving it empty would write a
            colourless cell beside the ones that exist and put the count on a
            variant nobody is ever going to pick from. */}
        <OwnColours
          product={draft.product}
          value={draft.colour}
          onChange={(colour) => onSet("colour", colour)}
        />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Search first, and it shows the photograph — two black trainers of
          different makes look identical in a list of names, and picking the
          wrong one puts Adidas stock on the Nike card. */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
        <Input
          value={needle}
          onChange={(event) => setNeedle(event.target.value)}
          placeholder="Bor tavarmi? — nom yoki kod"
          aria-label="Mavjud kartani qidirish"
          className="h-control-lg pl-8 text-body"
        />
      </div>

      {/* With nothing typed this is the recently received, which is the
          "same sack again?" shortcut: the second colour out of one sack, or the
          same goods arriving next month, is a tap rather than a search. */}
      {found.data?.items.length && !needle.trim() ? (
        <p className="text-micro text-ink-soft">Oxirgi kartalar</p>
      ) : null}

      {found.data?.items.length ? (
        <ul className="divide-y rounded-control border">
          {found.data.items.slice(0, 6).map((product) => (
            <li key={product.id}>
              <button
                type="button"
                onClick={() => onPick(product)}
                className="flex w-full items-center gap-3 p-2 text-left"
              >
                <Thumb product={product} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-small font-medium">{product.title}</div>
                  <div className="text-micro tabular text-ink-faint">
                    {product.sku} · {product.stock_left} dona
                    {product.status === "draft" ? " · do'konda yo'q" : ""}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {needle.trim().length > 1 && found.data?.items.length === 0 ? (
        <p className="text-small text-ink-soft">
          Bunday karta yo'q — pastda yangisini yozing.
        </p>
      ) : null}

      <div className="space-y-2 rounded-control border border-dashed p-2">
        <p className="text-micro text-ink-soft">
          Yangi tavar — bosib tanlang, yozish shart emas
        </p>
        <Chips
          label="Tur"
          options={vocab?.kinds ?? []}
          value={draft.kind}
          onChange={(value) => onSet("kind", value)}
          placeholder="Krossovka"
        />
        <Chips
          label="Brend"
          options={vocab?.brands ?? []}
          value={draft.brand}
          onChange={(value) => onSet("brand", value)}
          placeholder="Nike"
          none="brendsiz"
        />
        <Chips
          label="Rang"
          options={vocab?.colours ?? []}
          value={draft.colour}
          onChange={(value) => onSet("colour", value)}
          placeholder="Qora"
        />

        {draft.kind.trim() ? (
          <div className="pt-1">
            <p className="mb-1 text-micro text-ink-soft">
              Tanish rasmi — qopning ustida, ikki soniya
            </p>
            <Capture
              colour=""
              current={draft.snapshot || undefined}
              onTaken={(_, url) => onSet("snapshot", url)}
              guide="mijozga ko'rinmaydi — faqat tanish uchun"
              placeholder="rasm"
            />
            <p className="mt-1 text-micro text-ink-faint">
              Bo'sh qoldirsangiz ham javonga qo'yiladi. Katalog rasmi keyin,
              yorug'likda olinadi.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

/**
 * The colours this card already has, one of which arrived.
 *
 * Auto-selected when there is only one, because then it is not a question —
 * and a question with one answer on a form is a tap somebody has to make for
 * no reason.
 */
function OwnColours({
  product,
  value,
  onChange,
}: {
  product: AdminProduct
  value: string
  onChange: (colour: string) => void
}) {
  const grid = useVariants(product.id)
  const colours = useMemo(() => {
    const seen = new Set((grid.data ?? []).map((cell) => cell.colour))
    return [...seen]
  }, [grid.data])

  const only = colours.length === 1 ? colours[0] : null
  useEffect(() => {
    if (only !== null && value !== only) onChange(only)
    // Once, when the card's colours arrive.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [only])

  if (grid.isLoading || colours.length <= 1) return null

  return (
    <div>
      <span className="mb-1 block text-micro text-ink-soft">Qaysi rang keldi</span>
      <div className="flex flex-wrap gap-1">
        {colours.map((one) => (
          <button
            key={one}
            type="button"
            onClick={() => onChange(one)}
            className={cn(
              "h-control rounded-control border bg-surface px-3 text-small",
              one === value && "border-brand bg-brand text-brand-ink",
            )}
          >
            {one || "rangsiz"}
          </button>
        ))}
      </div>
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

/**
 * A chip row that grows. Everything received before, most-used first, and a
 * field for one that has not been. "On Cloud" is typed once and is a chip from
 * then on, because a market brings whatever it brings and no list drawn up
 * beforehand survives contact with it.
 */
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
  // Most-used first from the server, and a search once there are too many to
  // read at a glance.
  const [filter, setFilter] = useState("")
  const shown = filter.trim()
    ? options.filter((one) => one.toLowerCase().includes(filter.trim().toLowerCase()))
    : options.slice(0, 12)

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-micro text-ink-soft">{label}</span>
        {value ? <span className="text-micro font-medium">{value}</span> : null}
      </div>
      <div className="flex flex-wrap gap-1">
        {shown.map((one) => (
          <button
            key={one}
            type="button"
            onClick={() => onChange(one === value ? "" : one)}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              one === value && "border-brand bg-brand-soft text-brand-deep",
            )}
          >
            {one}
          </button>
        ))}
        {none ? (
          <button
            type="button"
            onClick={() => onChange("")}
            className={cn(
              "h-control rounded-control border border-dashed px-3 text-small text-ink-soft",
              !value && "border-brand text-brand-deep",
            )}
          >
            {none}
          </button>
        ) : null}
        {writing ? (
          <Input
            autoFocus
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onBlur={() => setWriting(false)}
            placeholder={placeholder}
            aria-label={label}
            className="h-control w-36"
          />
        ) : (
          <button
            type="button"
            onClick={() => setWriting(true)}
            className="h-control gap-1 rounded-control border border-dashed px-3 text-small text-brand-deep"
          >
            + yangi
          </button>
        )}
      </div>
      {options.length > 12 && !filter ? (
        <button
          type="button"
          onClick={() => setFilter(" ")}
          className="mt-1 text-micro text-brand-deep"
        >
          yana {options.length - 12} ta…
        </button>
      ) : null}
      {filter ? (
        <Input
          autoFocus
          value={filter.trim()}
          onChange={(event) => setFilter(event.target.value || " ")}
          placeholder={`${label} qidirish`}
          aria-label={`${label} qidirish`}
          className="mt-1 h-control"
        />
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------ how many

function Sizes({
  remembered,
  sizes,
  product,
  colour,
  onSet,
}: {
  remembered: string[]
  sizes: Record<string, string>
  product: AdminProduct | null
  colour: string
  onSet: (sizes: Record<string, string>) => void
}) {
  const [adding, setAdding] = useState("")
  const [sizeless, setSizeless] = useState(false)

  // What this card already holds, per colour and size, so that a second count
  // of the same size reads as an addition rather than looking like a figure
  // about to be overwritten. The screen this replaced overwrote it silently.
  const grid = useVariants(product?.id ?? null)
  const already = useMemo(() => {
    const map = new Map<string, number>()
    for (const cell of grid.data ?? []) {
      map.set(`${cell.colour}\u0000${cell.size}`, cell.stock_left)
    }
    return map
  }, [grid.data])

  // A card that already exists brings its own sizes, which beats anything
  // remembered by kind.
  const offered = useMemo(() => {
    const own = (grid.data ?? [])
      .filter((cell) => !colour || cell.colour === colour)
      .map((cell) => cell.size)
    const seen = new Set([...own, ...remembered, ...Object.keys(sizes)])
    seen.delete("")
    return [...seen]
  }, [grid.data, colour, remembered, sizes])

  // Sizes are the default and being sizeless is a choice, not a fallback. It
  // was the other way round for one build: on day one nothing is remembered
  // for any kind, so the first sack of shoes anybody received offered a single
  // quantity box and no sizes at all.
  if (sizeless) {
    return (
      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-micro text-ink-soft">Nechta keldi</span>
          <button
            type="button"
            onClick={() => {
              setSizeless(false)
              onSet({})
            }}
            className="text-micro text-brand-deep"
          >
            o'lchamlari bor
          </button>
        </div>
        <Input
          value={sizes[""] ?? ""}
          onChange={(event) => onSet({ "": event.target.value.replace(/\D/g, "") })}
          inputMode="numeric"
          placeholder="12"
          aria-label="Nechta"
          className="h-control-lg w-28 tabular text-body"
        />
      </div>
    )
  }

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-micro text-ink-soft">O'lchamlar — nechta keldi</span>
        {/* Bags and accessories have none, and asking for one is how a fake
            size gets typed. */}
        <button
          type="button"
          onClick={() => {
            setSizeless(true)
            onSet({})
          }}
          className="text-micro text-brand-deep"
        >
          o'lchamsiz
        </button>
      </div>

      {offered.length === 0 ? (
        <p className="mb-1 text-micro text-ink-faint">
          O'lchamni yozib Enter bosing — 41, keyin 42. Keyingi safar o'zi
          taklif qiladi.
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {offered.map((size) => (
          <SizeBox
            key={size}
            size={size}
            value={sizes[size] ?? ""}
            already={already.get(`${colour}\u0000${size}`) ?? 0}
            onChange={(value) => onSet({ ...sizes, [size]: value })}
          />
        ))}

        <label className="w-24">
          <span className="mb-0.5 block text-center text-micro text-ink-faint">
            + o'lcham
          </span>
          {/* Enter adds it and leaves the caret here, because the first sack of
              a kind means typing 41, 42, 43 one after another. */}
          <Input
            value={adding}
            onChange={(event) => setAdding(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return
              event.preventDefault()
              const size = adding.trim()
              if (size) onSet({ ...sizes, [size]: "" })
              setAdding("")
              event.currentTarget.focus()
            }}
            onBlur={() => {
              const size = adding.trim()
              if (size) onSet({ ...sizes, [size]: "" })
              setAdding("")
            }}
            placeholder="44"
            aria-label="Yangi o'lcham"
            className="h-control-lg text-center"
          />
        </label>
      </div>
    </div>
  )
}

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
  return (
    <label className="w-24">
      <span className="mb-0.5 block text-center text-micro text-ink-soft">{size}</span>
      <Input
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, ""))}
        inputMode="numeric"
        aria-label={`${size} — nechta`}
        className={cn(
          "h-control-lg text-center tabular text-body",
          Number(value) > 0 && "border-brand",
        )}
      />
      {already > 0 && Number(value) > 0 ? (
        <span className="mt-0.5 block text-center text-micro text-ink-faint">
          {already} + {Number(value)} = {already + Number(value)}
        </span>
      ) : null}
    </label>
  )
}

// -------------------------------------------------------------------- the cell

function Cell({ code, onSet }: { code: string; onSet: (code: string) => void }) {
  const typed = code.trim().toUpperCase()
  // Shown as soon as it looks like a cell code, because what is *in* the cell
  // is the check that matters: a valid code for the wrong cell is the mistake
  // a capacity bar cannot catch.
  const cell = useLocation(/^[A-Z]-\d{2}-\d{2}$/.test(typed) ? typed : null)

  return (
    <label className="block">
      <span className="mb-1 block text-micro text-ink-soft">
        Javon — bo'sh qoldirsa QABULda turadi
      </span>
      <Input
        value={code}
        onChange={(event) => onSet(event.target.value.toUpperCase())}
        placeholder="A-03-01"
        aria-label="Javon kodi"
        className="h-control-lg tabular text-body"
      />

      {cell.isLoading ? (
        <span className="mt-1 block text-micro text-ink-faint">tekshirilmoqda…</span>
      ) : null}

      {cell.isError ? (
        <span className="mt-1 block rounded-control bg-danger-soft p-2 text-micro text-danger">
          Bunday yacheyka yo'q. Xaritada bor kodni tekshiring.
        </span>
      ) : null}

      {cell.data ? (
        cell.data.contents.length ? (
          <span className="mt-1 block rounded-control bg-warn-soft p-2 text-micro text-warn-ink">
            Bu yacheykada: <b>{cell.data.contents[0].product_title}</b>
            {cell.data.contents.length > 1
              ? ` va yana ${cell.data.contents.length - 1} xil`
              : ""}
            {" — "}
            {cell.data.contents.reduce((sum, row) => sum + row.qty, 0)} dona
          </span>
        ) : (
          <span className="mt-1 block rounded-control bg-good-soft p-2 text-micro text-good">
            Bo'sh
          </span>
        )
      ) : null}
    </label>
  )
}

// ------------------------------------------------------------------ what to write

function Booked({
  pile,
  onAgain,
  onDone,
}: {
  pile: Pile
  onAgain: () => void
  onDone: () => void
}) {
  return (
    <div className="space-y-3 rounded-panel border border-good bg-good-soft p-3">
      <div className="flex items-start gap-2">
        <Sparkles className="mt-0.5 size-5 shrink-0 text-good" />
        <div className="min-w-0">
          <div className="text-body font-semibold">{pile.product.title}</div>
          <div className="text-small text-ink-soft">
            {pile.quantity} dona · {pile.location_code} · {money(pile.total_cost)}
          </div>
        </div>
      </div>

      {/* The codes, big, because there is no printer yet: they get written on
          the box with a marker. The print button is there for when there is
          one, and nothing about the codes changes when it arrives. */}
      <div className="rounded-control bg-surface p-2">
        <p className="mb-1 text-micro text-ink-soft">
          Qutiga yozib qo'ying — keyin shu kod bilan topiladi
        </p>
        <ul className="space-y-1">
          {pile.labels.map((one) => (
            <li key={one.variant_id} className="flex items-baseline justify-between gap-2">
              <span className="text-small text-ink-soft">{one.variant_label || "—"}</span>
              <span className="tabular text-body font-semibold">{one.sku}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* What is actually missing, from the card that came back — not a
          sentence about the usual case. The second pile of goods that are
          already on sale was being told the shop could not see them. */}
      {pile.product.unready.length ? (
        <p className="text-micro text-ink-soft">
          Do'konda hali yo'q — kerak:{" "}
          {pile.product.unready.map((gap) => gap.label).join(", ")}.{" "}
          <a href="/sotuvga-chiqarish" className="font-medium text-brand-deep underline">
            Sotuvga chiqarish
          </a>
        </p>
      ) : (
        <p className="text-micro text-good">Do'konda ham bor — sotuvda turibdi.</p>
      )}

      <div className="flex gap-2">
        <Button className="h-control-lg flex-1 gap-2" onClick={onAgain}>
          <Plus className="size-5" />
          Shu qopdan yana
        </Button>
        <Button variant="secondary" className="h-control-lg" onClick={onDone}>
          Tugadi
        </Button>
      </div>
    </div>
  )
}

// ------------------------------------------------------- sacks nobody has opened

/**
 * The reminder, and it is only a reminder.
 *
 * Its whole value is the age: goods are standing in the building and nobody
 * knows what they are. Tipping one out produces piles, which go in through the
 * form above — a sack is not one pile, so there is no arrangement of lines on
 * this row that would describe what came out of it. "Saralandi" dismisses it.
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
                aria-label="Qayerdan"
                className="h-control"
              />
            </label>
            <Button type="submit" variant="secondary" className="h-control">
              Keldi
            </Button>
          </form>

          {drafts.isLoading ? <Waiting what="Qoplar" /> : null}
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
