import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * The unit this application is built out of, instead of a table row.
 *
 * The backoffice has one `DataTable` and every screen contributes columns to
 * it, which is right for somebody scanning hundreds of rows. A seller has a
 * dozen offers and three batches; for that many, a row is a worse shape than
 * a card — the status has to be a colour they see rather than a word in the
 * fifth column, and the figure has to be the biggest thing in the block.
 *
 * So: no shared table here, and this is why. If a seller ever has four
 * hundred offers, that screen gets a table of its own and this stays as it is.
 */
export function Panel({
  title,
  hint,
  actions,
  children,
  className,
}: {
  title?: React.ReactNode
  hint?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={cn("rounded-2xl border border-line bg-surface", className)}
    >
      {title || actions ? (
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3">
          <div className="min-w-0">
            {title ? (
              <h2 className="text-[17px] font-semibold text-ink">{title}</h2>
            ) : null}
            {hint ? <p className="mt-0.5 text-[13px] text-ink-soft">{hint}</p> : null}
          </div>
          {actions}
        </header>
      ) : null}
      {children}
    </section>
  )
}

/** A row inside a Panel. Padding and dividers in one place. */
export function Row({
  children,
  className,
  onClick,
}: {
  children: React.ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-soft px-5 py-4",
        onClick && "cursor-pointer hover:bg-brand-soft/40",
        className,
      )}
    >
      {children}
    </div>
  )
}

/**
 * One figure, labelled, at the size somebody who opened the page for it can
 * see without reading.
 */
export function Figure({
  label,
  value,
  unit,
  hint,
  tone = "ink",
}: {
  label: string
  value: React.ReactNode
  unit?: string
  hint?: React.ReactNode
  tone?: "ink" | "good" | "danger" | "warn" | "brand"
}) {
  const colour = {
    ink: "text-ink",
    good: "text-good",
    danger: "text-danger",
    warn: "text-warn",
    brand: "text-brand",
  }[tone]
  return (
    <div>
      <p className="text-[13px] text-ink-soft">{label}</p>
      <p className={cn("figure mt-0.5", colour)}>
        {value}
        {unit ? (
          <span className="ml-1 text-[14px] font-normal text-ink-soft">{unit}</span>
        ) : null}
      </p>
      {hint ? <p className="mt-0.5 text-[13px] text-ink-faint">{hint}</p> : null}
    </div>
  )
}

/** Loading, failed and empty, said the same way on every screen. */
/* Loading, nothing and broken come from the one design system now — the same
 * three the back office and the courier's app draw, so a failed request looks
 * the same whichever panel somebody is in. `Empty` gained an `action` slot
 * there, which is what stops an empty screen being a dead end.
 *
 * Re-exported rather than swept, because every screen in this app already
 * imports them from here. */
export { Async, Empty, Failed, Loading } from "@/ui/states"
