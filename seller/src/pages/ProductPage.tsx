import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, PackagePlus, Truck } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Listing, Offer, Removal, Supply } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Input, Label } from "@/ui/field"
import { Async } from "@/ui/states"
import { Detail, Panel, Row } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { useAction } from "@/lib/mutate"
import { num, som } from "@/lib/format"
import { supplyStatus, t } from "@/lib/labels"

/**
 * One product, and the three things a seller can still do to it.
 *
 * After submission the card itself is not theirs to edit — an admin fixes what
 * needs fixing and the warehouse decides whether it is in the shop. What stays
 * theirs is the *price*, and two decisions about the goods: send more, or ask
 * for what is here back. Everything else on this screen is an answer to "what
 * happened to my thing", including the refusal, which is the one sentence a
 * refused seller needs and used to have nowhere to read.
 *
 * The two actions are per cell rather than per product, because that is how
 * the shelf is counted: black L and white L are different goods. A cell with
 * nothing on the shelf offers no way to take anything back, which is not a
 * disabled button but an absent one — there is nothing there to collect.
 */
export function ProductPage() {
  const { id } = useParams()
  const listing = useQuery({
    queryKey: ["listing", id],
    queryFn: () => api<Listing>(`/staff/catalog/listings/${id}`),
    enabled: Boolean(id),
  })

  return (
    <>
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/products">
            <ArrowLeft />
            {t.products}
          </Link>
        </Button>
      </div>

      <Async query={listing} lines={5}>
        {(row) => <Detailed row={row} />}
      </Async>
    </>
  )
}

function Detailed({ row }: { row: Listing }) {
  return (
    <div className="space-y-[var(--gap-page)]">
      <Panel>
        <div className="flex flex-wrap gap-5 px-5 py-5">
          <div className="flex gap-2">
            {row.images.slice(0, 3).map((url) => (
              <Thumb key={url} src={url} className="size-20" />
            ))}
          </div>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-semibold text-ink">{row.title}</h1>
              <Badge
                tone={
                  row.stage === "on_sale"
                    ? "good"
                    : row.stage === "rejected"
                      ? "danger"
                      : row.stage === "awaiting_warehouse"
                        ? "warn"
                        : "neutral"
                }
              >
                {row.stage_label}
              </Badge>
            </div>
            <p className="text-[length:var(--text-small)] text-ink-soft">{row.subtitle}</p>
            <p className="text-[length:var(--text-micro)] text-ink-faint">{row.sku}</p>
          </div>
          <div className="flex gap-8">
            <Detail label={t.onHand}>
              <span className="tabular">{num(row.on_hand_total)}</span>
            </Detail>
            <Detail label={t.sellable}>
              <span className="tabular">{num(row.sellable_total)}</span>
            </Detail>
          </div>
        </div>

        {/* The one sentence a refused seller needs. Loud, because they are
            being asked to fix something and cannot if they miss it. */}
        {row.moderation_note ? (
          <div
            role="alert"
            className="border-t border-line bg-danger-soft px-5 py-4 text-[length:var(--text-small)] text-danger"
          >
            <p className="font-semibold">{t.refusalReason}</p>
            <p>{row.moderation_note}</p>
          </div>
        ) : null}
      </Panel>

      {row.offer_id ? <PriceBox listing={row} /> : null}

      <StockBox listing={row} />
    </div>
  )
}

/**
 * The price, which stays the seller's after everything else stops being.
 *
 * Read through `GET /staff/offers?product_id=` rather than off the listing:
 * the listing carries the price as a figure to show, and this box is about
 * changing it, so it wants the offer it is going to PATCH.
 */
function PriceBox({ listing }: { listing: Listing }) {
  const offers = useQuery({
    queryKey: ["offers", listing.id],
    queryFn: () =>
      api<Offer[]>("/staff/offers", { query: { product_id: listing.id } }),
  })
  const offer = offers.data?.find((row) => row.id === listing.offer_id)

  const [price, setPrice] = React.useState<string>("")
  React.useEffect(() => {
    if (offer) setPrice(String(offer.price))
  }, [offer])

  const save = useAction<number, Offer>({
    run: (next) =>
      api<Offer>(`/staff/offers/${listing.offer_id}`, {
        method: "PATCH",
        json: { price: next },
      }),
    invalidate: [["listings"], ["listing", String(listing.id)], ["offers", listing.id]],
    success: t.priceSaved,
  })

  const changed = offer ? Number(price) > 0 && Number(price) !== offer.price : false

  return (
    <Panel title={t.price}>
      <form
        className="flex flex-wrap items-end gap-3 border-t border-line-soft px-5 py-5"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate(Number(price))
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="price">{t.price}</Label>
          <Input
            id="price"
            inputMode="numeric"
            className="w-40"
            value={price}
            onChange={(event) => setPrice(event.target.value.replace(/\D/g, ""))}
          />
        </div>
        <Button type="submit" variant="primary" disabled={!changed || save.isPending}>
          {t.savePrice}
        </Button>
        <p className="text-[length:var(--text-small)] text-ink-soft">
          Hozirgi narx: <span className="tabular">{som(offer?.price)}</span>
        </p>
      </form>
    </Panel>
  )
}

/**
 * The grid, one row per countable cell, with the two decisions beside it.
 *
 * `declared` and `on_hand` are shown side by side deliberately: the gap
 * between what a seller said was coming and what the warehouse found is the
 * only thing either party wants to talk about afterwards.
 */
function StockBox({ listing }: { listing: Listing }) {
  const [sending, setSending] = React.useState<Record<number, string>>({})
  const [taking, setTaking] = React.useState<Record<number, string>>({})

  const declare = useAction<{ variantId: number; quantity: number }, Supply>({
    run: ({ variantId, quantity }) =>
      api<Supply>("/staff/supplies", {
        method: "POST",
        json: {
          lines: [
            { offer_id: listing.offer_id, variant_id: variantId, quantity },
          ],
        },
      }),
    invalidate: [["listings"], ["listing", String(listing.id)], ["supplies"]],
    success: (made) => `${t.supplyDeclared} — ${made.code}`,
    onDone: () => setSending({}),
  })

  const remove = useAction<{ variantId: number; quantity: number }, Removal>({
    run: ({ variantId, quantity }) =>
      api<Removal>("/staff/removals", {
        method: "POST",
        json: {
          // `unsold` rather than a choice on this screen. A seller taking
          // goods back off a product page is taking back stock that is not
          // moving; "unsellable" is a claim about damage, which is the
          // warehouse's to make when they look at it.
          reason: "unsold",
          lines: [
            { offer_id: listing.offer_id, variant_id: variantId, quantity },
          ],
        },
      }),
    invalidate: [["listings"], ["listing", String(listing.id)], ["removals"]],
    success: (made) => `${t.removalRequested} — ${made.code}`,
    onDone: () => setTaking({}),
  })

  return (
    <Panel title={`${t.colors} · ${t.sizes}`}>
      <div className="hidden border-t border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
        <span className="flex-1">{t.colors}</span>
        <span className="w-16 text-right">{t.declared}</span>
        <span className="w-16 text-right">{t.onHand}</span>
        <span className="w-16 text-right">{t.sellable}</span>
        <span className="w-[19rem]" />
      </div>

      {listing.stock.map((cell) => (
        <Row key={cell.variant_id} className="sm:flex-nowrap">
          <p className="min-w-0 flex-1 text-[length:var(--text-body)] text-ink">
            {cell.color_label}
            {cell.size_label ? (
              <span className="text-ink-soft"> · {cell.size_label}</span>
            ) : null}
          </p>
          <span className="tabular w-16 text-right text-[length:var(--text-body)] text-ink-soft">
            {num(cell.declared)}
          </span>
          <span className="tabular w-16 text-right text-[length:var(--text-body)] text-ink">
            {num(cell.on_hand)}
          </span>
          <span className="tabular w-16 text-right text-[length:var(--text-body)] text-ink">
            {num(cell.sellable)}
          </span>

          <div className="flex w-full flex-wrap items-center gap-2 sm:w-[19rem] sm:justify-end">
            <Input
              inputMode="numeric"
              aria-label={`${cell.color_label} ${cell.size_label ?? ""} ${t.quantity}`}
              className="w-20"
              placeholder="0"
              value={sending[cell.variant_id] ?? ""}
              onChange={(event) =>
                setSending({
                  ...sending,
                  [cell.variant_id]: event.target.value.replace(/\D/g, ""),
                })
              }
            />
            <Button
              size="sm"
              disabled={
                !Number(sending[cell.variant_id]) || declare.isPending || !listing.offer_id
              }
              onClick={() =>
                declare.mutate({
                  variantId: cell.variant_id,
                  quantity: Number(sending[cell.variant_id]),
                })
              }
            >
              <PackagePlus />
              {t.addMore}
            </Button>

            {cell.on_hand > 0 ? (
              <>
                <Input
                  inputMode="numeric"
                  aria-label={`${cell.color_label} ${t.takeBack}`}
                  className="w-20"
                  placeholder={String(cell.on_hand)}
                  value={taking[cell.variant_id] ?? ""}
                  onChange={(event) =>
                    setTaking({
                      ...taking,
                      [cell.variant_id]: event.target.value.replace(/\D/g, ""),
                    })
                  }
                />
                <Button
                  size="sm"
                  variant="quiet"
                  disabled={!Number(taking[cell.variant_id]) || remove.isPending}
                  onClick={() =>
                    remove.mutate({
                      variantId: cell.variant_id,
                      quantity: Number(taking[cell.variant_id]),
                    })
                  }
                >
                  <Truck />
                  {t.takeBack}
                </Button>
              </>
            ) : null}
          </div>
        </Row>
      ))}

      {listing.supply_code ? (
        <div className="border-t border-line-soft px-5 py-3 text-[length:var(--text-small)] text-ink-soft">
          {t.supplies}: <span className="text-ink">{listing.supply_code}</span> ·{" "}
          {supplyStatus[listing.supply_status ?? ""] ?? listing.supply_status}
        </div>
      ) : null}
    </Panel>
  )
}
