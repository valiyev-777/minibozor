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
import { EditBox } from "@/pages/product/EditBox"
import { useAction } from "@/lib/mutate"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

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
            <Detail
              label={row.stage === "awaiting_warehouse" ? t.declaredShort : t.onHand}
            >
              <span className="tabular">
                {num(
                  row.stage === "awaiting_warehouse"
                    ? row.stock.reduce((sum, cell) => sum + cell.declared, 0)
                    : row.on_hand_total,
                )}
              </span>
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

      <EditBox listing={row} />

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
 * The goods, as one number a shopkeeper recognises.
 *
 * There used to be three columns here — declared, on hand, sellable — and a
 * seller reading them had to work out which of the three was the answer to
 * "how many have I got". They are one number now, and which number it is
 * follows the stage: before the warehouse has counted, the only true figure
 * is what was handed in; afterwards it is what is on the shelf, with the part
 * already promised to an order named beside it rather than given a column of
 * its own.
 *
 * The two decisions moved off the rows for the same reason. A seller does not
 * bring one size to the warehouse; they bring a box with several in it, and
 * a row of inputs repeated per size made a phone screen unreadable. Each
 * decision now opens one form over every size and sends one document.
 */
function StockBox({ listing }: { listing: Listing }) {
  const [open, setOpen] = React.useState<null | "send" | "take">(null)
  const waiting = listing.stage === "awaiting_warehouse"

  return (
    <Panel
      title={t.stock}
      action={
        !waiting ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={open === "send" ? "quiet" : "primary"}
              onClick={() => setOpen(open === "send" ? null : "send")}
            >
              <PackagePlus />
              {t.addMore}
            </Button>
            {listing.on_hand_total > 0 ? (
              <Button
                size="sm"
                variant="quiet"
                onClick={() => setOpen(open === "take" ? null : "take")}
              >
                <Truck />
                {t.takeBack}
              </Button>
            ) : null}
          </div>
        ) : null
      }
    >
      {listing.stock.map((cell) => {
        const promised = cell.on_hand - cell.sellable
        return (
          <Row key={cell.variant_id}>
            <p className="min-w-0 flex-1 text-[length:var(--text-body)] text-ink">
              {cell.color_label}
              {cell.size_label ? (
                <span className="text-ink-soft"> · {cell.size_label}</span>
              ) : null}
            </p>
            <span className="text-right text-[length:var(--text-body)] text-ink">
              <span className="tabular font-semibold">
                {num(waiting ? cell.declared : cell.on_hand)}
              </span>{" "}
              <span className="text-ink-soft">{t.pieces}</span>
              {!waiting && promised > 0 ? (
                <span className="text-[length:var(--text-micro)] text-ink-faint">
                  {" "}
                  · {num(promised)} {t.inOrder}
                </span>
              ) : null}
            </span>
          </Row>
        )
      })}

      <div className="border-t border-line-soft px-5 py-3 text-[length:var(--text-small)] text-ink-soft">
        {waiting ? (
          t.awaitingCount
        ) : (
          <>
            {t.totalOnHand}:{" "}
            <span className="tabular text-ink">{num(listing.on_hand_total)}</span>{" "}
            {t.pieces}
          </>
        )}
      </div>

      {open ? (
        <QuantityForm
          listing={listing}
          kind={open}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </Panel>
  )
}

/**
 * One quantity per size, and one document out of the lot.
 *
 * Both decisions have the same shape — a number against each size — so they
 * share the form and differ only in the endpoint and in what a blank means:
 * sending is bounded by nothing, taking back is bounded by what is on the
 * shelf, and the placeholder says that figure so nobody has to guess it.
 */
function QuantityForm({
  listing,
  kind,
  onClose,
}: {
  listing: Listing
  kind: "send" | "take"
  onClose: () => void
}) {
  const [qty, setQty] = React.useState<Record<number, string>>({})

  const lines = listing.stock
    .map((cell) => ({ cell, quantity: Number(qty[cell.variant_id] ?? "") }))
    .filter((line) => line.quantity > 0)

  const overshoot =
    kind === "take" && lines.some((line) => line.quantity > line.cell.on_hand)

  const send = useAction<void, Supply | Removal>({
    run: () =>
      kind === "send"
        ? api<Supply>("/staff/supplies", {
            method: "POST",
            json: {
              lines: lines.map((line) => ({
                offer_id: listing.offer_id,
                variant_id: line.cell.variant_id,
                quantity: line.quantity,
              })),
            },
          })
        : api<Removal>("/staff/removals", {
            method: "POST",
            json: {
              // `unsold` rather than a choice on this screen. A seller taking
              // goods back off a product page is taking back stock that is
              // not moving; "unsellable" is a claim about damage, which is
              // the warehouse's to make when they look at it.
              reason: "unsold",
              lines: lines.map((line) => ({
                offer_id: listing.offer_id,
                variant_id: line.cell.variant_id,
                quantity: line.quantity,
              })),
            },
          }),
    invalidate: [
      ["listings"],
      ["listing", String(listing.id)],
      [kind === "send" ? "supplies" : "removals"],
    ],
    success: kind === "send" ? t.supplyDeclared : t.removalRequested,
    onDone: () => {
      setQty({})
      onClose()
    },
  })

  return (
    <form
      className="border-t border-line bg-surface-soft px-5 py-4"
      onSubmit={(event) => {
        event.preventDefault()
        send.mutate()
      }}
    >
      <p className="mb-3 text-[length:var(--text-small)] font-semibold text-ink">
        {kind === "send" ? t.addMoreTitle : t.takeBackTitle}
      </p>

      <div className="space-y-2">
        {listing.stock.map((cell) => (
          <div key={cell.variant_id} className="flex items-center gap-3">
            <span className="min-w-0 flex-1 text-[length:var(--text-body)] text-ink">
              {cell.color_label}
              {cell.size_label ? (
                <span className="text-ink-soft"> · {cell.size_label}</span>
              ) : null}
            </span>
            <Input
              inputMode="numeric"
              aria-label={`${cell.color_label} ${cell.size_label ?? ""} ${t.quantity}`}
              className="w-24"
              placeholder={kind === "take" ? String(cell.on_hand) : "0"}
              value={qty[cell.variant_id] ?? ""}
              onChange={(event) =>
                setQty({
                  ...qty,
                  [cell.variant_id]: event.target.value.replace(/\D/g, ""),
                })
              }
            />
          </div>
        ))}
      </div>

      {overshoot ? (
        <p role="alert" className="mt-3 text-[length:var(--text-small)] text-danger">
          {t.moreThanOnHand}
        </p>
      ) : null}

      <div className="mt-4 flex gap-2">
        <Button
          type="submit"
          variant="primary"
          disabled={!lines.length || overshoot || send.isPending}
        >
          {kind === "send" ? t.addMore : t.takeBack}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          {t.cancel}
        </Button>
      </div>
    </form>
  )
}
