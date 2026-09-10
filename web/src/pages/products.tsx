/**
 * Mahsulotlar — the catalogue, and the one screen that puts a card in the shop.
 *
 * **The list leads with what is missing.** A card held back for want of a
 * photograph is the row somebody has to act on, so the status says which
 * colour is missing rather than the word "draft" — and the dashboard's own
 * tile links straight here with the filter already applied.
 *
 * Opening a card gives the three things a card is made of and nothing else:
 * the grid of colours and sizes, the photographs (one per colour), and the
 * button that puts it on sale. Its price belongs to the variants, its stock to
 * the ledger, and neither is edited from a form here.
 */

import { Check, Image as ImageIcon, Loader2, Search, Trash2 } from "lucide-react"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { PhotoStep, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import {
  useAddImage,
  useDeleteCard,
  useImages,
  useProducts,
  usePublish,
  useRetireVariant,
  useVariants,
} from "@/lib/queries"
import type { AdminProduct, AdminVariant } from "@/lib/types"

export function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get("status") ?? ""
  // What the dashboard's "Tugagan tavarlar" tile lands on. The tile linked to
  // `?low=1`, which nothing on either side read: the count was right and the
  // list it sent you to was the whole catalogue.
  const stock = params.get("stock") ?? ""
  const [needle, setNeedle] = useState("")
  const [openId, setOpenId] = useState<number | null>(null)
  const products = useProducts(needle, status, stock)

  if (openId) return <Card id={openId} onBack={() => setOpenId(null)} />

  return (
    <div className="space-y-4">
      <PageHeader title="Mahsulotlar" subtitle="Kataloq — kompaniyaniki">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={needle}
            onChange={(event) => setNeedle(event.target.value)}
            placeholder="Nomi yoki kodi"
            aria-label="Qidirish"
            className="h-control w-56 pl-8"
          />
        </div>
      </PageHeader>

      <div className="flex flex-wrap gap-1">
        {[
          { key: "", label: "Hammasi" },
          { key: "draft", label: "Rasmsiz — sotuvda emas" },
          { key: "active", label: "Sotuvda" },
          { key: "archived", label: "Arxivda" },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setParams(tab.key ? { status: tab.key } : {})}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              tab.key === status && !stock && "border-brand bg-brand-soft text-brand-deep",
            )}
          >
            {tab.label}
          </button>
        ))}
        {/* The two that are about the shelf rather than about the card.
            Money standing still in both directions: goods on sale that the
            shop cannot supply, and goods about to become that. */}
        {[
          { key: "out", label: "Tugagan" },
          { key: "low", label: "Tugayotgan" },
        ].map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setParams(stock === tab.key ? {} : { stock: tab.key })}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              tab.key === stock
                ? "border-danger bg-danger-soft text-danger"
                : "text-ink-soft",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Problem error={products.error} />
      {products.isLoading ? <Waiting what="Kartalar" /> : null}
      {products.data?.items.length === 0 ? (
        <Empty what="Bunday karta yo'q. Qabul ekranida, qop ochilganda yoziladi." />
      ) : null}

      <ul className="space-y-2">
        {(products.data?.items ?? []).map((product) => (
          <li key={product.id}>
            <button
              type="button"
              onClick={() => setOpenId(product.id)}
              className="flex w-full items-center gap-3 rounded-panel border bg-surface p-3 text-left hover:border-brand"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-body font-semibold">{product.title}</div>
                <div className="text-micro tabular text-ink-faint">
                  {product.sku} · {product.variant_count} variant ·{" "}
                  {product.image_count} rasm
                </div>
                {/* By name. A card is rarely out of stock as a whole — one
                    colour of it is, the total still reads comfortably, and
                    nobody hears about it until a customer orders that
                    colour. */}
                {product.sold_out.length && product.status === "active" ? (
                  <div className="mt-0.5 truncate text-micro text-danger">
                    Tugagan: {product.sold_out.join(", ")}
                  </div>
                ) : null}
              </div>
              <div className="shrink-0 text-right">
                <div className="tabular text-small font-medium">
                  {money(product.price)}
                </div>
                <div className="text-micro text-ink-faint">
                  {groups(product.stock_left)} dona
                </div>
              </div>
              <Status status={product.status} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Take one cell out of the shop window, or put it back.
 *
 * A cell that has ever held anything cannot be deleted — every movement and
 * order line points at it — so a size booked in by mistake used to be a chip
 * struck through on the product page for the life of the card. This is the way
 * out, and it is refused while the cell still holds goods: hiding stock the
 * shop has paid for is worse than an untidy row, because a picker can still
 * be sent to it and the office cannot see why the money is missing.
 */
function RetireLine({
  variant,
  onSet,
  busy,
}: {
  variant: AdminVariant
  onSet: (retired: boolean) => void
  busy: boolean
}) {
  if (variant.retired) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => onSet(false)}
        className="shrink-0 text-micro text-brand-deep"
      >
        Qaytarish
      </button>
    )
  }
  if (variant.stock_left > 0) {
    // Nothing to press and a reason it is not there, rather than a button that
    // asks and is refused.
    return (
      <span className="w-20 shrink-0 text-right text-micro text-ink-faint">
        javonda bor
      </span>
    )
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => onSet(true)}
      className="shrink-0 text-micro text-ink-soft hover:text-danger"
    >
      Olib tashlash
    </button>
  )
}

function Status({ status }: { status: AdminProduct["status"] }) {
  const word =
    status === "active" ? "sotuvda" : status === "draft" ? "rasmsiz" : "arxiv"
  return (
    <span
      className={cn(
        "shrink-0 rounded-full px-2 py-0.5 text-micro",
        status === "active" && "bg-good-soft text-good",
        status === "draft" && "bg-warn-soft text-warn-ink",
        status === "archived" && "bg-line-soft text-ink-soft",
      )}
    >
      {word}
    </span>
  )
}

// ------------------------------------------------------------------- one card

/**
 * Remove a card, with the confirmation in the button rather than in a dialog.
 *
 * Two taps: the first turns the button into the sentence it is about to carry
 * out, the second does it. A dialog would say the same thing in a box that has
 * to be dismissed, and a single tap on "O'chirish" beside a catalogue is the
 * kind of mistake nobody notices until the card is gone.
 *
 * What actually happens is the server's call: a card nothing has happened to is
 * deleted, and one with a movement or an order against it is archived, because
 * deleting that would leave an order naming a product that does not exist. The
 * answer says which it did.
 */
function DeleteCard({
  id,
  title,
  onGone,
}: {
  id: number
  title: string
  onGone: () => void
}) {
  const remove = useDeleteCard(id)
  const [asked, setAsked] = useState(false)

  if (!asked) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="gap-1 text-danger"
        onClick={() => setAsked(true)}
      >
        <Trash2 className="size-4" />
        O'chirish
      </Button>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-micro text-danger">{title || "Bu karta"} — aniqmi?</span>
      <Button
        size="sm"
        className="bg-danger text-danger-ink hover:bg-danger"
        disabled={remove.isPending}
        onClick={() =>
          remove.mutate(undefined, {
            onSuccess: onGone,
          })
        }
      >
        {remove.isPending ? <Loader2 className="size-4 animate-spin" /> : "Ha"}
      </Button>
      <Button variant="ghost" size="sm" onClick={() => setAsked(false)}>
        Yo'q
      </Button>
    </div>
  )
}

function Card({ id, onBack }: { id: number; onBack: () => void }) {
  const products = useProducts("", "")
  const grid = useVariants(id)
  const images = useImages(id)
  const addImage = useAddImage(id)
  const publish = usePublish(id)
  const retire = useRetireVariant(id)

  const product = products.data?.items.find((one) => one.id === id)
  const colours = [...new Set((grid.data ?? []).map((one) => one.colour))].filter(
    Boolean,
  )
  const taken = Object.fromEntries(
    (images.data ?? []).map((image) => [image.colour, image.url]),
  )
  const missing = (colours.length ? colours : [""]).filter((one) => !taken[one])

  return (
    <div className="space-y-4">
      <PageHeader
        title={product?.title ?? "Karta"}
        subtitle={product ? `${product.sku} · ${money(product.price)}` : ""}
      >
        <DeleteCard id={id} title={product?.title ?? ""} onGone={onBack} />
        <Button variant="ghost" onClick={onBack}>
          Ro'yxatga
        </Button>
      </PageHeader>

      <Problem
        error={
          grid.error ||
          images.error ||
          publish.error ||
          addImage.error ||
          retire.error
        }
      />

      <section className="rounded-panel border bg-surface p-3">
        <h2 className="mb-2 text-small font-semibold">Rang × o'lcham</h2>
        {grid.isLoading ? <Waiting /> : null}
        {grid.data?.length === 0 ? <Empty what="To'r hali yaratilmagan." /> : null}
        {/* Where a colour comes from, said once and here: the sack. Somebody
            publishing a card asked whether they were meant to be adding
            colours on this screen — nothing on it invents one, and a colour
            with no goods behind it would be a shop window offering something
            the room does not have. */}
        <p className="mb-2 text-micro text-ink-faint">
          Ranglar va o'lchamlar qabulda yoziladi — qop ochilganda. Bu yerda
          faqat rasm, narx va sotuvga chiqarish.
        </p>
        <ul className="divide-y">
          {(grid.data ?? []).map((variant) => (
            <li
              key={variant.id}
              className={cn(
                "flex items-center gap-3 py-2",
                variant.retired && "opacity-55",
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="text-small font-medium">
                  {variant.label}
                  {variant.retired ? (
                    <span className="ml-2 rounded-full bg-line-soft px-2 py-0.5 text-micro font-normal text-ink-soft">
                      sotuvda emas
                    </span>
                  ) : null}
                </div>
                <div className="text-micro tabular text-ink-faint">
                  {variant.sku} · {variant.barcode}
                </div>
              </div>
              <span className="tabular text-small">{money(variant.price)}</span>
              {/* Nought is a word, not a figure to be read off a column. The
                  list showed "0" in the same grey as every other count. */}
              {variant.stock_left <= 0 ? (
                <span className="w-16 text-right text-small font-semibold text-danger">
                  {variant.retired ? "—" : "tugagan"}
                </span>
              ) : (
                <span className="w-16 text-right tabular text-small font-semibold">
                  {groups(variant.stock_left)}
                </span>
              )}
              <RetireLine
                variant={variant}
                onSet={(retired) =>
                  retire.mutate({ variantId: variant.id, retired })
                }
                busy={retire.isPending}
              />
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-panel border bg-surface p-3">
        <h2 className="mb-2 flex items-center gap-2 text-small font-semibold">
          <ImageIcon className="size-4" />
          Rasmlar — har rangga bittadan
        </h2>
        <PhotoStep
          colours={colours.length ? colours : [""]}
          taken={taken}
          onTaken={(colour, url) => addImage.mutate({ url, colour })}
        />
        {images.data?.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {images.data.map((image) => (
              <figure key={image.id} className="w-20">
                <img
                  src={mediaUrl(image.url)}
                  alt={image.colour}
                  className="aspect-square w-full rounded-control object-cover"
                />
                <figcaption className="truncate text-center text-micro text-ink-faint">
                  {image.colour || "umumiy"}
                </figcaption>
              </figure>
            ))}
          </div>
        ) : null}
      </section>

      {product ? (
        <Button
          className="h-control-lg w-full gap-2"
          disabled={publish.isPending || (product.status !== "active" && missing.length > 0)}
          onClick={() =>
            publish.mutate(product.status === "active" ? "archived" : "active")
          }
        >
          <Check className="size-5" />
          {product.status === "active"
            ? "Sotuvdan olish"
            : missing.length
              ? `Rasmsiz rang: ${missing.join(", ")}`
              : "Sotuvga chiqarish"}
        </Button>
      ) : null}
    </div>
  )
}
