/**
 * Sotuvga chiqarish — the shop window, and it is the seller's screen.
 *
 * Two lists, because there are two ways a card fails a customer and only one
 * of them is visible.
 *
 * **Sotuvga chiqmagan** — goods on a shelf that nobody can buy. Three things
 * are refused until they exist: a category (or nothing browsing finds it), a
 * price (or there is nothing to charge), and a photograph per colour (or the
 * shop shows a grey square). This is money standing still, and nothing about
 * it breaks or errors, which is why it needs a count in the menu.
 *
 * **Yupqa ko'rinadi** — cards that *are* on sale and read like a receipt. The
 * apps hide a block whose field is empty: no description means no description
 * panel rather than an empty one, so a thin card looks sparse rather than
 * broken and nobody ever notices it needs finishing. Hence the second list.
 * None of it is refused — a card with one photograph still sells, and holding
 * it back until the prose is written is how nothing goes on sale at all.
 *
 * The server names both sets: `unready` is the gate, `listing_gaps` is the
 * to-do list, and the browser branches on `gap.key` to decide which control to
 * put in front of somebody rather than keeping its own copy of the rule.
 */

import {
  Camera,
  Check,
  Loader2,
  Package,
  Plus,
  Table2,
  Tags,
  Trash2,
  Wallet,
} from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Capture, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { age, minutesSince, money } from "@/lib/format"
import {
  useAddImage,
  useCategories,
  useFileCard,
  useImages,
  usePriceCard,
  useProduct,
  useProducts,
  usePublish,
  useSpecs,
  useVariants,
  useWriteCategory,
  useWriteSpecs,
} from "@/lib/queries"
import type { AdminProduct, Spec } from "@/lib/types"

// Three days. An afternoon is somebody waiting for daylight; three days is
// goods nobody is going to get round to, costing rent and earning nothing.
const STALE_MINUTES = 3 * 24 * 60

export function PublishPage() {
  const drafts = useProducts("", "draft")
  const live = useProducts("", "active")
  const [open, setOpen] = useState<number | null>(null)

  // Only what is actually on a shelf. A card somebody started and abandoned is
  // not money sitting still, and mixing the two makes the count mean nothing.
  const held = useMemo(
    () =>
      (drafts.data?.items ?? [])
        .filter((card) => card.stock_left > 0)
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [drafts.data],
  )
  const thin = useMemo(
    () => (live.data?.items ?? []).filter((card) => card.listing_gaps.length > 0),
    [live.data],
  )

  const worth = held.reduce((sum, card) => sum + card.stock_left * card.price, 0)

  return (
    <div className="space-y-5">
      <PageHeader title="Sotuvga chiqarish" subtitle="Do'kon vitrinasi" />

      <Problem error={drafts.error || live.error} />
      {drafts.isLoading ? <Waiting what="Navbat" /> : null}

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-small font-semibold">
            Javonda bor, do'konda yo'q
            {held.length ? <span className="tabular"> · {held.length}</span> : null}
          </h2>
          {worth ? (
            <span className="text-micro tabular text-ink-faint">{money(worth)}</span>
          ) : null}
        </div>

        {!drafts.isLoading && held.length === 0 ? (
          <Empty what="Javondagi hamma tovar do'konda ham bor." />
        ) : null}

        <ul className="space-y-2">
          {held.map((card) => (
            <li key={card.id}>
              <Row
                card={card}
                gaps={card.unready}
                urgent
                open={open === card.id}
                onOpen={() => setOpen(open === card.id ? null : card.id)}
              />
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-small font-semibold">
          Sotuvda, lekin yupqa ko'rinadi
          {thin.length ? <span className="tabular"> · {thin.length}</span> : null}
        </h2>
        <p className="text-micro text-ink-faint">
          Ilova bo'sh maydonni yashiradi — sahifa buzilmaydi, faqat quruq
          ko'rinadi. Shuning uchun bu ro'yxat bor.
        </p>

        {!live.isLoading && thin.length === 0 ? (
          <Empty what="Sotuvdagi kartalar to'liq." />
        ) : null}

        <ul className="space-y-2">
          {thin.map((card) => (
            <li key={card.id}>
              <Row
                card={card}
                gaps={card.listing_gaps}
                open={open === card.id}
                onOpen={() => setOpen(open === card.id ? null : card.id)}
              />
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

// ------------------------------------------------------------------- one row

function Row({
  card,
  gaps,
  urgent,
  open,
  onOpen,
}: {
  card: AdminProduct
  gaps: { key: string; label: string }[]
  urgent?: boolean
  open: boolean
  onOpen: () => void
}) {
  const minutes = minutesSince(card.created_at)
  const stale = Boolean(urgent) && minutes >= STALE_MINUTES

  return (
    <div
      className={cn(
        "rounded-panel border bg-surface",
        stale && "border-danger",
        open && "border-brand",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full items-center gap-3 p-3 text-left"
      >
        {card.snapshot_url ? (
          <img
            src={mediaUrl(card.snapshot_url)}
            alt=""
            className="size-12 shrink-0 rounded-control object-cover"
          />
        ) : (
          <span className="grid size-12 shrink-0 place-items-center rounded-control bg-canvas text-ink-faint">
            <Package className="size-5" />
          </span>
        )}

        <div className="min-w-0 flex-1">
          <div className="truncate text-body font-semibold">{card.title}</div>
          <div className="text-micro tabular text-ink-soft">
            {card.stock_left} dona · {card.sku}
            {card.price ? ` · ${money(card.price)}` : ""}
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {gaps.map((gap) => (
              <span
                key={gap.key}
                className={cn(
                  "rounded-control px-1.5 py-0.5 text-micro",
                  urgent ? "bg-warn-soft text-warn-ink" : "bg-canvas text-ink-soft",
                )}
              >
                {gap.label}
              </span>
            ))}
          </div>
        </div>

        {urgent ? (
          <span
            className={cn(
              "shrink-0 text-micro tabular",
              stale ? "font-semibold text-danger" : "text-ink-faint",
            )}
          >
            {age(minutes)}
          </span>
        ) : null}
      </button>

      {open ? <Editor card={card} /> : null}
    </div>
  )
}

// ------------------------------------------------------------------ the editor

function Editor({ card }: { card: AdminProduct }) {
  const gate = new Set(card.unready.map((gap) => gap.key))
  const publish = usePublish(card.id)

  return (
    <div className="space-y-5 border-t p-3">
      {gate.size ? (
        <div className="space-y-4">
          <h3 className="text-micro font-semibold uppercase tracking-wide text-warn-ink">
            Sotuvga chiqishi uchun
          </h3>
          {gate.has("needs_photo") ? <Photos card={card} /> : null}
          {gate.has("needs_category") ? <Filing card={card} /> : null}
          {gate.has("needs_price") ? <Pricing card={card} /> : null}

          <Problem error={publish.error} />
        </div>
      ) : card.next_statuses.includes("active") ? (
        <>
          <Problem error={publish.error} />
          <Button
            className="h-control-lg w-full gap-2 text-body"
            disabled={publish.isPending}
            onClick={() => publish.mutate("active")}
          >
            {publish.isPending ? (
              <Loader2 className="size-5 animate-spin" />
            ) : (
              <Check className="size-5" />
            )}
            Sotuvga chiqarish
          </Button>
        </>
      ) : (
        /* Already on sale. The button used to be drawn here too, labelled
           "Sotuvda" and still sending `active` — so pressing it asked the
           server to move a card from active to active and got the refusal it
           deserved. Which button exists is the server's answer, not a guess
           from the status: `next_statuses` is on the card for exactly this. */
        <p className="flex items-center gap-2 rounded-control bg-good-soft p-2 text-small text-good">
          <Check className="size-4 shrink-0" />
          Sotuvda — quyidagilarni to'ldirsangiz to'liqroq ko'rinadi
        </p>
      )}

      <div className="space-y-4 border-t pt-4">
        <h3 className="text-micro font-semibold uppercase tracking-wide text-ink-soft">
          Telefonda to'liq ko'rinishi uchun
        </h3>
        <Words card={card} />
        <Specs card={card} />
        {!gate.has("needs_photo") ? <Photos card={card} more /> : null}
        {!gate.has("needs_price") ? <Pricing card={card} /> : null}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------- the words

/**
 * The name, the line under it, the prose, the guarantee.
 *
 * One form and one save, because it is one job: somebody looking at the goods
 * writing what a customer needs to read. The name matters most — a card
 * arrives from the bench called `Krossovka · Nike · Qora`, which is a warehouse
 * label and not a thing anybody searches for.
 */
function Words({ card }: { card: AdminProduct }) {
  const detail = useProduct(card.id)
  const write = useFileCard(card.id)

  const [title, setTitle] = useState(card.title)
  const [subtitle, setSubtitle] = useState("")
  const [description, setDescription] = useState("")
  const [warranty, setWarranty] = useState("")

  // Filled once the card arrives, and not on every render: typing into a field
  // whose value is being reset underneath is the classic form that fights back.
  const [loaded, setLoaded] = useState(false)
  useEffect(() => {
    if (loaded || !detail.data) return
    setTitle(detail.data.title)
    setSubtitle(detail.data.subtitle)
    setDescription(detail.data.description)
    setWarranty(detail.data.warranty ?? "")
    setLoaded(true)
  }, [detail.data, loaded])

  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault()
        write.mutate({
          title: title.trim() || card.title,
          subtitle: subtitle.trim(),
          description: description.trim(),
          warranty: warranty.trim() || null,
        })
      }}
    >
      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Nomi — mijoz shuni o'qiydi va shuni qidiradi
        </span>
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Erkaklar krossovkasi Alfa"
          aria-label="Nomi"
          className="h-control-lg text-body"
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Qisqa izoh — nom ostidagi bir qator
        </span>
        <Input
          value={subtitle}
          onChange={(event) => setSubtitle(event.target.value)}
          placeholder="Qora, yengil, kunlik"
          aria-label="Qisqa izoh"
          className="h-control"
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">Tavsif</span>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={4}
          placeholder="Nimadan tikilgan, kimga to'g'ri keladi, qanday parvarish qilinadi."
          aria-label="Tavsif"
          className="w-full rounded-control border bg-surface p-2 text-small"
        />
      </label>

      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Kafolat — bo'lmasa bo'sh qoldiring
        </span>
        <Input
          value={warranty}
          onChange={(event) => setWarranty(event.target.value)}
          placeholder="1 yil"
          aria-label="Kafolat"
          className="h-control"
        />
      </label>

      <Problem error={write.error} />
      <Button
        type="submit"
        variant="secondary"
        className="h-control w-full"
        disabled={write.isPending}
      >
        {write.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
        Saqlash
      </Button>
    </form>
  )
}

// ------------------------------------------------------------------- the table

/** The specification table, which the phone draws as a table or not at all. */
function Specs({ card }: { card: AdminProduct }) {
  const stored = useSpecs(card.id)
  const write = useWriteSpecs(card.id)
  const [rows, setRows] = useState<Spec[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (loaded || !stored.data) return
    setRows(stored.data.length ? stored.data : [{ key: "", value: "" }])
    setLoaded(true)
  }, [stored.data, loaded])

  function set(index: number, patch: Partial<Spec>) {
    setRows((was) => was.map((row, at) => (at === index ? { ...row, ...patch } : row)))
  }

  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Table2 className="size-4 text-ink-soft" />
        Xususiyatlar
      </h4>

      <ul className="space-y-1">
        {rows.map((row, index) => (
          <li key={index} className="flex gap-1">
            <Input
              value={row.key}
              onChange={(event) => set(index, { key: event.target.value })}
              placeholder="Mato"
              aria-label={`${index + 1} — nomi`}
              className="h-control w-1/3"
            />
            <Input
              value={row.value}
              onChange={(event) => set(index, { value: event.target.value })}
              placeholder="Paxta"
              aria-label={`${index + 1} — qiymati`}
              className="h-control flex-1"
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label="Qatorni o'chirish"
              onClick={() => setRows((was) => was.filter((_, at) => at !== index))}
            >
              <Trash2 className="size-4" />
            </Button>
          </li>
        ))}
      </ul>

      <div className="flex gap-2">
        <Button
          type="button"
          variant="ghost"
          className="h-control gap-1"
          onClick={() => setRows((was) => [...was, { key: "", value: "" }])}
        >
          <Plus className="size-4" />
          Qator
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="h-control flex-1"
          disabled={write.isPending}
          onClick={() =>
            write.mutate(
              rows
                .map((row) => ({ key: row.key.trim(), value: row.value.trim() }))
                .filter((row) => row.key && row.value),
            )
          }
        >
          Saqlash
        </Button>
      </div>

      <Problem error={write.error} />
    </div>
  )
}

// -------------------------------------------------------------- the photographs

function Photos({ card, more }: { card: AdminProduct; more?: boolean }) {
  const grid = useVariants(card.id)
  const shots = useImages(card.id)
  const image = useAddImage(card.id)
  const [taken, setTaken] = useState<Record<string, string>>({})

  // One per colour, never per size: two colours in six sizes is two
  // photographs, and asking for twelve is how a desk stops photographing
  // anything at all.
  const colours = useMemo(() => {
    const seen = new Set((grid.data ?? []).map((cell) => cell.colour))
    return [...seen]
  }, [grid.data])

  const [colour, setColour] = useState<string | null>(null)
  const active = colour ?? colours[0] ?? ""
  const held = (shots.data ?? []).filter((one) => one.colour === active)

  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Camera className="size-4 text-ink-soft" />
        {more ? "Ko'proq rasm" : "Katalog rasmi"}
        {more ? (
          <span className="font-normal text-ink-faint">
            — mijoz varaqlaydi, bittasi kam
          </span>
        ) : null}
      </h4>

      {colours.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {colours.map((one) => (
            <button
              key={one}
              type="button"
              onClick={() => setColour(one)}
              className={cn(
                "h-control rounded-control border px-3 text-small",
                one === active && "border-brand bg-brand text-brand-ink",
              )}
            >
              {one || "rasm"}
              <span className="ml-1 tabular opacity-70">
                {(shots.data ?? []).filter((shot) => shot.colour === one).length}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {held.length ? (
        <ul className="flex flex-wrap gap-1">
          {held.map((shot) => (
            <li key={shot.id}>
              <img
                src={mediaUrl(shot.url)}
                alt=""
                className="size-16 rounded-control border object-cover"
              />
            </li>
          ))}
        </ul>
      ) : null}

      {/* The identification snapshot is already on the card and is sometimes
          good enough. Reusing it is one tap against a walk to the bench. */}
      {card.snapshot_url && !held.length && !taken[active] ? (
        <div className="flex items-center gap-2 rounded-control border border-dashed p-2">
          <img
            src={mediaUrl(card.snapshot_url)}
            alt=""
            className="size-12 rounded-control object-cover"
          />
          <p className="min-w-0 flex-1 text-micro text-ink-soft">
            Qabuldagi tanish rasmi. Yaxshi chiqqan bo'lsa qaytadan olish shart emas.
          </p>
          <Button
            type="button"
            variant="secondary"
            className="h-control"
            disabled={image.isPending}
            onClick={() =>
              image.mutate(
                { url: card.snapshot_url, colour: active },
                {
                  onSuccess: () =>
                    setTaken((was) => ({ ...was, [active]: card.snapshot_url })),
                },
              )
            }
          >
            Shuni ishlat
          </Button>
        </div>
      ) : null}

      <Capture
        colour={active}
        current={undefined}
        onTaken={(one, url) => {
          setTaken((was) => ({ ...was, [one]: url }))
          image.mutate({ url, colour: one })
        }}
      />

      <Problem error={image.error} />
    </section>
  )
}

// ------------------------------------------------------------------- the filing

function Filing({ card }: { card: AdminProduct }) {
  const categories = useCategories()
  const file = useFileCard(card.id)
  const write = useWriteCategory()
  const [name, setName] = useState("")

  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Tags className="size-4 text-ink-soft" />
        Kategoriya
        <span className="font-normal text-ink-faint">— mijoz shu orqali topadi</span>
      </h4>

      <div className="flex flex-wrap gap-1">
        {(categories.data ?? []).map((one) => (
          <button
            key={one.slug}
            type="button"
            disabled={file.isPending}
            onClick={() => file.mutate({ category_slug: one.slug })}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              card.category_slug === one.slug && "border-brand bg-brand text-brand-ink",
            )}
          >
            {one.name}
          </button>
        ))}
      </div>

      {/* Written here rather than on another screen: the first card ever
          written has nowhere to go, and sending somebody to a different menu
          to make one is where the old flow stopped dead. */}
      <form
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          const wanted = name.trim()
          if (!wanted) return
          const slug =
            wanted
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-|-$/g, "") || `kat-${Date.now()}`
          write.mutate(
            { slug, name: wanted },
            {
              onSuccess: (made) => {
                setName("")
                file.mutate({ category_slug: made.slug })
              },
            },
          )
        }}
      >
        <label className="min-w-32 flex-1">
          <span className="mb-1 block text-micro text-ink-soft">Yangi kategoriya</span>
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Oyoq kiyim"
            aria-label="Yangi kategoriya"
            className="h-control"
          />
        </label>
        <Button type="submit" variant="secondary" className="h-control">
          Qo'shish
        </Button>
      </form>

      <Problem error={file.error || write.error} />
    </section>
  )
}

// -------------------------------------------------------------------- the price

function Pricing({ card }: { card: AdminProduct }) {
  const price = usePriceCard(card.id)
  const [sale, setSale] = useState(card.price ? String(card.price) : "")
  const [was, setWas] = useState(card.old_price ? String(card.old_price) : "")

  // What the goods cost is the one figure already known — it was written at the
  // bench with the sack open, and it lives on the market run's line rather than
  // on the cell, because a cell's price is what we sell at. So the markup is
  // offered rather than the price: "+75%" is how the person who bought them
  // thinks, and typing the answer outright is still there for when it is not.
  const cost = card.last_cost
  const wanted = Number(sale) || 0
  const markup = cost > 0 && wanted > 0 ? Math.round((wanted / cost - 1) * 100) : 0

  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-2 text-small font-medium">
        <Wallet className="size-4 text-ink-soft" />
        Sotuv narxi
        {cost > 0 ? (
          <span className="font-normal text-ink-faint">— tannarx {money(cost)}</span>
        ) : null}
      </h4>

      {cost > 0 ? (
        <div className="flex flex-wrap gap-1">
          {[40, 60, 75, 100].map((percent) => (
            <button
              key={percent}
              type="button"
              onClick={() =>
                setSale(String(Math.round((cost * (100 + percent)) / 100 / 1000) * 1000))
              }
              className="h-control rounded-control border px-3 text-small"
            >
              +{percent}%
            </button>
          ))}
        </div>
      ) : null}

      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (wanted > 0) {
            price.mutate({ price: wanted, old_price: Number(was) || null })
          }
        }}
      >
        <label className="w-36">
          <span className="mb-1 block text-micro text-ink-soft">Narx</span>
          <Input
            value={sale}
            onChange={(event) => setSale(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="149 000"
            aria-label="Sotuv narxi"
            className="h-control-lg tabular text-body"
          />
        </label>
        <label className="w-36">
          <span className="mb-1 block text-micro text-ink-soft">
            Eski narx — chegirma
          </span>
          <Input
            value={was}
            onChange={(event) => setWas(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="199 000"
            aria-label="Eski narx"
            className="h-control tabular"
          />
        </label>
        <Button
          type="submit"
          variant="secondary"
          className="h-control-lg"
          disabled={wanted <= 0 || price.isPending}
        >
          Qo'yish
        </Button>
        {markup > 0 ? (
          <span className="pb-2 text-small text-ink-soft">+{markup}%</span>
        ) : null}
      </form>

      <Problem error={price.error} />
    </section>
  )
}
