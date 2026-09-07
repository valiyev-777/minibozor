import * as React from "react"
import { AlertCircle, Inbox } from "lucide-react"
import { ApiError } from "@/api/client"
import { Button } from "@/components/ui/button"
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
export function Loading({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-3 px-5 py-5">
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className="block h-4 w-full max-w-sm animate-pulse rounded bg-line" />
      ))}
    </div>
  )
}

export function Failed({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line bg-danger-soft px-5 py-4">
      <p className="flex items-start gap-2 text-[14px] text-danger">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        {error instanceof ApiError ? error.message : "So'rov bajarilmadi."}
      </p>
      {onRetry ? (
        <Button size="sm" onClick={onRetry}>
          Qaytadan
        </Button>
      ) : null}
    </div>
  )
}

export function Empty({ title, hint }: { title: string; hint?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1.5 border-t border-line-soft px-5 py-12 text-center">
      <Inbox className="size-6 text-ink-faint" />
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {hint ? <p className="max-w-sm text-[13px] text-ink-soft">{hint}</p> : null}
    </div>
  )
}
