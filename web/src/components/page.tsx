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
 * `rounded-panel border border-line bg-surface shadow-panel p-3` in eleven
 * files, and a status chip with its own three colours in four of them. Not a
 * preference — the same object drawn eleven times drifts eleven ways, and the
 * app read like eleven screens rather than one.
 */

import { AlertCircle, Loader2 } from "lucide-react"

import { cn } from "@/lib/cn"

/**
 * The head of a screen, and it is a **card** rather than bare text on the
 * page.
 *
 * That is the one structural thing the house system does differently, and it
 * is worth the pixels: the title, the filters and the primary action are one
 * object with an edge round it, so the band across the top of every screen is
 * the same band and the eye stops re-finding it per page. A heading floating
 * over a grid of cards reads as a caption for the first card.
 */
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
    <header className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-panel border border-panel-edge bg-surface px-4 py-3">
      <div className="min-w-0">
        {/* Capped, unlike the figure token it borrows from. A courier's
            density triples every size on the screen, which is right for a
            pick count read in daylight and wrong for a page title — at
            40px it is the loudest thing on a screen whose job is the list
            underneath it. */}
        <h1 className="truncate text-[clamp(1.25rem,var(--text-figure),1.75rem)] font-bold leading-tight tracking-tight">
          {title}
        </h1>
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
        "overflow-hidden rounded-panel border border-panel-edge bg-surface",
        className,
      )}
    >
      {title || aside ? (
        <header className="flex min-h-12 flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-small font-semibold tracking-tight">{title}</h2>
          {aside ? <div className="flex items-center gap-2">{aside}</div> : null}
        </header>
      ) : null}
      <div className={cn(bare ? "" : "p-4")}>{children}</div>
    </section>
  )
}

/**
 * One control with a position in it, not five boxes with one of them tinted.
 *
 * Every screen that filters a list was drawing this by hand — `orders` as a
 * segmented control, `reports` as a row of outlined buttons, and the two did
 * not look like the same act. Five bordered rectangles in a row read as five
 * things to decide; a segment reads as one thing whose answer is currently
 * over there.
 *
 * A `<button>` per option rather than a `<select>`: the options are three to
 * six words and the point is that all of them are visible, which is what
 * makes it a filter somebody uses rather than a menu somebody opens.
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  tone = "neutral",
  className,
}: {
  /** `null` when the list is filtered by something else and none of these
   *  answers is the current one — a control that always shows a selection it
   *  is not responsible for is a control that lies. */
  value: T | null | undefined
  onChange: (next: T) => void
  options: Array<{ key: T; label: React.ReactNode }>
  /** What the row of options is choosing between, for a screen reader. */
  label: string
  /** The colour of the selected chip. `neutral` — a white chip on the fill —
   *  unless the answer itself is a warning ("Tugagan"), which is the one
   *  case where the filter's own state is the news. */
  tone?: Tone
  className?: string
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "inline-flex flex-wrap gap-0.5 rounded-control bg-line-soft p-1",
        className,
      )}
    >
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={option.key === value}
          onClick={() => onChange(option.key)}
          className={cn(
            "h-control-sm rounded-[calc(var(--radius-control)-2px)] px-3 text-small transition-colors",
            option.key === value
              ? tone === "neutral"
                ? "bg-surface font-medium text-ink shadow-panel"
                : cn("font-medium", TONES[tone])
              : "text-ink-soft hover:text-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
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

/** The same five meanings as a solid block, for the icon square on a `Stat`
 *  — a tint behind a coloured glyph disappears at 40px. */
const TONES_SOLID: Record<Tone, string> = {
  neutral: "bg-line-soft text-ink-soft",
  good: "bg-good text-good-ink",
  warn: "bg-warn text-white",
  danger: "bg-danger text-danger-ink",
  brand: "bg-brand text-brand-ink",
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
 * A figure, an icon square beside it, and the name of the thing underneath.
 *
 * The dashboard was a grid of these written inline, all the same weight, so
 * seven counters shouted equally and the one that needed acting on did not
 * stand out at all. Two things separate them now: the coloured square, which
 * is what the eye finds first in a row of six cards, and the figure's own
 * colour. Neither is a wash over the whole card — a card that is entirely
 * pink is harder to read, not easier.
 *
 * `icon` is optional because half the places that want a figure (a report
 * total, a count line) have no sensible glyph, and an invented one is noise.
 */
export function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
  className,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  icon?: React.ComponentType<{ className?: string }>
  tone?: Tone
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-panel border bg-surface p-4 transition-colors",
        tone === "danger" ? "border-danger/35" : "border-panel-edge",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        {Icon ? (
          <span
            className={cn(
              "grid size-10 shrink-0 place-items-center rounded-panel",
              TONES_SOLID[tone],
            )}
          >
            <Icon className="size-5" />
          </span>
        ) : null}
        <div className="min-w-0 flex-1">
          <div
            className={cn(
              "figure truncate",
              tone === "danger" && "text-danger",
              tone === "good" && "text-good",
              tone === "warn" && "text-warn-ink",
            )}
          >
            {value}
          </div>
          {hint ? (
            <div className="truncate text-micro text-ink-faint">{hint}</div>
          ) : null}
        </div>
      </div>
      <div className="truncate text-micro font-medium text-ink-soft">{label}</div>
    </div>
  )
}

export function Waiting({ what = "Yuklanmoqda" }: { what?: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 rounded-panel border border-panel-edge bg-surface p-8 text-small text-ink-soft"
    >
      <Loader2 className="size-4 animate-spin text-brand" />
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
 *
 * The shape is the house one: a tinted brand circle holding a glyph, a bold
 * line naming what is missing, and a quieter line saying where it comes
 * from. The glyph is the table's own — a list with no orders and a list with
 * no shelves are different absences, and one generic box drawn for both is
 * what makes an empty screen feel like a failure instead of a state.
 */
export function Empty({
  what,
  title,
  icon: Icon,
  children,
  bare = false,
}: {
  /** The sentence: where the things come from, or what to do now. */
  what: string
  /** The headline. Without one this is the old one-line empty. */
  title?: string
  icon?: React.ComponentType<{ className?: string }>
  children?: React.ReactNode
  /** Already inside a card — draw no edge of my own. */
  bare?: boolean
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center justify-center px-4 text-center",
        title || Icon ? "py-16" : "py-10",
        bare ? "" : "rounded-panel border border-panel-edge bg-surface",
      )}
    >
      {Icon ? (
        <span className="mb-4 grid size-22 shrink-0 place-items-center rounded-full bg-brand/10">
          <Icon className="size-8 text-brand" />
        </span>
      ) : null}
      {title ? <p className="mb-0.5 font-semibold">{title}</p> : null}
      <p className="max-w-md text-small text-ink-soft">{what}</p>
      {children ? (
        <div className="mt-4 flex justify-center gap-2">{children}</div>
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
      className="flex items-start gap-2 rounded-control border border-danger/25 bg-danger-soft p-3 text-small text-danger"
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
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
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
