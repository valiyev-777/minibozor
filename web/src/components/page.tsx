/**
 * The furniture every screen shares: a heading, a waiting state, an empty
 * state, and the one sentence to show when the API refuses.
 *
 * Written once because these are the three states every screen has and the
 * places they get invented separately are the places they get forgotten — a
 * list that renders nothing while loading is indistinguishable from a list
 * with nothing in it, and somebody makes a decision on that.
 */

import { AlertCircle, Loader2 } from "lucide-react"

import { cn } from "@/lib/cn"

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children?: React.ReactNode
}) {
  return (
    <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="text-small text-ink-soft">{subtitle}</p> : null}
      </div>
      {children ? <div className="flex items-center gap-2">{children}</div> : null}
    </header>
  )
}

export function Waiting({ what = "Yuklanmoqda" }: { what?: string }) {
  return (
    <div className="flex items-center gap-2 p-8 text-small text-ink-soft">
      <Loader2 className="size-4 animate-spin" />
      {what}…
    </div>
  )
}

export function Empty({ what }: { what: string }) {
  return (
    <div className="rounded-panel border border-dashed bg-surface p-8 text-center text-small text-ink-soft">
      {what}
    </div>
  )
}

export function Problem({ error }: { error: unknown }) {
  if (!error) return null
  const text =
    error instanceof Error ? error.message : "Nimadir noto'g'ri ketdi."
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-control bg-danger-soft p-3 text-small text-danger"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      <span>{text}</span>
    </div>
  )
}

/**
 * A fill bar. Never colour alone — the figure is beside it and the width is
 * the same information a third time, because a warehouse is read in a hurry
 * and by people who do not all see colour the same way.
 */
export function Fill({ percent }: { percent: number }) {
  const level = percent >= 90 ? "full" : percent >= 60 ? "busy" : "roomy"
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-line-soft">
      <div
        className={cn(
          "h-full rounded-full transition-[width]",
          level === "full" && "bg-danger",
          level === "busy" && "bg-warn",
          level === "roomy" && "bg-good",
        )}
        style={{ width: `${Math.min(100, Math.max(percent, percent > 0 ? 6 : 0))}%` }}
      />
    </div>
  )
}
