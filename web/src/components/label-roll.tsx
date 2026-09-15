/**
 * The label roll — a thermal printer, one sticker per unit.
 *
 * Not an A4 sheet of many labels: **one label per page, printed N times**, so
 * the driver advances the roll between them. Twenty shoes are twenty pages and
 * one `window.print()`. There is no grid, no gutter and no crop mark, because
 * nobody is cutting anything up.
 *
 * **Grouped, in the order they were typed.** Ten 43s, then ten 42s — matching
 * the piles standing on the table. Interleaved sizes would make the person
 * read every sticker before sticking it, which is the work the sticker exists
 * to remove.
 *
 * **The barcode is the variant's own**, permanent, and twenty stickers carry
 * the same one because twenty identical shoes are twenty of one thing. The
 * `n/copies` in the corner is not an identity, it is a counting aid: you know
 * you are finished when you have used `10/10`, which is the only check there
 * is that every unit got a sticker.
 *
 * **The price is not on it.** Prices change; a sticker does not.
 *
 * Printing takes the whole page, so the roll is rendered into a portal on the
 * body and `@media print` hides the app behind it — a print of a label is the
 * label, not the receipt screen it was launched from.
 */

import { useEffect, useMemo, useRef } from "react"
import { createPortal } from "react-dom"

import { Barcode, useStickerBarcode } from "@/components/barcode"
import { cn } from "@/lib/cn"
import { groups } from "@/lib/format"

/**
 * The label stock, in millimetres, and the only place either number is
 * written. 58 × 40 mm is the common roll for a 58 mm thermal printer; a shop
 * that buys 58 × 30 changes this line and nothing else.
 *
 * It lives in TypeScript rather than in `index.css` because `@page` cannot
 * read a custom property — the rule below is written at runtime from these
 * two numbers, so the paper size and the page box cannot drift apart.
 */
const LABEL_STOCK = { w: 58, h: 40 }

const STOCK_CSS = `
@page { size: ${LABEL_STOCK.w}mm ${LABEL_STOCK.h}mm; margin: 0 }
.label-page { width: ${LABEL_STOCK.w}mm; height: ${LABEL_STOCK.h}mm }
`

/** The sticker face, and the counting aid printed in its corner. */
export type RollLabel = {
  product_title: string
  variant_label: string
  colour: string
  size: string
  sku: string
  barcode: string
  /** How many units of this line came in — one sticker each. */
  copies: number
}

/** A shelf-edge label: the cell's code, read across a room far more often
 *  than it is scanned. */
export type RollCell = { code: string }

/** A line that claims no copies still has to be printable — somebody asked
 *  for this label, and a reprint of nothing is a jam nobody can clear. */
function copiesOf(label: RollLabel): number {
  return Number.isFinite(label.copies) && label.copies > 0 ? Math.floor(label.copies) : 1
}

/** The biggest thing on the sticker. The size, when there is one — somebody
 *  sorting a shelf reads it from half a metre and scans only when they need
 *  certainty. A variant with no size falls back to whatever names it. */
function bigWord(label: RollLabel): string {
  return label.size || label.variant_label || label.sku
}

export function LabelRoll({
  labels,
  autoPrint = false,
  onPrinted,
}: {
  labels: RollLabel[]
  /** Print once, on mount. A remount — a bumped `key` — prints again. */
  autoPrint?: boolean
  onPrinted?: () => void
}) {
  // Flattened in array order, so the pages come off the roll in the order the
  // piles sit on the table.
  const pages = useMemo(
    () =>
      labels.flatMap((label) => {
        const total = copiesOf(label)
        return Array.from({ length: total }, (_, index) => ({
          label,
          n: index + 1,
          total,
        }))
      }),
    [labels],
  )

  usePrintOnce(autoPrint && pages.length > 0, onPrinted)

  return (
    <>
      {/* The preview is the sticker at screen scale, one card per line rather
          than one per unit: twenty identical cards say nothing the "× 20"
          does not, and they push the print hint off the phone. */}
      <div className="no-print space-y-2">
        <p className="text-micro text-ink-soft">
          {groups(pages.length)} ta yorliq · {groups(labels.length)} xil ·{" "}
          {LABEL_STOCK.w} × {LABEL_STOCK.h} mm
        </p>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {labels.map((label, index) => (
            <li
              key={`${label.barcode}-${index}`}
              className="rounded-control border border-line bg-surface p-2"
            >
              <div className="truncate text-micro text-ink-faint">{label.product_title}</div>
              <div className="flex items-baseline justify-between gap-2">
                <span className="figure font-bold leading-none">{bigWord(label)}</span>
                <span className="min-w-0 truncate text-small font-medium text-ink-soft">
                  {label.colour}
                </span>
              </div>
              <Barcode value={label.barcode} />
              <div className="flex items-baseline justify-between gap-2 text-micro tabular">
                <span className="min-w-0 truncate text-ink-faint">{label.sku}</span>
                <span className="shrink-0 font-medium">{groups(copiesOf(label))} dona</span>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <Roll>
        {pages.map((page, index) => (
          <Sticker key={index} label={page.label} n={page.n} total={page.total} />
        ))}
      </Roll>
    </>
  )
}

/**
 * The shelf-edge labels. Same printer, same page, but the code is the whole
 * sticker with its barcode underneath — a person reads `B-01-02` far more
 * often than they scan it, and they read it from the aisle.
 */
export function CellRoll({
  cells,
  autoPrint = false,
  onPrinted,
}: {
  cells: RollCell[]
  autoPrint?: boolean
  onPrinted?: () => void
}) {
  usePrintOnce(autoPrint && cells.length > 0, onPrinted)

  return (
    <>
      <div className="no-print space-y-2">
        <p className="text-micro text-ink-soft">
          {groups(cells.length)} ta katak yorlig'i · {LABEL_STOCK.w} × {LABEL_STOCK.h} mm
        </p>
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {cells.map((cell) => (
            <li key={cell.code} className="rounded-control border border-line bg-surface p-2">
              <div className="text-center">
                <span className="display leading-none tabular">{cell.code}</span>
              </div>
              <Barcode value={cell.code} />
            </li>
          ))}
        </ul>
      </div>

      <Roll>
        {cells.map((cell) => (
          <CellSticker key={cell.code} code={cell.code} />
        ))}
      </Roll>
    </>
  )
}

// ------------------------------------------------------------------ the pages

/** The stack the printer sees, on the body so the app can be hidden behind
 *  it, and carrying the one rule that says how big a page is. */
function Roll({ children }: { children: React.ReactNode }) {
  return createPortal(
    <div className="label-roll print-only">
      <style>{STOCK_CSS}</style>
      {children}
    </div>,
    document.body,
  )
}

function Sticker({ label, n, total }: { label: RollLabel; n: number; total: number }) {
  const bars = useStickerBarcode(label.barcode)
  const big = bigWord(label)

  return (
    <article className="label-page">
      <div className="label-head">
        {/* Four sizes still read at 11 mm; "42-43" or a variant name does not,
            so a long word steps down rather than running off the sticker. */}
        <span className={cn("label-size", big.length > 4 && "label-size-long")}>{big}</span>
        <span className="label-colour">{label.colour}</span>
      </div>
      {bars ? <img className="label-bars" src={bars} alt={label.barcode} /> : null}
      <div className="label-foot">
        <span className="label-sku">{label.sku}</span>
        <span className="label-count">
          {n}/{total}
        </span>
      </div>
    </article>
  )
}

function CellSticker({ code }: { code: string }) {
  const bars = useStickerBarcode(code)
  return (
    <article className="label-page label-page-cell">
      <span className={cn("cell-code", code.length > 9 && "cell-code-long")}>{code}</span>
      {bars ? <img className="label-bars" src={bars} alt={code} /> : null}
    </article>
  )
}

/**
 * Print once, when the roll arrives.
 *
 * Pressing Qabul *is* the decision to print — every unit gets one — so the
 * roll does not wait to be asked a second time. The frame of delay is for the
 * barcode images: `window.print()` freezes the page as it stands, and a page
 * printed before its pictures decoded is a page of empty boxes.
 */
function usePrintOnce(wanted: boolean, onPrinted?: () => void) {
  const done = useRef(onPrinted)
  done.current = onPrinted
  const fired = useRef(false)

  useEffect(() => {
    if (!wanted || fired.current) return
    const timer = window.setTimeout(() => {
      // Claimed here rather than when the effect runs: a remount that clears
      // the timer before it fires — which is every mount under StrictMode —
      // must leave the next one free to print, or nothing ever does.
      fired.current = true
      window.print()
      done.current?.()
    }, 120)
    return () => window.clearTimeout(timer)
  }, [wanted])
}
