/**
 * §5.2 ·10 — the price, as a table, because that is what it is.
 *
 * One row per variant: `Rang · O'lcham · Shtrix-kod · Tannarx · Narx ·
 * Chegirma · Sotish narxi`.
 *
 * **Three of the seven columns are not typed.** The barcode is ours and is
 * already on a sticker on a shelf (§6.5). *Tannarx* comes off the receipt —
 * it is what the goods cost at the market, captured at the bench with the sack
 * open, and retyping it here would be inventing a second answer to a question
 * that already has one. *Sotish narxi* is arithmetic, and a shop where the
 * discount and the final price are both typed is a shop where they disagree.
 *
 * **One price for the card, with a per-row override.** Pricing twelve cells
 * through twelve requests is how a card stays in the publishing queue for a
 * week, so the strip at the top prices the whole card in one write — and the
 * 43 that really does cost more is repriced on its own row.
 *
 * **The markup is offered, not the price.** `+60%` is how the person who
 * bought them thinks; `174 000` is the answer to a sum they would rather not
 * do. Rounded to the thousand, the way every price in this shop is.
 *
 * *Chegirma is a percentage and it is not stored as one.* The variant carries
 * the money it actually sells for, so a reopened card derives the discount
 * back from the two figures. That is lossy in one direction only — the sum is
 * always right, the split is a reconstruction — and it is the right trade
 * against adding a column to the ledger's neighbour for a display figure.
 *
 * **The table says what is stored; the strip says what is pending.** They used
 * to be mixed: the `Narx` column printed whatever was typed into the strip, so
 * pressing `+60%` made twelve rows read `Narx 192 000 · Sotish narxi 0` before
 * anything had been written, and each row's discount was derived against the
 * typed figure and jumped to a phantom 36% mid-keystroke. A figure nobody has
 * saved must not be printed in the column that says what a customer pays: the
 * pending sum gets a ghosted line of its own above the table, and the columns
 * do not move until `Qo'yish`.
 */

import { Loader2 } from "lucide-react"
import { useEffect, useState } from "react"

import { Swatch } from "@/components/card-form/bits"
import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { money } from "@/lib/format"
import { useColours, usePriceCard, useRepriceVariant, useVariants } from "@/lib/queries"
import type { AdminProduct } from "@/lib/types"

/** Every price here is a round thousand; nobody in this shop charges 174 300. */
const thousand = (amount: number) => Math.round(amount / 1000) * 1000

/** What is left after the discount — the only place this sum is done. */
const after = (list: number, discount: number) =>
  Math.max(0, thousand((list * (100 - discount)) / 100))

/** Digits only: a price field that accepts `1 2 0.k` is a price field that lies. */
const digits = (value: string) => value.replace(/\D/g, "")

/** The discount two stored figures work out to, or 0 when there is none. */
const discountOf = (list: number, price: number) =>
  list > 0 && price > 0 && list > price ? Math.round((1 - price / list) * 100) : 0

export function PriceTable({ card }: { card: AdminProduct }) {
  const grid = useVariants(card.id)
  const palette = useColours()
  const priceCard = usePriceCard(card.id)
  const reprice = useRepriceVariant(card.id)

  const cost = card.last_cost
  const rows = grid.data ?? []
  const hex = new Map((palette.data ?? []).map((row) => [row.name, row.hex]))

  // The card's own figures. Seeded from what is stored once, then driven by
  // hand — a field reset underneath the cursor is the form that fights back.
  const [list, setList] = useState("")
  const [discount, setDiscount] = useState("0")
  const [seeded, setSeeded] = useState(false)
  // `old_price` is the struck-through figure, which is the list price
  // whenever there is a discount at all. Never below what the card actually
  // sells for: a few old cards carry an `old_price` under their `price`, and
  // a "list price" lower than the selling price is not a discount, it is
  // rubbish that would print a struck-through figure smaller than the one
  // beside it.
  const storedList = Math.max(card.old_price ?? 0, card.price)
  const storedDiscount = discountOf(storedList, card.price)
  useEffect(() => {
    if (seeded || !grid.data) return
    setList(storedList ? String(storedList) : "")
    setDiscount(String(storedDiscount))
    setSeeded(true)
  }, [grid.data, storedList, storedDiscount, seeded])

  const listNumber = Number(list) || 0
  const discountNumber = Math.min(90, Math.max(0, Number(discount) || 0))
  const selling = after(listNumber, discountNumber)
  const markup = cost > 0 && selling > 0 ? Math.round((selling / cost - 1) * 100) : 0
  // Typed but not written. The strip is a proposal until `Qo'yish`, and the
  // table below is what the shop is actually charging right now.
  const pending =
    seeded && (listNumber !== storedList || discountNumber !== storedDiscount)

  // Which row is being overridden, and with what. One at a time: a table of
  // twelve open inputs is twelve unsaved edits nobody can account for.
  const [override, setOverride] = useState<{ id: number; price: string } | null>(null)

  return (
    <div className="space-y-3">
      <div className="rounded-control bg-line-soft p-3">
        <p className="mb-2 text-micro text-ink-soft">
          Butun kartaga bitta narx. Qimmatroq o'lcham quyidagi jadvalda alohida
          o'zgartiriladi.
          {cost > 0 ? <> Tannarx — {money(cost)}.</> : null}
        </p>

        {cost > 0 ? (
          <div className="mb-2 flex flex-wrap gap-1">
            {[40, 60, 75, 100].map((percent) => (
              <button
                key={percent}
                type="button"
                onClick={() => {
                  setList(String(thousand((cost * (100 + percent)) / 100)))
                  setDiscount("0")
                }}
                className="h-control-sm rounded-control border border-line bg-surface px-2.5 text-micro tabular hover:bg-line-soft"
              >
                +{percent}%
              </button>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-end gap-2">
          <label className="w-32">
            <span className="mb-1 block text-micro text-ink-soft">Narx</span>
            <Input
              value={list}
              onChange={(event) => setList(digits(event.target.value))}
              inputMode="numeric"
              placeholder="290 000"
              aria-label="Narx"
              className="tabular"
            />
          </label>
          <label className="w-24">
            <span className="mb-1 block text-micro text-ink-soft">Chegirma %</span>
            <Input
              value={discount}
              onChange={(event) => setDiscount(digits(event.target.value))}
              inputMode="numeric"
              aria-label="Chegirma foizi"
              className="tabular"
            />
          </label>
          <div className="w-36">
            <span className="mb-1 block text-micro text-ink-soft">Sotish narxi</span>
            <output className="flex h-control items-center rounded-control bg-surface px-3 text-body font-semibold tabular">
              {selling ? money(selling) : "—"}
            </output>
          </div>
          <Button
            type="button"
            className="gap-2"
            disabled={selling <= 0 || priceCard.isPending}
            onClick={() => {
              setOverride(null)
              priceCard.mutate({
                price: selling,
                old_price: discountNumber > 0 ? listNumber : null,
              })
            }}
          >
            {priceCard.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
            Qo'yish
          </Button>
          {markup > 0 ? (
            <span className="pb-2 text-small text-ink-soft tabular">+{markup}%</span>
          ) : null}
        </div>
      </div>

      {/* The pending figure, drawn as pending: dashed, faint, and above the
          table rather than inside it. */}
      {pending ? (
        <p className="rounded-control border border-dashed border-warn/50 bg-warn-soft/40 px-3 py-2 text-micro text-warn-ink">
          Hali qo'yilmagan: narx{" "}
          <span className="tabular">{listNumber ? money(listNumber) : "—"}</span>
          {discountNumber > 0 ? (
            <>
              {" · chegirma "}
              <span className="tabular">{discountNumber}%</span>
            </>
          ) : null}
          {" · sotish narxi "}
          <span className="font-medium tabular">{selling ? money(selling) : "—"}</span>
          . Quyidagi jadval «Qo'yish» bosilgunicha hozirgi narxni ko'rsatadi.
        </p>
      ) : null}

      <Problem error={grid.error || priceCard.error || reprice.error} />

      {rows.length === 0 ? (
        <p className="text-micro text-ink-faint">
          Rang × o'lcham to'ri hali yo'q — narx qabuldan keyin qo'yiladi.
        </p>
      ) : (
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full text-small">
            <thead>
              <tr className="bg-line-soft text-micro font-medium text-ink-soft">
                <th className="px-3 py-2 text-left">Rang</th>
                <th className="px-3 py-2 text-left">O'lcham</th>
                <th className="px-3 py-2 text-left">Shtrix-kod</th>
                <th className="px-3 py-2 text-right">Tannarx</th>
                <th className="px-3 py-2 text-right">Narx</th>
                <th className="px-3 py-2 text-right">Chegirma</th>
                <th className="px-3 py-2 text-right">Sotish narxi</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, at) => {
                // This row's list price, off what is stored and nothing else.
                // A variant carries one figure — the money it sells for — so
                // the struck-through price is the card's, and it applies to a
                // row that is still selling at the card's own price. A row
                // repriced on its own is sold at that price, full stop.
                const rowList = row.price === card.price ? storedList : row.price
                const own = discountOf(rowList, row.price)
                const editing = override?.id === row.id
                const typed = Number(editing ? override.price : "") || 0
                return (
                  <tr
                    key={row.id}
                    className={cn(
                      at % 2 === 1 && "bg-line-soft/60",
                      row.retired && "opacity-50",
                    )}
                  >
                    <td className="px-3 py-2">
                      <span className="flex items-center gap-2">
                        <Swatch hex={row.colour_hex || hex.get(row.colour)} />
                        {row.colour || "—"}
                      </span>
                    </td>
                    <td className="px-3 py-2 tabular">{row.size || "—"}</td>
                    {/* Read-only and never a field: it is printed on a sticker
                        that is already on a shelf. */}
                    <td className="px-3 py-2 text-micro text-ink-soft tabular">
                      {row.barcode}
                    </td>
                    <td className="px-3 py-2 text-right tabular text-ink-soft">
                      {cost > 0 ? money(cost) : "—"}
                    </td>
                    <td className="px-3 py-2 text-right tabular">{money(rowList)}</td>
                    <td className="px-3 py-2 text-right tabular text-ink-soft">
                      {own ? `${own}%` : "0%"}
                    </td>
                    {/* The one figure this row can be overridden with is the
                        money it sells for, so that is the cell that opens —
                        seeded from the row's own stored price and not from
                        whatever the strip above is holding. */}
                    <td className="px-3 py-2 text-right">
                      {editing ? (
                        <span className="flex items-center justify-end gap-2">
                          <Input
                            autoFocus
                            value={override.price}
                            onChange={(event) =>
                              setOverride({
                                id: row.id,
                                price: digits(event.target.value),
                              })
                            }
                            inputMode="numeric"
                            aria-label={`${row.label} — sotish narxi`}
                            className="h-control-sm w-28 text-right tabular"
                          />
                          <Button
                            type="button"
                            size="sm"
                            disabled={typed <= 0 || reprice.isPending}
                            onClick={() =>
                              reprice.mutate(
                                { variantId: row.id, price: thousand(typed) },
                                { onSuccess: () => setOverride(null) },
                              )
                            }
                          >
                            Saqlash
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setOverride(null)}
                          >
                            Bekor
                          </Button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            setOverride({ id: row.id, price: String(row.price || "") })
                          }
                          className="font-medium tabular underline-offset-4 hover:underline"
                        >
                          {money(row.price)}
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
