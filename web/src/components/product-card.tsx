/**
 * One card in the catalogue — the goods, not a row about the goods.
 *
 * **The photograph is the card.** A catalogue of black trainers is unreadable
 * as titles, and a 20-pixel thumbnail beside eight columns of figures is a
 * list somebody reads rather than one they scan. So the picture is the biggest
 * thing on the card and everything else sits beside it.
 *
 * **Four facts and no more**: the name, the code, the price, what is on the
 * shelf. The reference this was drawn against carries nine metrics and two
 * full-width grey bars, and the result is a card where nothing is the product
 * — *"uzun uzun qilib qo'yma buttonlarni"*. The state is a pill, and the four
 * things that can be done to a card live behind the `⋯` at the foot, so the
 * card is the picture and the menu is a menu.
 *
 * **A card with no photograph shows the gap and the reason in the same pixel.**
 * The dashed `rasm yo'q` frame is also what is holding the card out of the
 * shop; nobody has to read a status word to know which cards need work.
 *
 * **The slack goes into the picture.** A grid stretches every card in a row to
 * the tallest of them, and the first drawing spent that slack on a hole: the
 * facts ended a third of the way up and a ruled band underneath carried
 * nothing but the `⋯`. Measured at 1440 that was 75 of 214 pixels empty. The
 * photograph is the one thing on a card that is better bigger, so it is the
 * element that stretches — the column beside it keeps its natural height and
 * the row equalises by growing the goods.
 */

import {
  Archive,
  ImageOff,
  MoreHorizontal,
  Pencil,
  Printer,
  Store,
  Undo2,
} from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { Code } from "@/components/copy"
import { Pill, type Tone } from "@/components/page"
import { mediaUrl } from "@/components/photo-step"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/cn"
import { groups, money } from "@/lib/format"
import { usePublish, useVariants } from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

/** The one word for a card's state — on the pill, and in an export. */
export function word(status: AdminProduct["status"]): string {
  return status === "active" ? "sotuvda" : status === "draft" ? "rasmsiz" : "arxiv"
}

export function Status({ status }: { status: AdminProduct["status"] }) {
  const tone: Tone =
    status === "active" ? "good" : status === "draft" ? "warn" : "neutral"
  return <Pill tone={tone}>{word(status)}</Pill>
}

export function ProductCard({
  card,
  onOpen,
}: {
  card: AdminProduct
  onOpen: () => void
}) {
  const publish = usePublish(card.id)
  const next = card.next_statuses
  // The gates are the server's. An item that fires a request certain to be
  // refused is worse than one that opens the form where the gates are listed.
  const ready = card.unready.length === 0

  return (
    <article
      onClick={onOpen}
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return
        if (event.target !== event.currentTarget) return
        event.preventDefault()
        onOpen()
      }}
      className={cn(
        "flex cursor-pointer items-stretch gap-3 rounded-panel border border-line bg-surface p-3 shadow-panel",
        "transition-colors hover:border-brand/40 hover:bg-line-soft/40",
        "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
      )}
    >
      <Shot card={card} />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h3 className="line-clamp-2 text-small font-medium [overflow-wrap:anywhere]">
          {card.title}
        </h3>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-micro text-ink-soft">
          <Code>{card.sku}</Code>
          <Status status={card.status} />
        </div>
        <div className="mt-0.5 text-body font-semibold tabular [overflow-wrap:anywhere]">
          {money(card.price)}
        </div>

        {/* The last line of the card carries the shelf **and** the menu.
            `mt-auto` keeps the `⋯` of every card in a grid row on one line —
            a menu that stopped wherever its card's text stopped would read as
            a ragged column of dots rather than one place to press — and
            sharing the line with the facts is what stops it costing a band of
            its own. */}
        <div className="mt-auto flex items-end gap-2 pt-1">
          <div className="min-w-0 flex-1 space-y-0.5">
            {/* What is on the shelf. The colour count is not on the catalogue
                row, so this says what the row does know — and each fact holds
                together when the line has to wrap, because a 262px column
                breaks it in the middle otherwise and "20 dona · 2" over
                "variant" is a figure cut from its unit. */}
            <div className="text-micro tabular text-ink-soft">
              <span className="whitespace-nowrap">
                {groups(card.stock_left)} dona
              </span>
              {" · "}
              <span className="whitespace-nowrap">
                {groups(card.variant_count)} variant
              </span>
            </div>
            {/* By name, and only when true. A card is rarely out of stock as a
                whole — one colour of it is, the total still reads comfortably,
                and nobody hears about it until a customer orders that
                colour. */}
            {card.sold_out.length > 0 && card.status === "active" ? (
              <div className="line-clamp-2 text-micro text-danger">
                Tugagan: {card.sold_out.join(", ")}
              </div>
            ) : null}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger
              onClick={(event) => event.stopPropagation()}
              aria-label="Amallar"
              className={cn(
                "grid size-control shrink-0 place-items-center rounded-control text-ink-soft",
                "transition-colors hover:bg-line-soft hover:text-ink",
                "focus-visible:outline-2 focus-visible:outline-brand data-[state=open]:bg-line-soft",
              )}
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="end"
              onClick={(event) => event.stopPropagation()}
            >
              {next.includes("active") ? (
                <DropdownMenuItem
                  disabled={publish.isPending}
                  onSelect={() => (ready ? publish.mutate("active") : onOpen())}
                >
                  <Store />
                  Do'konga chiqarish
                  {ready ? null : (
                    <span className="ml-auto text-micro text-warn-ink">
                      {groups(card.unready.length)} ta shart
                    </span>
                  )}
                </DropdownMenuItem>
              ) : null}

              <DropdownMenuItem onSelect={onOpen}>
                <Pencil />
                Tahrirlash
              </DropdownMenuItem>

              <Labels productId={card.id} />

              {next.includes("draft") && card.status === "archived" ? (
                <DropdownMenuItem
                  disabled={publish.isPending}
                  onSelect={() => publish.mutate("draft")}
                >
                  <Undo2 />
                  Arxivdan qaytarish
                </DropdownMenuItem>
              ) : null}

              {next.includes("archived") ? (
                <DropdownMenuItem
                  tone="danger"
                  disabled={publish.isPending}
                  onSelect={() => publish.mutate("archived")}
                >
                  <Archive />
                  Arxivga
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </article>
  )
}

/**
 * The goods, and the empty frame that says why the card is not in the shop.
 *
 * `cover_url` is the catalogue cover — the photograph the customer meets,
 * chosen by the same ordering the apps read. Not the identification snapshot:
 * that one is taken at the bench to tell two black trainers apart and is never
 * shown to a customer, so showing it here would put a different picture in the
 * office's list than the one on sale.
 *
 * Fixed width, free height: it fills the row it is in, so a card made taller
 * by a neighbour's second line of title spends that height on the goods.
 * `min-h-24` is the floor, which is the square this used to be.
 */
function Shot({ card }: { card: AdminProduct }) {
  if (card.cover_url) {
    return (
      <img
        src={mediaUrl(card.cover_url)}
        alt=""
        loading="lazy"
        className="w-24 min-h-24 shrink-0 self-stretch rounded-control border border-line bg-canvas object-cover"
      />
    )
  }

  return (
    <span
      className={cn(
        "grid w-24 min-h-24 shrink-0 self-stretch place-items-center gap-1 rounded-control border border-dashed text-center",
        card.image_count
          ? "border-line text-ink-faint"
          : "border-warn/50 bg-warn-soft text-warn-ink",
      )}
    >
      <ImageOff className="size-5" />
      <span className="text-micro">rasm yo'q</span>
    </span>
  )
}

/**
 * The stickers for this card, at 58 mm, one per unit.
 *
 * The labels screen takes cells rather than cards, so the ids are fetched when
 * the menu opens and not before — thirty catalogue cards on screen must not be
 * thirty requests for a list nobody asked to see.
 */
function Labels({ productId }: { productId: number }) {
  const navigate = useNavigate()
  const grid = useVariants(productId)
  const cells = (grid.data ?? []).filter((one) => !one.retired)

  return (
    <DropdownMenuItem
      disabled={grid.isLoading || cells.length === 0}
      onSelect={() =>
        navigate(
          `/yorliqlar?${cells.map((one) => `variant_id=${one.id}`).join("&")}`,
        )
      }
    >
      <Printer />
      Yorliq chiqarish
      {grid.isLoading ? (
        <span className="ml-auto text-micro text-ink-faint">yuklanmoqda</span>
      ) : null}
    </DropdownMenuItem>
  )
}

/**
 * The catalogue as cards — and what it says when there are none.
 *
 * `repeat(auto-fill, minmax(260px, 1fr))`: one column on a phone, four at
 * 1280 and five at 1440, with no breakpoint deciding it.
 */
export function ProductGrid({
  cards,
  onOpen,
}: {
  cards: AdminProduct[]
  onOpen: (id: number) => void
}) {
  return (
    <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
      {cards.map((card) => (
        <ProductCard key={card.id} card={card} onOpen={() => onOpen(card.id)} />
      ))}
    </div>
  )
}

/** Cards or figures — the office sometimes wants two hundred rows. */
export type CatalogueView = "grid" | "table"

const KEY = "mb:catalogue-view"

export function useCatalogueView() {
  const [view, setView] = useState<CatalogueView>(() =>
    localStorage.getItem(KEY) === "table" ? "table" : "grid",
  )

  return [
    view,
    (next: CatalogueView) => {
      localStorage.setItem(KEY, next)
      setView(next)
    },
  ] as const
}
