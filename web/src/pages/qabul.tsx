/**
 * Qabul — the receiving desk, in two stages.
 *
 * They are apart because the van arrives at nine in the evening and sorting
 * five sacks that night is not going to happen. The alternative — waiting
 * until somebody has time — is goods in the building that the system has
 * never heard of.
 *
 * **Stage one is thirty seconds.** How many sacks, where from, what the
 * transport cost. The sacks now stand in `QABUL` as drafts and the dashboard
 * starts counting their age.
 *
 * **Stage two is the sorting.** Open a sack, separate by colour and size,
 * count each pile, price it. The product field **searches the existing cards
 * first**: typing "krossovka" shows the cards that match, and choosing one
 * means entering only a quantity and a cost. "Yangi karta" is there and is
 * deliberately the second option, because the same goods arriving a second
 * time as a third new card is how a catalogue rots.
 *
 * Closing the run is what brings the goods into existence.
 */

import { Check, Plus, Search, Trash2, X } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { PhotoStep } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, money } from "@/lib/format"
import {
  useAddImage,
  useCancelRun,
  useCategories,
  useCreateProduct,
  useProducts,
  usePublish,
  useReceiveRun,
  useSetGrid,
  useSortRun,
  useStartRun,
  useSupplies,
  useSupply,
  useVariants,
} from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

// A sack that has stood this long is the thing this shop actually loses money
// on: goods in the building that nothing has heard of.
const OVERNIGHT_MINUTES = 14 * 60

type Line = {
  variant_id: number
  label: string
  product_title: string
  quantity: number
  unit_cost: number
}

export function QabulPage() {
  const [openId, setOpenId] = useState<number | null>(null)
  if (openId) return <Sorting id={openId} onBack={() => setOpenId(null)} />
  return <Arrivals onOpen={setOpenId} />
}

// ------------------------------------------------------------------ stage one

function Arrivals({ onOpen }: { onOpen: (id: number) => void }) {
  const drafts = useSupplies("draft")
  const everything = useSupplies()
  const start = useStartRun()
  const [sacks, setSacks] = useState("1")
  const [place, setPlace] = useState("")
  const [transport, setTransport] = useState("")

  // Autocomplete from previous runs: a market is not an entity anybody
  // maintains, and this is what keeps it spelt the same way twice.
  const places = useMemo(() => {
    const seen = new Set<string>()
    for (const run of everything.data ?? []) if (run.place) seen.add(run.place)
    return [...seen].slice(0, 8)
  }, [everything.data])

  return (
    <div className="space-y-4">
      <PageHeader title="Qabul" subtitle="Qoplar keldi — o'ttiz soniya" />

      <form
        onSubmit={(event) => {
          event.preventDefault()
          start.mutate(
            {
              sacks: Number(sacks) || 1,
              place: place.trim(),
              transport_cost: Number(transport) || 0,
            },
            {
              onSuccess: () => {
                setSacks("1")
                setTransport("")
              },
            },
          )
        }}
        className="grid gap-3 rounded-panel border bg-surface p-3 sm:grid-cols-4"
      >
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Nechta qop</span>
          <Input
            value={sacks}
            onChange={(event) => setSacks(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            aria-label="Nechta qop"
            className="h-control-lg tabular text-body"
          />
        </label>
        <label className="sm:col-span-2">
          <span className="mb-1 block text-micro text-ink-soft">Qayerdan</span>
          <Input
            value={place}
            onChange={(event) => setPlace(event.target.value)}
            list="places"
            placeholder="Chorsu"
            aria-label="Qayerdan"
            className="h-control-lg text-body"
          />
          <datalist id="places">
            {places.map((one) => (
              <option key={one} value={one} />
            ))}
          </datalist>
        </label>
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Yo'l xarajati</span>
          <Input
            value={transport}
            onChange={(event) => setTransport(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="0"
            aria-label="Yo'l xarajati"
            className="h-control-lg tabular text-body"
          />
        </label>
        <Button
          type="submit"
          disabled={start.isPending}
          className="h-control-lg sm:col-span-4"
        >
          Qoplarni qayd etish
        </Button>
      </form>

      <Problem error={start.error || drafts.error} />
      {drafts.isLoading ? <Waiting what="Qoplar" /> : null}
      {drafts.data?.length === 0 ? <Empty what="Saralanmagan qop yo'q." /> : null}

      <ul className="space-y-2">
        {(drafts.data ?? []).map((run) => (
          <li key={run.id}>
            <button
              type="button"
              onClick={() => onOpen(run.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-panel border bg-surface p-3 text-left",
                run.age_minutes >= OVERNIGHT_MINUTES && "border-danger bg-danger-soft",
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="text-body font-semibold tabular">{run.code}</div>
                <div className="text-small text-ink-soft">
                  {run.place || "joyi yozilmagan"} · {run.buyer}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-small font-medium">{age(run.age_minutes)}</div>
                <div className="text-micro text-ink-faint">turibdi</div>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ------------------------------------------------------------------ stage two

function Sorting({ id, onBack }: { id: number; onBack: () => void }) {
  const run = useSupply(id)
  const sort = useSortRun(id)
  const receive = useReceiveRun(id)
  const cancel = useCancelRun(id)
  const [edited, setEdited] = useState<Line[] | null>(null)
  const [adding, setAdding] = useState(false)

  const lines: Line[] =
    edited ??
    (run.data?.lines ?? []).map((line) => ({
      variant_id: line.variant_id,
      label: line.variant_label,
      product_title: line.product_title,
      quantity: line.quantity,
      unit_cost: line.unit_cost,
    }))

  const total =
    lines.reduce((sum, line) => sum + line.quantity * line.unit_cost, 0) +
    (run.data?.transport_cost ?? 0)

  function save(next: Line[]) {
    setEdited(next)
    sort.mutate({
      lines: next.map((line) => ({
        variant_id: line.variant_id,
        quantity: line.quantity,
        unit_cost: line.unit_cost,
      })),
    })
  }

  function edit(variantId: number, patch: Partial<Line>) {
    save(
      lines.map((one) => (one.variant_id === variantId ? { ...one, ...patch } : one)),
    )
  }

  if (run.isLoading) return <Waiting what="Qop" />
  if (!run.data) return <Problem error={run.error} />

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${run.data.code} — saralash`}
        subtitle={`${run.data.place || "joyi yozilmagan"} · ${age(run.data.age_minutes)} turgan`}
      >
        <Button variant="ghost" onClick={onBack}>
          Orqaga
        </Button>
      </PageHeader>

      <Problem error={sort.error || receive.error || cancel.error} />

      {lines.length === 0 && !adding ? (
        <Empty what="Qopni to'kib, har bir uyumni alohida yozing." />
      ) : null}

      <ul className="space-y-2">
        {lines.map((line) => (
          <li
            key={line.variant_id}
            className="flex items-center gap-2 rounded-panel border bg-surface p-3"
          >
            <div className="min-w-0 flex-1">
              <div className="truncate text-body font-semibold">{line.product_title}</div>
              <div className="text-small text-ink-soft">{line.label}</div>
            </div>
            <label className="w-20 shrink-0">
              <span className="mb-0.5 block text-micro text-ink-faint">dona</span>
              <Input
                value={String(line.quantity)}
                inputMode="numeric"
                aria-label="Nechta"
                onChange={(event) =>
                  edit(line.variant_id, {
                    quantity: Number(event.target.value.replace(/\D/g, "")) || 0,
                  })
                }
                className="h-control tabular"
              />
            </label>
            <label className="w-28 shrink-0">
              <span className="mb-0.5 block text-micro text-ink-faint">tannarx</span>
              <Input
                value={String(line.unit_cost)}
                inputMode="numeric"
                aria-label="Tannarx"
                onChange={(event) =>
                  edit(line.variant_id, {
                    unit_cost: Number(event.target.value.replace(/\D/g, "")) || 0,
                  })
                }
                className="h-control tabular"
              />
            </label>
            <Button
              variant="ghost"
              size="sm"
              aria-label="O'chirish"
              onClick={() => save(lines.filter((one) => one.variant_id !== line.variant_id))}
            >
              <Trash2 className="size-4" />
            </Button>
          </li>
        ))}
      </ul>

      {adding ? (
        <AddLine
          onCancel={() => setAdding(false)}
          onAdd={(added) => {
            setAdding(false)
            save([...lines.filter((one) => one.variant_id !== added.variant_id), added])
          }}
        />
      ) : (
        <Button
          variant="secondary"
          className="h-control-lg w-full gap-2"
          onClick={() => setAdding(true)}
        >
          <Plus className="size-5" />
          Uyum qo'shish
        </Button>
      )}

      <div className="rounded-panel border bg-surface p-3">
        <div className="flex items-baseline justify-between">
          <span className="text-small text-ink-soft">Safar qiymati</span>
          <span className="figure">{money(total)}</span>
        </div>
        <div className="text-micro text-ink-faint">
          tovar + yo'l ({money(run.data.transport_cost)})
        </div>
        <Button
          className="mt-3 h-control-lg w-full gap-2 text-body"
          disabled={receive.isPending || lines.length === 0}
          onClick={() => receive.mutate(undefined, { onSuccess: onBack })}
        >
          <Check className="size-5" />
          Qabul qilish
        </Button>
        <Button
          variant="ghost"
          className="mt-2 h-control w-full text-danger"
          disabled={cancel.isPending}
          onClick={() => {
            const reason = window.prompt("Nega qabul qilinmayapti?")
            if (reason) cancel.mutate(reason, { onSuccess: onBack })
          }}
        >
          Qopni bekor qilish
        </Button>
      </div>
    </div>
  )
}

// -------------------------------------------------------- what is in the pile

function AddLine({
  onAdd,
  onCancel,
}: {
  onAdd: (line: Line) => void
  onCancel: () => void
}) {
  const [needle, setNeedle] = useState("")
  const [chosen, setChosen] = useState<AdminProduct | null>(null)
  const [writing, setWriting] = useState(false)
  // Drafts included: a card waiting on a photograph is exactly the card
  // somebody is about to bring more of.
  const found = useProducts(needle, "")

  if (writing) {
    return (
      <NewCard onCancel={() => setWriting(false)} onWritten={setChosen} />
    )
  }
  if (chosen) {
    return <PickVariant product={chosen} onAdd={onAdd} onBack={() => setChosen(null)} />
  }

  return (
    <div className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-small font-semibold">Bu nima?</h2>
        <Button variant="ghost" size="sm" onClick={onCancel} aria-label="Yopish">
          <X className="size-4" />
        </Button>
      </div>

      <div className="relative">
        <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
        <Input
          autoFocus
          value={needle}
          onChange={(event) => setNeedle(event.target.value)}
          placeholder="Mavjud kartani qidiring — krossovka…"
          aria-label="Mahsulot qidirish"
          className="h-control-lg pl-8 text-body"
        />
      </div>

      {found.data?.items.length ? (
        <ul className="divide-y">
          {found.data.items.slice(0, 8).map((product) => (
            <li key={product.id}>
              <button
                type="button"
                onClick={() => setChosen(product)}
                className="flex w-full items-center gap-3 py-2 text-left"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate text-small font-medium">{product.title}</div>
                  <div className="text-micro tabular text-ink-faint">
                    {product.sku} · {product.variant_count} variant
                    {product.status === "draft" ? " · rasmsiz" : ""}
                  </div>
                </div>
                <span className="tabular text-small">{money(product.price)}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {needle.trim() && found.data?.items.length === 0 ? (
        <p className="text-small text-ink-soft">Bunday karta yo'q.</p>
      ) : null}

      {/* Deliberately second: the same goods arriving again as a third new
          card is how a catalogue rots. */}
      <Button
        variant="secondary"
        className="h-control w-full"
        onClick={() => setWriting(true)}
      >
        Yangi karta
      </Button>
    </div>
  )
}

function PickVariant({
  product,
  onAdd,
  onBack,
}: {
  product: AdminProduct
  onAdd: (line: Line) => void
  onBack: () => void
}) {
  const grid = useVariants(product.id)
  const [chosen, setChosen] = useState<number | null>(null)
  const [qty, setQty] = useState("1")
  const [cost, setCost] = useState("")

  const variant = grid.data?.find((one) => one.id === chosen)

  return (
    <div className="space-y-3 rounded-panel border bg-surface p-3">
      <div className="flex items-center justify-between">
        <h2 className="min-w-0 truncate text-small font-semibold">{product.title}</h2>
        <Button variant="ghost" size="sm" onClick={onBack}>
          Boshqasi
        </Button>
      </div>

      {grid.isLoading ? <Waiting what="Variantlar" /> : null}
      {grid.data?.length === 0 ? (
        <Empty what="Bu kartada hali rang/o'lcham yo'q. Kartani tahrirlab, to'rini yarating." />
      ) : null}

      <div className="flex flex-wrap gap-1">
        {(grid.data ?? []).map((one) => (
          <button
            key={one.id}
            type="button"
            onClick={() => {
              setChosen(one.id)
              if (!cost) setCost(String(Math.round(one.price * 0.6)))
            }}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              one.id === chosen && "border-brand bg-brand-soft text-brand-deep",
            )}
          >
            {one.label}
          </button>
        ))}
      </div>

      {variant ? (
        <form
          onSubmit={(event) => {
            event.preventDefault()
            onAdd({
              variant_id: variant.id,
              label: variant.label,
              product_title: product.title,
              quantity: Number(qty) || 1,
              unit_cost: Number(cost) || 0,
            })
          }}
          className="flex flex-wrap items-end gap-2"
        >
          <label className="w-24">
            <span className="mb-1 block text-micro text-ink-soft">Nechta</span>
            <Input
              value={qty}
              onChange={(event) => setQty(event.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
              aria-label="Nechta"
              className="h-control-lg tabular text-body"
            />
          </label>
          <label className="w-32">
            <span className="mb-1 block text-micro text-ink-soft">Tannarx</span>
            <Input
              value={cost}
              onChange={(event) => setCost(event.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
              aria-label="Tannarx"
              className="h-control-lg tabular text-body"
            />
          </label>
          <Button type="submit" className="h-control-lg flex-1">
            Qo'shish
          </Button>
        </form>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------- a card, inline

function NewCard({
  onWritten,
  onCancel,
}: {
  onWritten: (product: AdminProduct) => void
  onCancel: () => void
}) {
  const categories = useCategories()
  const create = useCreateProduct()
  const [title, setTitle] = useState("")
  const [sku, setSku] = useState("")
  const [category, setCategory] = useState("")
  const [price, setPrice] = useState("")
  const [colours, setColours] = useState("")
  const [sizes, setSizes] = useState("")
  const [written, setWritten] = useState<AdminProduct | null>(null)

  if (written) {
    return (
      <Photographs
        product={written}
        colours={split(colours)}
        sizes={split(sizes)}
        onDone={() => onWritten(written)}
      />
    )
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        create.mutate(
          {
            sku: sku.trim().toUpperCase(),
            title: title.trim(),
            category_slug: category,
            price: Number(price) || 0,
          },
          { onSuccess: setWritten },
        )
      }}
      className="space-y-3 rounded-panel border bg-surface p-3"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-small font-semibold">Yangi karta</h2>
        <Button variant="ghost" size="sm" onClick={onCancel} aria-label="Yopish">
          <X className="size-4" />
        </Button>
      </div>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">Nomi</span>
        <Input
          autoFocus
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Krossovka Alfa"
          aria-label="Nomi"
          className="h-control-lg text-body"
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-3">
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Kod (SKU)</span>
          <Input
            value={sku}
            onChange={(event) => setSku(event.target.value.toUpperCase())}
            placeholder="KRS-01"
            aria-label="SKU"
            className="h-control tabular"
          />
        </label>
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Kategoriya</span>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            aria-label="Kategoriya"
            className="h-control w-full rounded-control border bg-surface px-2 text-small"
          >
            <option value="">tanlang</option>
            {(categories.data ?? []).map((one) => (
              <option key={one.slug} value={one.slug}>
                {one.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="mb-1 block text-micro text-ink-soft">Sotuv narxi</span>
          <Input
            value={price}
            onChange={(event) => setPrice(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            aria-label="Narx"
            className="h-control tabular"
          />
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          <span className="mb-1 block text-micro text-ink-soft">
            Ranglar — vergul bilan
          </span>
          <Input
            value={colours}
            onChange={(event) => setColours(event.target.value)}
            placeholder="Qora, Oq"
            aria-label="Ranglar"
            className="h-control"
          />
        </label>
        <label>
          <span className="mb-1 block text-micro text-ink-soft">
            O'lchamlar — vergul bilan
          </span>
          <Input
            value={sizes}
            onChange={(event) => setSizes(event.target.value)}
            placeholder="41, 42, 43"
            aria-label="O'lchamlar"
            className="h-control"
          />
        </label>
      </div>
      <p className="text-micro text-ink-faint">
        Rang × o'lcham to'ri bir qadamda yaratiladi — {split(colours).length || 1} ×{" "}
        {split(sizes).length || 1} ={" "}
        {(split(colours).length || 1) * (split(sizes).length || 1)} variant.
      </p>

      <Problem error={create.error} />

      <Button
        type="submit"
        disabled={create.isPending || !title.trim() || !sku.trim() || !category}
        className="h-control-lg w-full"
      >
        Kartani yaratish
      </Button>
    </form>
  )
}

function Photographs({
  product,
  colours,
  sizes,
  onDone,
}: {
  product: AdminProduct
  colours: string[]
  sizes: string[]
  onDone: () => void
}) {
  const grid = useSetGrid(product.id)
  const image = useAddImage(product.id)
  const publish = usePublish(product.id)
  const [taken, setTaken] = useState<Record<string, string>>({})

  // The grid, once, as soon as there is a card to hang it on. In an effect
  // rather than in the render, because a mutation fired while React is
  // rendering is a mutation fired twice under StrictMode.
  const built = useRef(false)
  useEffect(() => {
    if (built.current) return
    built.current = true
    grid.mutate({
      colours: colours.map((colour) => ({ colour, hex: "" })),
      sizes,
      price: product.price,
    })
    // Once per card. The inputs are captured when the card is written and do
    // not change while this screen is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const wanted = colours.length ? colours : [""]
  const missing = wanted.filter((colour) => !taken[colour])

  return (
    <div className="space-y-3 rounded-panel border bg-surface p-3">
      <h2 className="text-small font-semibold">{product.title} — rasm</h2>

      <PhotoStep
        colours={wanted}
        taken={taken}
        onTaken={(colour, url) => {
          setTaken((was) => ({ ...was, [colour]: url }))
          image.mutate({ url, colour })
        }}
      />

      <Problem error={grid.error || image.error || publish.error} />

      <Button
        className="h-control-lg w-full"
        disabled={image.isPending}
        onClick={() => {
          // Only when every colour has one. The server refuses otherwise, and
          // asking it to refuse is how the person finds out on the wrong
          // screen.
          if (!missing.length) publish.mutate("active", { onSuccess: onDone })
          else onDone()
        }}
      >
        {missing.length ? "Rasmsiz davom etish" : "Sotuvga chiqarish va davom etish"}
      </Button>
    </div>
  )
}

function split(value: string): string[] {
  return value
    .split(",")
    .map((one) => one.trim())
    .filter(Boolean)
}
