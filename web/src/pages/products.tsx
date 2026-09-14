/**
 * Mahsulotlar — the catalogue, and the one screen that puts a card in the shop.
 *
 * **The list leads with what is missing.** A card held back for want of a
 * photograph is the row somebody has to act on, so the status says which
 * colour is missing rather than the word "draft" — and the dashboard's own
 * tile links straight here with the filter already applied.
 *
 * Opening a card gives the three things a card is made of: the grid of colours
 * and sizes, the photographs (one per colour), and the button that puts it on
 * sale. Its stock is the ledger's and is not edited from a form here.
 *
 * **And what was written wrong can be corrected.** The editor — the words, the
 * filing, the price, the table — used to live only inside "Sotuvga
 * chiqarish", which lists what is *held back*; a card that went on sale
 * cleanly dropped off every list that had a form on it, so a name mistyped at
 * the receiving desk was permanent and deleting the card was the only way out.
 * It is folded away behind a button because most visits here are to read a
 * row, not to rewrite one.
 */

import {
  Check,
  Image as ImageIcon,
  Loader2,
  PackageSearch,
  Pencil,
  Trash2,
} from "lucide-react"
import { useState } from "react"
import { useSearchParams } from "react-router-dom"

import {
  Empty,
  PageHeader,
  Panel,
  Pill,
  Problem,
  Segmented,
  Waiting,
} from "@/components/page"
import { Code } from "@/components/copy"
import { DataTable, useTableState } from "@/components/data-table"
import { Filing, Pricing, Specs, Words } from "@/components/card-editor"
import type { Tone } from "@/components/page"
import { PhotoStep, mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import {
  useAddImage,
  useDamage,
  useDeleteCard,
  useDeleteImage,
  useImages,
  useProducts,
  usePublish,
  useRetireVariant,
  useVariants,
} from "@/lib/queries"
import type { AdminImage, AdminProduct, AdminVariant } from "@/lib/types"

export function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const status = params.get("status") ?? ""
  // What the dashboard's "Tugagan tavarlar" tile lands on. The tile linked to
  // `?low=1`, which nothing on either side read: the count was right and the
  // list it sent you to was the whole catalogue.
  const stock = params.get("stock") ?? ""
  const state = useTableState()
  const [openId, setOpenId] = useState<number | null>(null)
  const products = useProducts(state.q, status, stock)

  if (openId) return <Card id={openId} onBack={() => setOpenId(null)} />

  return (
    <div className="space-y-4">
      <PageHeader title="Mahsulotlar" subtitle="Kataloq — kompaniyaniki" />

      {/* The catalogue is the biggest list in the app and was the last one
          drawn by hand: its own search box in the page header, its own row,
          no sorting, no paging and no way to take it off the screen. It is
          the same table as the other ten now — which is the whole of what
          "the screens match" means. */}
      <DataTable<AdminProduct>
        title="Mahsulotlar"
        rows={products.data?.items ?? []}
        total={products.data?.total}
        loading={products.isLoading}
        error={products.error}
        rowKey={(row) => row.id}
        onRowClick={(row) => setOpenId(row.id)}
        count={(n) => `${groups(n)} ta karta`}
        searchPlaceholder="Nomi yoki kodi"
        empty={{
          icon: PackageSearch,
          title: "Bunday karta yo'q",
          what: "Kartalar qabul ekranida, qop ochilganda yoziladi.",
        }}
        beforeSearch={
          <div className="flex flex-wrap items-center gap-2">
            {/* What state the card is in — one segmented control, because
                these four are one question with four answers. It shows no
                answer at all while the list is filtered by the shelf. */}
            <Segmented
              label="Holat"
              value={stock ? null : status}
              onChange={(key) => setParams(key ? { status: key } : {})}
              options={[
                { key: "", label: "Hammasi" },
                { key: "draft", label: "Rasmsiz" },
                { key: "active", label: "Sotuvda" },
                { key: "archived", label: "Arxivda" },
              ]}
            />

            {/* And these two are about the shelf rather than about the card —
                money standing still in both directions: goods on sale the
                shop cannot supply, and goods about to become that. */}
            <Segmented
              label="Javon"
              tone="danger"
              value={stock || null}
              onChange={(key) => setParams(stock === key ? {} : { stock: key })}
              options={[
                { key: "out", label: "Tugagan" },
                { key: "low", label: "Tugayotgan" },
              ]}
            />
          </div>
        }
        columns={[
          {
            key: "title",
            header: "Karta",
            sortable: true,
            sortValue: (row) => row.title.toLowerCase(),
            cell: (row) => (
              <div className="min-w-0">
                <div className="truncate font-medium">{row.title}</div>
                {/* By name. A card is rarely out of stock as a whole — one
                    colour of it is, the total still reads comfortably, and
                    nobody hears about it until a customer orders that
                    colour. */}
                {row.sold_out.length && row.status === "active" ? (
                  <div className="truncate text-micro text-danger">
                    Tugagan: {row.sold_out.join(", ")}
                  </div>
                ) : null}
              </div>
            ),
            export: (row) => row.title,
          },
          {
            key: "sku",
            header: "Kod",
            width: "1%",
            cell: (row) => <Code>{row.sku}</Code>,
            export: (row) => row.sku,
          },
          {
            key: "variant_count",
            header: "Variant",
            numeric: true,
            sortable: true,
            sortValue: (row) => row.variant_count,
            cell: (row) => groups(row.variant_count),
          },
          {
            key: "image_count",
            header: "Rasm",
            numeric: true,
            sortable: true,
            sortValue: (row) => row.image_count,
            cell: (row) => groups(row.image_count),
          },
          {
            key: "price",
            header: "Narx",
            numeric: true,
            sortable: true,
            sortValue: (row) => row.price,
            cell: (row) => money(row.price),
          },
          {
            key: "stock_left",
            header: "Qoldiq",
            numeric: true,
            sortable: true,
            sortValue: (row) => row.stock_left,
            cell: (row) => `${groups(row.stock_left)} dona`,
          },
          {
            key: "status",
            header: "Holat",
            width: "1%",
            cell: (row) => <Status status={row.status} />,
            export: (row) => word(row.status),
          },
        ]}
      />
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
        className="shrink-0 text-micro text-brand-deep">
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
      className="shrink-0 text-micro text-ink-soft hover:text-danger">
      Olib tashlash
    </button>
  )
}

/**
 * A garment that cannot be sold, off the shelf and into the corner by the door.
 *
 * There was no way to say this anywhere in the panel: a stain found on the
 * shelf left the choice between leaving the piece sellable in the count and
 * emptying the whole cell, which is a different and much blunter act. It
 * belongs on this row because the variant is already in hand — the person is
 * looking at the size they are holding.
 *
 * **Not a write-off.** The goods go to `BRAK`, which is a place in the
 * building: a torn shirt has not evaporated, it is countable, and somebody
 * decides later whether it goes back to the market or into a bin. The reason
 * is required, and it is required for the reason it is required on a
 * stocktake — three months later that sentence is the only thing telling
 * damage from a miscount.
 *
 * Nothing to press on a size the shelf does not hold: the server refuses more
 * than is there, and a button that is always refused is worse than no button.
 *
 * **And it says what happened, because the row cannot.** The count on the row
 * is everything in the *building* and the damaged corner is in the building,
 * so it does not move when a shirt is damaged — quite right, and it would
 * leave somebody pressing the button twice. The answer names what went across
 * and what is left to sell.
 */
function Damage({
  variant,
  onDone,
}: {
  variant: AdminVariant
  onDone: () => void
}) {
  const damage = useDamage()
  const [quantity, setQuantity] = useState("1")
  const [reason, setReason] = useState("")

  const many = Number(quantity) || 0
  const said = reason.trim()
  const ready = many > 0 && said.length > 0 && !damage.isPending
  const done = damage.data

  if (done) {
    return (
      <div className="mt-2 flex flex-wrap items-center gap-2 rounded-control border border-good/25 bg-good-soft p-2">
        <span className="min-w-40 flex-1 text-micro text-good">
          <span className="tabular">{groups(many)}</span> dona BRAK burchagiga
          o'tdi. Sotuvga qoladi:{" "}
          <span className="tabular">{groups(done.sellable)}</span> dona.
        </span>
        <Button variant="ghost" size="sm" onClick={onDone}>
          Yopish
        </Button>
      </div>
    )
  }

  return (
    <div className="mt-2 space-y-2 rounded-control border border-panel-edge bg-line-soft/60 p-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="w-20">
          <span className="mb-1 block text-micro text-ink-soft">Nechta</span>
          <Input
            value={quantity}
            onChange={(event) => setQuantity(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            aria-label="Nechtasi brak"
            className="h-control tabular" />
        </label>
        <label className="min-w-40 flex-1">
          <span className="mb-1 block text-micro text-ink-soft">Sababi</span>
          <Input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Dog' tushgan, tikuvi so'kilgan…"
            aria-label="Brak sababi"
            className="h-control" />
        </label>
        <Button
          size="sm"
          variant="secondary"
          disabled={!ready}
          onClick={() =>
            damage.mutate({ variant_id: variant.id, quantity: many, reason: said })
          }
        >
          {damage.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            "BRAK ga"
          )}
        </Button>
        <Button variant="ghost" size="sm" onClick={onDone}>
          Yo'q
        </Button>
      </div>
      {/* Where the goods actually go, because "brak" sounds like erasing and
          this is a move: out of the cell, into a corner that can be counted. */}
      <p className="text-micro text-ink-faint">
        Javondan chiqadi, yo'qolmaydi — BRAK burchagiga o'tadi. Sababsiz
        bo'lmaydi: keyin brakni noto'g'ri sanoqdan ajratadigan yagona yozuv shu.
      </p>
      <Problem error={damage.error} />
    </div>
  )
}

/**
 * One cell of the grid, and the two things that can be done to it.
 *
 * A row, not a list item drawn inline, because the damage form belongs *under*
 * the size it is about — the person is holding that garment — and a dialog
 * over the grid would hide the counts they are checking it against.
 */
function VariantRow({
  variant,
  onRetire,
  retiring,
}: {
  variant: AdminVariant
  onRetire: (retired: boolean) => void
  retiring: boolean
}) {
  const [damaging, setDamaging] = useState(false)

  return (
    <li className={cn("py-2", variant.retired && "opacity-55")}>
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-small font-medium">
            {variant.label}
            {variant.retired ? (
              <Pill className="ml-2 font-normal">sotuvda emas</Pill>
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
        {/* Nothing to press on a size the shelf does not hold: the server
            refuses more than is there, and a button that is always refused is
            worse than no button. */}
        {variant.stock_left > 0 ? (
          <button
            type="button"
            onClick={() => setDamaging((was) => !was)}
            className={cn(
              "shrink-0 text-micro text-ink-soft hover:text-warn-ink",
              damaging && "font-medium text-warn-ink",
            )}>
            Brak
          </button>
        ) : null}
        <RetireLine variant={variant} onSet={onRetire} busy={retiring} />
      </div>

      {damaging ? (
        <Damage variant={variant} onDone={() => setDamaging(false)} />
      ) : null}
    </li>
  )
}

/** The one word for a card's state — on the chip, and in an export. */
function word(status: AdminProduct["status"]): string {
  return status === "active" ? "sotuvda" : status === "draft" ? "rasmsiz" : "arxiv"
}

function Status({ status }: { status: AdminProduct["status"] }) {
  const tone: Tone =
    status === "active" ? "good" : status === "draft" ? "warn" : "neutral"
  return <Pill tone={tone}>{word(status)}</Pill>
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
      <Button variant="ghost" size="sm" className="gap-1 text-danger" onClick={() => setAsked(true)}
      >
        <Trash2 className="size-4" />
        O'chirish
      </Button>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-micro text-danger">{title || "Bu karta"} — aniqmi?</span>
      <Button size="sm" className="bg-danger text-danger-ink hover:bg-danger" disabled={remove.isPending} onClick={() =>
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
  const [editing, setEditing] = useState(false)

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
        <Button
          variant={editing ? "secondary" : "ghost"}
          size="sm"
          className="gap-1"
          onClick={() => setEditing((was) => !was)}
        >
          <Pencil className="size-4" />
          {editing ? "Tahrirni yopish" : "Tahrirlash"}
        </Button>
        <DeleteCard id={id} title={product?.title ?? ""} onGone={onBack} />
        <Button variant="ghost" onClick={onBack}>
          Ro'yxatga
        </Button>
      </PageHeader>

      {/* The same controls "Sotuvga chiqarish" draws, and deliberately the
          same ones: a card is corrected in one vocabulary wherever somebody
          happens to have opened it. Each block saves itself — the words, the
          filing, the price and the table are four decisions, not one form. */}
      {editing && product ? (
        <Panel title="Tahrirlash">
          <div className="space-y-5">
            <Words card={product} />
            <Filing card={product} />
            <Pricing card={product} />
            <Specs card={product} />
          </div>
        </Panel>
      ) : null}

      <Problem
        error={
          grid.error ||
          images.error ||
          publish.error ||
          addImage.error ||
          retire.error
        }
      />

      <Panel title="Rang × o'lcham">
        {grid.isLoading ? <Waiting /> : null}
        {grid.data?.length === 0 ? (
          <Empty bare what="To'r hali yaratilmagan." />
        ) : null}
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
            <VariantRow
              key={variant.id}
              variant={variant}
              onRetire={(retired) =>
                retire.mutate({ variantId: variant.id, retired })
              }
              retiring={retire.isPending}
            />
          ))}
        </ul>
      </Panel>

      <Panel
        title="Rasmlar — har rangga bittadan"
        aside={<ImageIcon className="size-4 text-ink-faint" />}
      >
        <PhotoStep
          colours={colours.length ? colours : [""]}
          taken={taken}
          onTaken={(colour, url) => addImage.mutate({ url, colour })}
        />
        <Gallery
          productId={id}
          images={images.data ?? []}
          live={product?.status === "active"}
        />
      </Panel>

      {product ? (
        <Button size="lg" className="w-full gap-2" disabled={publish.isPending || (product.status !=="active" && missing.length > 0)}
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

/**
 * The photographs, and the way back off the card.
 *
 * The door has always existed — the panel simply threw `image.id` away as a
 * React key and had nothing to name to it, so **a photograph of the wrong
 * garment was permanent**: the only way out was deleting the card.
 *
 * **The first photograph of a colour, by `sort`, is that colour's cover**, and
 * there is no reorder endpoint. Which makes "use that one instead" sayable
 * only as "delete the ones in front of it" — said on the panel, because
 * nobody is going to deduce it from a row of squares.
 *
 * **And the last photograph of a colour is not an ordinary deletion.** On a
 * card that is on sale, taking it down takes the card out of the shop: the
 * server demotes it to draft, deliberately, because a card that stayed on sale
 * only because a picture was deleted rather than never taken is the same grey
 * square to a customer. That one is warned about by name. The ordinary one is
 * not — a warning that every deletion triggers is a warning nobody reads.
 */
function Gallery({
  productId,
  images,
  live,
}: {
  productId: number
  images: AdminImage[]
  live: boolean
}) {
  const remove = useDeleteImage(productId)
  const [asked, setAsked] = useState<number | null>(null)

  if (!images.length) return null

  // Grouped by colour, and inside a colour by `sort` — the way the apps read
  // it. Not the order the list arrived in: the cover badge is a claim about
  // what the customer sees, and "delete the ones in front of it" is only
  // followable if a colour's photographs are next to each other.
  const seen: string[] = []
  for (const image of images) {
    if (!seen.includes(image.colour)) seen.push(image.colour)
  }
  const order = [...images].sort(
    (one, two) =>
      seen.indexOf(one.colour) - seen.indexOf(two.colour) ||
      one.sort - two.sort ||
      one.id - two.id,
  )
  const cover = new Map<string, number>()
  const held = new Map<string, number>()
  for (const image of order) {
    if (!cover.has(image.colour)) cover.set(image.colour, image.id)
    held.set(image.colour, (held.get(image.colour) ?? 0) + 1)
  }
  const stacked = [...held.values()].some((many) => many > 1)

  const going = order.find((one) => one.id === asked) ?? null
  const last = going ? held.get(going.colour) === 1 : false
  const falls = Boolean(going && last && live)
  const name = (colour: string) => colour || "umumiy"

  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-2">
        {order.map((image) => (
          <figure key={image.id} className="w-20">
            <div className="relative">
              <img
                src={mediaUrl(image.url)}
                alt={image.colour}
                className={cn(
                  "aspect-square w-full rounded-control object-cover",
                  asked === image.id && "ring-2 ring-danger",
                )} />
              <button
                type="button"
                aria-label={`${name(image.colour)} rasmini o'chirish`}
                onClick={() =>
                  setAsked(asked === image.id ? null : image.id)
                }
                className="absolute right-1 top-1 grid size-5 place-items-center rounded-full bg-surface/90 text-ink-soft shadow-panel transition-colors hover:text-danger">
                <Trash2 className="size-3" />
              </button>
            </div>
            <figcaption className="truncate text-center text-micro text-ink-faint">
              {name(image.colour)}
            </figcaption>
            {/* Under the tile rather than over it: a badge inside 80 pixels
                either covers the goods or gets clipped, and the one thing
                this label must do is be readable. */}
            {cover.get(image.colour) === image.id ? (
              <div className="text-center text-micro font-medium text-brand-deep">
                muqova
              </div>
            ) : null}
          </figure>
        ))}
      </div>

      {/* Only where it can be acted on: one photograph per colour is the
          normal card, and on that card the sentence is noise. */}
      {stacked ? (
        <p className="text-micro text-ink-faint">
          Har rangning birinchi rasmi — muqova. Tartibni almashtirib bo'lmaydi:
          boshqasini muqova qilish uchun oldidagilarini o'chirish kerak.
        </p>
      ) : null}

      {/* Two taps, and the second one is the sentence — the same way the card
          itself is deleted on this screen. */}
      {going ? (
        <div
          className={cn(
            "flex flex-wrap items-center gap-2 rounded-control border p-2",
            falls ? "border-danger bg-danger-soft" : "border-panel-edge",
          )}
        >
          <span
            className={cn(
              "min-w-40 flex-1 text-micro",
              falls ? "text-danger" : "text-ink-soft",
            )}>
            {falls
              ? `«${name(going.colour)}» rangining oxirgi rasmi. O'chirilsa karta sotuvdan tushadi — rasmsiz rang do'konga chiqmaydi.`
              : `«${name(going.colour)}» rasmi o'chiriladi — aniqmi?`}
          </span>
          <Button
            variant="danger"
            size="sm"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(going.id, { onSuccess: () => setAsked(null) })
            }
          >
            {remove.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : falls ? (
              "Ha, sotuvdan tushsin"
            ) : (
              "Ha"
            )}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setAsked(null)}>
            Yo'q
          </Button>
        </div>
      ) : null}

      <Problem error={remove.error} />
    </div>
  )
}
