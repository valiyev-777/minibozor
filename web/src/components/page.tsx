/**
 * The furniture every screen shares: a heading, a panel, a status chip, a
 * figure, and the three states every screen has — waiting, empty, refused.
 *
 * Written once because these are the places things get forgotten when they
 * are invented per screen. A list that renders nothing while loading is
 * indistinguishable from a list with nothing in it, and somebody makes a
 * decision on that.
 *
 * `Panel` and `Pill` were the pieces every page was writing out by hand:
 * `rounded-panel border border-line bg-surface shadow-panel p-3` in eleven files, and a status chip
 * with its own three colours in four of them. Not a preference — the same
 * object drawn eleven times drifts eleven ways, and the app read like eleven
 * screens rather than one.
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
    <header className="mb-(--gap-page) flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 text-small text-ink-soft">{subtitle}</p>
        ) : null}
      </div>
      {children ? (
        <div className="flex flex-wrap items-center gap-2">{children}</div>
      ) : null}
    </header>
  )
}

/**
 * A surface with a name on it.
 *
 * The title is part of the panel rather than a heading somebody remembers to
 * put above it, so every section on every screen has the same relationship
 * between its name and its contents. `aside` is the one control that belongs
 * to the section — a filter, a link, a count — and it sits on the title's
 * line, where it cannot be mistaken for part of the content.
 */
export function Panel({
  title,
  aside,
  children,
  className,
  bare = false,
}: {
  title?: string
  aside?: React.ReactNode
  children: React.ReactNode
  className?: string
  /** No padding — for a panel whose whole body is a list of rows. */
  bare?: boolean
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-panel border border-line bg-surface shadow-panel",
        className,
      )}
    >
      {title || aside ? (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
          <h2 className="text-small font-semibold tracking-tight">{title}</h2>
          {aside ? <div className="flex items-center gap-2">{aside}</div> : null}
        </header>
      ) : null}
      <div className={cn(bare ? "" : "p-3")}>{children}</div>
    </section>
  )
}

/** The tones every meaning has, everywhere: green happened, red did not,
 *  amber not yet, blue is where the thing is now. */
export type Tone = "neutral" | "good" | "warn" | "danger" | "brand"

const TONES: Record<Tone, string> = {
  neutral: "bg-line-soft text-ink-soft",
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn-ink",
  danger: "bg-danger-soft text-danger",
  brand: "bg-brand-soft text-brand-deep",
}

/** One word about the state of the row it sits in. */
export function Pill({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode
  tone?: Tone
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-micro font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/**
 * A figure with its name under it, and a hint under that.
 *
 * The dashboard was a grid of these written inline, all the same weight, so
 * seven counters shouted equally and the one that needed acting on did not
 * stand out at all. `tone` is what makes one of them urgent, and it is
 * carried by the border and the figure rather than by a wash of colour over
 * the whole card: a card that is entirely pink is harder to read, not easier.
 */
export function Stat({
  label,
  value,
  hint,
  tone = "neutral",
  className,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  tone?: Tone
  className?: string
}) {
  return (
    <div
      className={cn(
        "rounded-panel border border-line bg-surface shadow-panel p-3 shadow-panel transition-colors",
        tone === "danger" ? "border-danger/35" : "border-line",
        className,
      )}
    >
      <div className="truncate text-micro font-medium text-ink-soft">{label}</div>
      <div
        className={cn(
          "figure mt-1",
          tone === "danger" && "text-danger",
          tone === "good" && "text-good",
          tone === "warn" && "text-warn-ink",
        )}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-0.5 truncate text-micro text-ink-faint">{hint}</div>
      ) : null}
    </div>
  )
}

export function Waiting({ what = "Yuklanmoqda" }: { what?: string }) {
  return (
    <div
      role="status"
      className="flex items-center gap-2 rounded-panel border border-line bg-surface p-8 text-small text-ink-soft">
      <Loader2 className="size-4 animate-spin" />
      {what}…
    </div>
  )
}

/**
 * Nothing here — and what to do about it.
 *
 * An empty list is a dead end unless it says where the things come from. The
 * warehouse screens all have an answer to that ("qop ochilganda yoziladi"),
 * and a sentence is cheaper than somebody asking.
 */
export function Empty({
  what,
  children,
}: {
  what: string
  children?: React.ReactNode
}) {
  return (
    <div className="rounded-panel border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="text-small text-ink-soft">{what}</p>
      {children ? (
        <div className="mt-3 flex justify-center gap-2">{children}</div>
      ) : null}
    </div>
  )
}

export function Problem({ error }: { error: unknown }) {
  if (!error) return null
  const text = error instanceof Error ? error.message : "Nimadir noto'g'ri ketdi."
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-control border border-danger/25 bg-danger-soft p-3 text-small text-danger">
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
