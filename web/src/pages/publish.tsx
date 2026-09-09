/**
 * Sotuvga chiqarish — goods that are on a shelf and not in the shop.
 *
 * This is the other half of the receiving desk, and it exists because the two
 * halves were one screen and neither got done. Booking a pile in is physical
 * and urgent: the sack is open, the goods are in the way, and the only things
 * anybody knows are what it is, how many, and which cell. Filing it in the
 * shop is none of those things — it wants a category somebody has thought
 * about, a price somebody has worked out, and a photograph taken in daylight
 * against white paper.
 *
 * So a card off the van is a stub, and this is the queue of stubs. Everything
 * in it is **already stock**: shelved, counted, findable, and invisible to
 * every customer. That is the quiet way this shop loses money — nothing is
 * broken, nothing errors, the goods simply never go on sale — so the queue
 * carries a count in the menu and a tile on the dashboard, and a card that has
 * waited three days goes red.
 *
 * Three gaps, and the server names them. The browser branches on `gap.key` to
 * decide which control to put in front of somebody and shows `gap.label` as
 * the wording, so neither the rule nor the translation is duplicated here.
 */

import { Camera, Check, Loader2, Package, Tags, Wallet } from "lucide-react"
import { useMemo, useState } from "react"

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
  usePriceCard,
  useProducts,
  usePublish,
  useVariants,
  useWriteCategory,
} from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

// Three days. An afternoon is somebody waiting for daylight; three days is
// goods nobody is going to get round to, costing rent and earning nothing.
const STALE_MINUTES = 3 * 24 * 60

export function PublishPage() {
  const drafts = useProducts("", "draft")
  const [open, setOpen] = useState<number | null>(null)

  // Only what is actually on a shelf. A card somebody started writing and
  // abandoned is not money sitting still, and mixing the two makes the count
  // in the menu mean nothing.
  const held = useMemo(
    () =>
      (drafts.data?.items ?? [])
        .filter((card) => card.stock_left > 0)
        .sort((a, b) => a.created_at.localeCompare(b.created_at)),
    [drafts.data],
  )

  const worth = held.reduce((sum, card) => sum + card.stock_left * card.price, 0)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Sotuvga chiqarish"
        subtitle="Javonda bor, do'konda yo'q"
      >
        {held.length ? (
          <span className="text-small text-ink-soft">
            {held.length} tovar{worth ? ` · ${money(worth)}` : ""}
          </span>
        ) : null}
      </PageHeader>

      {drafts.isLoading ? <Waiting what="Navbat" /> : null}
      <Problem error={drafts.error} />

      {!drafts.isLoading && held.length === 0 ? (
        <Empty what="Javondagi hamma tovar do'konda ham bor. Qabuldan keyin shu yerga tushadi." />
      ) : null}

      <ul className="space-y-2">
        {held.map((card) => (
          <li key={card.id}>
            <Card
              card={card}
              open={open === card.id}
              onOpen={() => setOpen(open === card.id ? null : card.id)}
            />
          </li>
        ))}
      </ul>
    </div>
  )
}

// ------------------------------------------------------------------- one card

function Card({
  card,
  open,
  onOpen,
}: {
  card: AdminProduct
  open: boolean
  onOpen: () => void
}) {
  const minutes = minutesSince(card.created_at)
  const stale = minutes >= STALE_MINUTES

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
          </div>
          <div className="mt-1 flex flex-wrap gap-1">
            {card.unready.map((gap) => (
              <span
                key={gap.key}
                className="rounded-control bg-warn-soft px-1.5 py-0.5 text-micro text-warn-ink"
              >
                {gap.label}
              </span>
            ))}
          </div>
        </div>

        <span
          className={cn(
            "shrink-0 text-micro tabular",
            stale ? "font-semibold text-danger" : "text-ink-faint",
          )}
        >
          {age(minutes)}
        </span>
      </button>

      {open ? <Fill card={card} /> : null}
    </div>
  )
}

/** The three gaps, in the order somebody would actually fill them. */
function Fill({ card }: { card: AdminProduct }) {
  const gaps = new Set(card.unready.map((gap) => gap.key))
  const publish = usePublish(card.id)

  return (
    <div className="space-y-4 border-t p-3">
      {gaps.has("needs_photo") ? <Photos card={card} /> : null}
      {gaps.has("needs_category") ? <Filing card={card} /> : null}
      {gaps.has("needs_price") ? <Pricing card={card} /> : null}

      <Problem error={publish.error} />

      {gaps.size === 0 ? (
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
      ) : (
        <p className="text-center text-micro text-ink-faint">
          Yuqoridagilar to'lgach sotuvga chiqadi
        </p>
      )}
    </div>
  )
}

// -------------------------------------------------------------- the photograph

function Photos({ card }: { card: AdminProduct }) {
  const grid = useVariants(card.id)
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

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-small font-semibold">
        <Camera className="size-4 text-ink-soft" />
        Katalog rasmi
      </h3>

      {colours.length > 1 ? (
        <div className="flex flex-wrap gap-1">
          {colours.map((one) => (
            <button
              key={one}
              type="button"
              onClick={() => setColour(one)}
              className={cn(
                "h-control rounded-control border px-3 text-small",
                one === active && "border-brand bg-brand-soft text-brand-deep",
                taken[one] && "border-good",
              )}
            >
              {one || "rasm"}
              {taken[one] ? " ✓" : ""}
            </button>
          ))}
        </div>
      ) : null}

      {/* The identification snapshot is already on the card and is sometimes
          good enough. Reusing it is one tap against a walk to the bench. */}
      {card.snapshot_url && !taken[active] ? (
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
        current={taken[active]}
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
      <h3 className="flex items-center gap-2 text-small font-semibold">
        <Tags className="size-4 text-ink-soft" />
        Kategoriya
        <span className="font-normal text-ink-faint">
          — mijoz shu orqali topadi
        </span>
      </h3>

      <div className="flex flex-wrap gap-1">
        {(categories.data ?? []).map((one) => (
          <button
            key={one.slug}
            type="button"
            disabled={file.isPending}
            onClick={() => file.mutate({ category_slug: one.slug })}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              card.category_slug === one.slug &&
                "border-brand bg-brand-soft text-brand-deep",
            )}
          >
            {one.name}
          </button>
        ))}
      </div>

      {/* Written here rather than on another screen: a card is filed at the
          moment somebody is looking at the goods and knows where they belong. */}
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

// ------------------------------------------------------------------- the price

function Pricing({ card }: { card: AdminProduct }) {
  const price = usePriceCard(card.id)
  const [sale, setSale] = useState("")

  // What the goods cost is the one figure already known — it was written at
  // the bench with the sack open, and it lives on the market run's line rather
  // than on the cell, because a cell's price is what we sell at. So the markup
  // is offered rather than the price: "+75%" is how the person who bought them
  // thinks, and typing the answer outright is still there for when it is not.
  const cost = card.last_cost

  const wanted = Number(sale) || 0
  const markup = cost > 0 && wanted > 0 ? Math.round((wanted / cost - 1) * 100) : 0

  return (
    <section className="space-y-2">
      <h3 className="flex items-center gap-2 text-small font-semibold">
        <Wallet className="size-4 text-ink-soft" />
        Sotuv narxi
        {cost > 0 ? (
          <span className="font-normal text-ink-faint">
            — tannarx {money(cost)}
          </span>
        ) : null}
      </h3>

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
        className="flex items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (wanted > 0) price.mutate({ price: wanted })
        }}
      >
        <label className="w-40">
          <Input
            value={sale}
            onChange={(event) => setSale(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="149000"
            aria-label="Sotuv narxi"
            className="h-control-lg tabular text-body"
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
