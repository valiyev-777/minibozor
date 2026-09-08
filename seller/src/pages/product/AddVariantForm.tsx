import * as React from "react"
import { Plus, Trash2 } from "lucide-react"
import { api } from "@/api/client"
import type { Listing, ListingVariantsIn } from "@/api/types"
import { Button } from "@/ui/button"
import { Hint, Input, Label, Select } from "@/ui/field"
import { ColourPicker } from "@/components/ColourPicker"
import { useAction } from "@/lib/mutate"
import { t } from "@/lib/labels"

/**
 * A colour or a size the card did not have, and the goods with it.
 *
 * The gap this closes: "Qo'shimcha topshirish" could only send another box of
 * something already on the card, so a shop that started selling a shirt in
 * black and later got it in blue had to open a **second card** for the blue
 * one — new photographs, a second price to keep in step, two rows in the shop
 * for one thing.
 *
 * Two modes, because a seller wants one of two things and asking them to
 * understand a single form that does both would be asking them to understand
 * our data model:
 *
 * - **a new colour** — a swatch, its own photograph, and the sizes it comes in;
 * - **a new size** — a label and a quantity, under a colour they already have.
 *
 * Both post to `POST /staff/catalog/listings/{id}/variants`, which reuses what
 * is already there and writes only what is new. So sending a colour that
 * exists is not an error, and the form does not have to work out the
 * difference between what the card has and what the seller typed.
 *
 * The quantity is not optional in either mode. A colour with no goods behind
 * it is a swatch a customer can tap and never buy, and the whole reason this
 * form creates a batch at the same time is so that state cannot exist.
 */
type SizeDraft = { key: number; label: string; quantity: string }

let nextKey = 1
const key = () => nextKey++
const emptySize = (): SizeDraft => ({ key: key(), label: "", quantity: "" })

export function AddVariantForm({
  listing,
  onClose,
}: {
  listing: Listing
  onClose: () => void
}) {
  // Which colours the card already has, and whether it uses sizes at all.
  const colours = React.useMemo(() => {
    const seen = new Map<string, string>()
    for (const cell of listing.stock) seen.set(cell.color_label, cell.color_label)
    return [...seen.keys()]
  }, [listing.stock])
  const hasSizes = listing.stock.some((cell) => cell.size_label)

  const [mode, setMode] = React.useState<"colour" | "size">(
    // A card with no sizes has nothing to add a size to, so the choice is not
    // offered — it opens on the only thing it can do.
    hasSizes && colours.length ? "size" : "colour",
  )
  const [colour, setColour] = React.useState({ label: "", value: "", image_url: "" })
  const [under, setUnder] = React.useState(colours[0] ?? "")
  const [sizes, setSizes] = React.useState<SizeDraft[]>([emptySize()])

  const send = useAction<ListingVariantsIn, Listing>({
    run: (body) =>
      api<Listing>(`/staff/catalog/listings/${listing.id}/variants`, {
        method: "POST",
        json: body,
      }),
    invalidate: [["listings"], ["listing", String(listing.id)], ["supplies"]],
    success: t.variantAdded,
    onDone: onClose,
  })

  const rows = sizes
    .filter((size) => size.label.trim() && Number(size.quantity) > 0)
    .map((size) => ({
      label: size.label.trim(),
      value: size.label.trim(),
      quantity: Number(size.quantity),
    }))

  const ready =
    mode === "colour"
      ? Boolean(colour.label.trim() && colour.image_url) &&
        (hasSizes ? rows.length > 0 : true)
      : Boolean(under) && rows.length > 0

  function submit(event: React.FormEvent) {
    event.preventDefault()
    send.mutate({
      colors:
        mode === "colour"
          ? [
              {
                label: colour.label.trim(),
                value: colour.value,
                image_url: colour.image_url,
                sizes: hasSizes ? rows : [],
                // Counted on the colour when there are no sizes under it.
                quantity: hasSizes ? 0 : Number(sizes[0]?.quantity) || 0,
              },
            ]
          : // The existing colour, named, with only the new sizes under it.
            // Its photograph is not resent: the server asks for one only for
            // a colour it has never seen.
            [{ label: under, value: "", sizes: rows, quantity: 0 }],
    })
  }

  return (
    <form className="space-y-4 border-t border-line bg-surface-soft px-5 py-4" onSubmit={submit}>
      {hasSizes && colours.length ? (
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            size="sm"
            variant={mode === "size" ? "primary" : "outline"}
            onClick={() => setMode("size")}
          >
            {t.newSize}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={mode === "colour" ? "primary" : "outline"}
            onClick={() => setMode("colour")}
          >
            {t.newColour}
          </Button>
        </div>
      ) : (
        <p className="text-[length:var(--text-small)] font-medium text-ink">
          {t.newColour}
        </p>
      )}

      {mode === "colour" ? (
        <ColourPicker colour={colour} onChange={(patch) => setColour({ ...colour, ...patch })} />
      ) : (
        <div className="max-w-xs space-y-1.5">
          <Label htmlFor="under-colour">{t.underColour}</Label>
          <Select
            id="under-colour"
            value={under}
            onChange={(event) => setUnder(event.target.value)}
          >
            {colours.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </div>
      )}

      {mode === "size" || hasSizes ? (
        <div className="space-y-2">
          <p className="text-[length:var(--text-small)] font-medium text-ink">
            {t.sizesAndCount}
          </p>
          {sizes.map((size, at) => (
            <div key={size.key} className="flex items-end gap-2">
              <div className="min-w-0 flex-1 space-y-1.5">
                <Label htmlFor={`new-size-${size.key}`} className="sr-only">
                  {t.sizeLabel}
                </Label>
                <Input
                  id={`new-size-${size.key}`}
                  value={size.label}
                  placeholder={t.sizeLabel}
                  onChange={(event) =>
                    setSizes(
                      sizes.map((row, i) =>
                        i === at ? { ...row, label: event.target.value } : row,
                      ),
                    )
                  }
                />
              </div>
              <div className="w-28 space-y-1.5">
                <Label htmlFor={`new-qty-${size.key}`} className="sr-only">
                  {t.quantity}
                </Label>
                <Input
                  id={`new-qty-${size.key}`}
                  inputMode="numeric"
                  value={size.quantity}
                  placeholder={t.quantity}
                  onChange={(event) =>
                    setSizes(
                      sizes.map((row, i) =>
                        i === at
                          ? { ...row, quantity: event.target.value.replace(/\D/g, "") }
                          : row,
                      ),
                    )
                  }
                />
              </div>
              {sizes.length > 1 ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label={t.removeSize}
                  onClick={() => setSizes(sizes.filter((_, i) => i !== at))}
                >
                  <Trash2 />
                </Button>
              ) : null}
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setSizes([...sizes, emptySize()])}
          >
            <Plus />
            {t.addSize}
          </Button>
        </div>
      ) : (
        <div className="max-w-xs space-y-1.5">
          <Label htmlFor="colour-qty">{t.quantity}</Label>
          <Input
            id="colour-qty"
            inputMode="numeric"
            value={sizes[0]?.quantity ?? ""}
            onChange={(event) =>
              setSizes([
                {
                  key: sizes[0]?.key ?? key(),
                  label: colour.label || "-",
                  quantity: event.target.value.replace(/\D/g, ""),
                },
              ])
            }
          />
        </div>
      )}

      <Hint>{t.addVariantHint}</Hint>

      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={!ready || send.isPending}>
          {send.isPending ? t.submitting : t.submit}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          {t.cancel}
        </Button>
      </div>
    </form>
  )
}
