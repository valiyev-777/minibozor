import * as React from "react"
import { cn } from "@/ui/cn"

/**
 * The box a screen's content sits in, and the row inside it.
 *
 * Not a `Card`: every screen here is a list of rows in a bordered box, and
 * naming it after the shape rather than after a metaphor is what stopped the
 * three panels each inventing their own. `Panel` draws the border and the
 * heading; `Row` is one line of the list, and it is a `<div>` rather than a
 * `<tr>` because these lists are read on a phone as often as at a desk and a
 * table cannot wrap.
 */

export function Panel({
  title,
  action,
  children,
  className,
}: {
  title?: React.ReactNode
  /** The one thing to do on this screen, beside the heading. */
  action?: React.ReactNode
  children?: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-[var(--radius-panel)] border border-line bg-surface",
        className,
      )}
    >
      {title || action ? (
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
          {title ? (
            <h2 className="text-[length:var(--text-body)] font-semibold text-ink">
              {title}
            </h2>
          ) : (
            <span />
          )}
          {action}
        </header>
      ) : null}
      {children}
    </section>
  )
}

export function Row({
  children,
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-soft px-5",
        "py-[calc(var(--cell-y)*2)]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

/**
 * A figure with the word for it under it.
 *
 * The word goes *under* the number on purpose: these are read by scanning the
 * numbers first — "what am I owed" is answered by the digits, and the label
 * only settles which digits they were.
 */
export function Figure({
  label,
  value,
  tone,
}: {
  label: string
  value: React.ReactNode
  tone?: "good" | "danger" | "brand"
}) {
  return (
    <div className="space-y-0.5">
      <p
        className={cn(
          "figure",
          tone === "good" && "text-good",
          tone === "danger" && "text-danger",
          tone === "brand" && "text-brand-deep",
        )}
      >
        {value}
      </p>
      <p className="text-[length:var(--text-small)] text-ink-soft">{label}</p>
    </div>
  )
}

/** A label above a value, for a detail list rather than a headline. */
export function Detail({
  label,
  children,
  className,
}: {
  label: string
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("space-y-0.5", className)}>
      <p className="text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint">
        {label}
      </p>
      <p className="text-[length:var(--text-body)] text-ink">{children ?? "—"}</p>
    </div>
  )
}
