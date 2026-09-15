/**
 * Mahsulotlar — the catalogue, and the one screen that puts a card in the shop.
 *
 * **A catalogue is scanned, not read.** The list was migrated onto the shared
 * table with the other ten screens, and that was right for orders, customers
 * and the audit trail — a row of text is how you read a ledger. It is wrong
 * here: goods are recognised by their picture, and a 20-pixel thumbnail in
 * the first of eight columns is a picture nobody can recognise anything from.
 * So the default is `ProductCard` — the photograph, four facts, and the row's
 * actions behind a `⋯` rather than across the card in grey bars.
 *
 * **The office still wants figures.** Two hundred rows of price and stock is a
 * real question and the same data answers it, so the toolbar keeps a toggle
 * and remembers which was chosen. The toolbar itself — the filters, the
 * search, the export, the URL state — is the table's and stays the table's:
 * it is what makes a filtered catalogue a link somebody can send.
 *
 * **And the card leads with what is missing.** A card held back for want of a
 * photograph shows the gap and the reason in the same pixel: the dashed
 * `rasm yo'q` frame *is* what is keeping it out of the shop. The dashboard's
 * own tile links straight here with the filter already applied.
 *
 * **One card, one form.** Opening a card mounts `CardForm` in `catalogue`
 * mode — the same component the receiving desk opens for goods with no card
 * yet, showing everything once there is a card to show it on, with the publish
 * gate at its top. There is no second screen and no editor folded behind a
 * button: what is filled in is filled in. Stock is the ledger's and stays
 * under the form, where a size can be retired or sent to `BRAK`.
 */

import {
  Archive,
  Image as ImageIcon,
  LayoutGrid,
  Loader2,
  PackageSearch,
  Rows3,
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
import { CardForm } from "@/components/card-form"
import { DataTable, useTableState } from "@/components/data-table"
import {
  ProductGrid,
  Status,
  useCatalogueView,
  word,
} from "@/components/product-card"
import { mediaUrl } from "@/components/photo-step"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import {
  useDamage,
  useDeleteCard,
  useProduct,
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
  const state = useTableState()
  const [openId, setOpenId] = useState<number | null>(null)
  const [view, setView] = useCatalogueView()
  const products = useProducts(state.q, status, stock)

  if (openId) return <Card id={openId} onBack={() => setOpenId(null)} />

  return (
    <div className="space-y-4">
      <PageHeader title="Mahsulotlar" subtitle="Kataloq — kompaniyaniki" />

      {/* The toolbar is the table's in both views — one search box, one set of
          filters, one export, one address bar. Only the records are drawn
          differently, so the card view hands the table a `body` and the table
          keeps everything else. It used to hide the rows with a selector
          against the table's own internals, which left every catalogue row in
          the document: read aloud by a screen reader, tabbed into, and
          clickable by anything driving the page. */}
      <DataTable<AdminProduct>
        body={
          view === "grid"
            ? (rows) => <ProductGrid cards={rows} onOpen={setOpenId} />
            : undefined
        }
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
          what: "Kartalar qabul ekranida yoziladi.",
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
        afterSearch={
          // Which shape of the same page. Remembered, because whoever wants
          // figures wants them every morning and whoever wants pictures never
          // wants figures.
          <Segmented
            label="Ko'rinish"
            value={view}
            onChange={setView}
            options={[
              {
                key: "grid" as const,
                label: (
                  <span className="flex items-center gap-1.5">
                    <LayoutGrid className="size-4" />
                    Kartalar
                  </span>
                ),
              },
              {
                key: "table" as const,
                label: (
                  <span className="flex items-center gap-1.5">
                    <Rows3 className="size-4" />
                    Jadval
                  </span>
                ),
              },
            ]}
          />
        }
        columns={[
          // The picture leads the row. It was a count in the fourth column —
          // "3", "0", "1" — which is a figure about photographs rather than a
          // look at the goods, and the one thing a person scanning a catalogue
          // of black trainers actually reads.
          {
            key: "image_count",
            header: "Rasm",
            width: "1%",
            sortable: true,
            sortValue: (row) => row.image_count,
            cell: (row) => <Thumb row={row} />,
            // A picture exports as nothing; the count is what a spreadsheet
            // can hold, and it is what this column used to be.
            export: (row) => groups(row.image_count),
          },
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
      {/* **Two lines on a phone, one at a desk.** Five inflexible children in
          a non-wrapping row is a row that cannot get narrower than its
          contents: at 390px the price was drawn on top of the SKU and the
          colour·size label broke into stacked fragments. `basis-full` gives
          the name and the code a line of their own below `sm`, and the four
          short things — price, count, Brak, Olib tashlash — share the line
          under it and may wrap again between themselves if they must. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <div className="min-w-0 flex-1 basis-full sm:basis-0">
          <div className="text-small font-medium">
            {variant.label}
            {variant.retired ? (
              <Pill className="ml-2 font-normal">sotuvda emas</Pill>
            ) : null}
          </div>
          <div className="truncate text-micro tabular text-ink-faint">
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
        {/* A verb, and in the warn ink even at rest. It used to read "Brak" in
            the same grey as "javonda bor" beside it — an action dressed as a
            state, which people read as "this size *is* damaged" on a row where
            nothing had been written off. */}
        {variant.stock_left > 0 ? (
          <button
            type="button"
            onClick={() => setDamaging((was) => !was)}
            className={cn(
              "shrink-0 text-micro text-warn-ink underline decoration-dotted underline-offset-2 hover:decoration-solid",
              damaging && "font-medium decoration-solid",
            )}>
            Brakka chiqarish
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

/**
 * The goods, in the row — a 40px square where a count used to be.
 *
 * **Why the empty square is the point.** A card with no photograph is the
 * `Rasmsiz` queue: the whole reason the list has a filter for it, and the one
 * thing holding goods out of the shop. A dashed warn-toned box beside a title
 * says that at a glance, in a way "0" in a grey column never did.
 *
 * **Where the picture comes from.** `cover_url` — the catalogue cover, the
 * photograph the customer meets, chosen by the same ordering the apps read. Not
 * the identification snapshot: that one is taken at the bench to tell two black
 * trainers apart and is never shown to a customer, so showing it here would put
 * a different picture in the office's list than the one on sale.
 *
 * The server sends `""` for a card with no photographs, which is the `Rasmsiz`
 * queue and draws the warn-toned box above.
 */
function Thumb({ row }: { row: AdminProduct }) {
  const shot = row.cover_url ?? ""

  if (shot) {
    return (
      <img
        src={mediaUrl(shot)}
        alt=""
        loading="lazy"
        className="size-10 shrink-0 rounded-control border border-line bg-canvas object-cover"
      />
    )
  }

  return (
    <span
      aria-label={row.image_count ? "rasm bor" : "rasmsiz"}
      title={row.image_count ? `${groups(row.image_count)} ta rasm` : "rasmsiz"}
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-control border border-dashed",
        row.image_count
          ? "border-line text-ink-faint"
          : "border-warn/50 bg-warn-soft text-warn-ink",
      )}
    >
      <ImageIcon className="size-4" />
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
  const card = useProduct(id)
  const grid = useVariants(id)
  const publish = usePublish(id)
  const retire = useRetireVariant(id)

  const product = card.data
  const live = product?.status === "active"

  return (
    <div className="space-y-4">
      <PageHeader
        title={product?.title ?? "Karta"}
        subtitle={product ? `${product.sku} · ${money(product.price)}` : ""}
      >
        {/* Taking a card back out of the shop is the one act on this screen
            that is not part of writing it, so it is a header action rather
            than a bar across the foot of the form. */}
        {live ? (
          <Button
            variant="ghost"
            size="sm"
            className="gap-1"
            disabled={publish.isPending}
            onClick={() => publish.mutate("archived")}
          >
            {publish.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Archive className="size-4" />
            )}
            Sotuvdan olish
          </Button>
        ) : null}
        <DeleteCard id={id} title={product?.title ?? ""} onGone={onBack} />
        <Button variant="ghost" onClick={onBack}>
          Ro'yxatga
        </Button>
      </PageHeader>

      <Problem error={card.error || publish.error || retire.error} />

      {/* The whole card, in the one form the receiving desk also opens — the
          publish gate at its top, then the words, the specs, the photographs
          and the price, in one column. There is no "Tahrirlash" button any
          more: a card that is open is a card being written. */}
      <CardForm productId={id} mode="catalogue" />

      <Panel title="Rang × o'lcham">
        {grid.isLoading ? <Waiting /> : null}
        {grid.data?.length === 0 ? (
          <Empty bare what="To'r hali yaratilmagan." />
        ) : null}
        {/* Where a colour comes from, said once and here: the receiving desk.
            Somebody publishing a card asked whether they were meant to be
            adding colours on this screen — nothing on it invents one, and a
            colour with no goods behind it would be a shop window offering
            something the room does not have. */}
        <p className="mb-2 text-micro text-ink-faint">
          Ranglar va o'lchamlar qabulda yoziladi. Bu yerda faqat rasm, narx va
          sotuvga chiqarish.
        </p>
        <Problem error={grid.error} />
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
    </div>
  )
}
