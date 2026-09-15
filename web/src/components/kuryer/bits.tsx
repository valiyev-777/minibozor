/**
 * The pieces every courier screen is made of.
 *
 * This is deliberately *not* `components/page.tsx`. That file draws the back
 * office — a `PageHeader` card, a `Panel` with a hairline, a `Stat` tile, a
 * `Pill` — and every one of those is a rectangle on a grey page read at a
 * desk. The courier's screens are panes of frosted glass floating over a map,
 * held one-handed outdoors, and the shapes do not transfer: a 12px-radius
 * bordered card over a satellite photograph reads as a bug.
 *
 * So there are two vocabularies, and they are kept apart on purpose rather
 * than merged into one component with a `variant="glass"` that would drag the
 * desk's assumptions along behind it. What they *share* is the token file:
 * every colour, radius and shadow below is a `kuryer-*` token from
 * `shared/theme.css`, and there is no hex in this directory.
 *
 * The sizes are the house's: `h-control-lg` is 64px in `density-comfortable`
 * and that is what a primary action is here, because "a thumb hits it without
 * aiming while holding a parcel" is the same requirement the density exists
 * for. The design drew 58px; the token is the rule.
 */

import type { LucideIcon } from "lucide-react"

import { cn } from "@/lib/cn"

/* ------------------------------------------------------------------ surfaces */

/**
 * A scrolling courier screen: the wash, the status-strip clearance at the top
 * and the tab bar's room at the foot.
 *
 * The shell is `overflow-hidden` and every screen scrolls inside itself, so
 * this is the scroll container — not the document. `overscroll-contain` stops
 * a flick at the end of the list from rubber-banding the whole app, which on a
 * map screen looks like the map has come loose.
 *
 * `max-w-md` is what keeps a desk honest. These screens are a phone app; shown
 * at 1400px they would be a phone app with 900px of empty glass in the middle,
 * so they stay the width they were drawn at and sit in the centre.
 */
export function Page({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className="h-full overflow-y-auto overscroll-contain bg-linear-to-b from-kuryer-ground to-kuryer-ground-deep">
      <div
        className={cn(
          "mx-auto flex w-full max-w-md flex-col gap-3.5 px-4",
          "pt-[calc(1.5rem+env(safe-area-inset-top))] pb-[calc(var(--kuryer-tabs)+1rem)]",
          className,
        )}
      >
        {children}
      </div>
    </div>
  )
}

/**
 * A pane of frosted glass. The fill and the blur come as one class — see
 * `.kuryer-glass` in the theme for why they must not be separated.
 */
export function Glass({
  className,
  strong = false,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & {
  /** For a pane that scrolling content passes **under** — see
   *  `--color-kuryer-glass-strong`. A running total at 78% has a list's
   *  headlines reading straight through it. */
  strong?: boolean
}) {
  return (
    <div
      {...rest}
      className={cn(
        strong ? "kuryer-glass-strong" : "kuryer-glass",
        "rounded-glass p-4 shadow-kuryer-glass",
        className,
      )}
    >
      {children}
    </div>
  )
}

/**
 * The opaque tile. The design's second surface: a plain white card on the
 * wash, with no blur, for the blocks that are not floating over anything.
 */
export function Tile({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cn(
        "rounded-tile bg-kuryer-card p-4 shadow-kuryer-card",
        className,
      )}
    >
      {children}
    </div>
  )
}

/* ------------------------------------------------------------------- actions */

/** What a button means, which is the whole colour code: blue acts, green is
 *  done, amber is cash, red stops, and `quiet` competes with none of them. */
export type Act = "act" | "done" | "cash" | "halt" | "quiet"

const SLAB: Record<Act, string> = {
  act: "bg-kuryer-act text-kuryer-act-ink shadow-kuryer-act",
  done: "bg-kuryer-done text-kuryer-done-ink shadow-kuryer-done",
  cash: "bg-kuryer-cash text-kuryer-cash-ink",
  halt: "border border-kuryer-halt-edge bg-kuryer-halt-soft text-kuryer-halt-ink",
  quiet: "bg-kuryer-quiet text-kuryer-ink",
}

/**
 * The full-width action at the foot of a screen.
 *
 * One `act`-coloured slab per screen and no more — the same rule the office's
 * `primary` button follows, for the same reason: two filled blue buttons on
 * one screen means neither of them is *the* thing to do.
 *
 * Disabled is a real state here rather than 50% opacity, because half-opacity
 * blue on a bright phone screen outdoors still reads as a button.
 */
export function Slab({
  tone = "act",
  className,
  disabled,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Act }) {
  return (
    <button
      {...rest}
      disabled={disabled}
      className={cn(
        "flex h-control-lg w-full items-center justify-center gap-2 rounded-slab px-4 text-body font-semibold transition-colors",
        disabled
          ? "bg-kuryer-quiet text-kuryer-ink-faint shadow-none"
          : SLAB[tone],
        className,
      )}
    >
      {children}
    </button>
  )
}

/** A round glass button floating over the map — back, recentre, call. 44px is
 *  the smallest target Apple will stand behind and the only place on these
 *  screens that goes below `h-control-sm`, because it floats over content
 *  rather than sitting in a row of its own. */
export function GlassButton({
  icon: Icon,
  label,
  className,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: LucideIcon
  label: string
}) {
  return (
    <button
      {...rest}
      aria-label={label}
      title={label}
      className={cn(
        "kuryer-glass grid size-11 shrink-0 place-items-center rounded-full text-kuryer-act shadow-kuryer-float",
        className,
      )}
    >
      <Icon className="size-5" />
    </button>
  )
}

/* --------------------------------------------------------------------- words */

/** The small tracked label over a figure. The house `.caption` with the
 *  courier's weight and colour — the design sets these at 700 because they sit
 *  on glass and a 500 at 14px disappears into it outdoors. */
export function Cap({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <p className={cn("caption font-bold text-kuryer-ink-soft", className)}>
      {children}
    </p>
  )
}

/** The screen's own name, and the line above and below it. */
export function Title({
  over,
  children,
  lede,
}: {
  over?: React.ReactNode
  children: React.ReactNode
  lede?: React.ReactNode
}) {
  return (
    <header>
      {over ? (
        <p className="text-small font-semibold text-kuryer-ink-soft">{over}</p>
      ) : null}
      <h1 className="mt-0.5 text-kuryer-title font-bold tracking-tight text-kuryer-ink [overflow-wrap:anywhere]">
        {children}
      </h1>
      {lede ? (
        <p className="mt-1.5 text-small text-kuryer-ink-soft">{lede}</p>
      ) : null}
    </header>
  )
}

/**
 * The one sum a screen exists to show, with its unit beside it.
 *
 * `.display` and `[overflow-wrap:anywhere]` together: a seven-figure sum cut
 * to `612 00…` is not a tidier number, it is a wrong one — the house rule
 * from the `Stat` tile, and it matters more here because the number is the
 * screen.
 */
export function Sum({
  value,
  unit = "so'm",
  tone = "ink",
}: {
  value: string
  unit?: string
  tone?: "ink" | "cash" | "done"
}) {
  return (
    <p className="flex flex-wrap items-baseline gap-2">
      <span
        className={cn(
          "display [overflow-wrap:anywhere]",
          tone === "cash"
            ? "text-kuryer-cash-ink"
            : tone === "done"
              ? "text-kuryer-done-deep"
              : "text-kuryer-ink",
        )}
      >
        {value}
      </span>
      {unit ? (
        <span className="text-body font-semibold text-kuryer-ink-soft">{unit}</span>
      ) : null}
    </p>
  )
}

/* --------------------------------------------------------------------- chips */

const CHIP: Record<Act, string> = {
  act: "bg-kuryer-act-soft text-kuryer-act-deep",
  done: "bg-kuryer-done-soft text-kuryer-done-deep",
  cash: "bg-kuryer-cash-soft text-kuryer-cash-ink",
  halt: "bg-kuryer-halt-soft text-kuryer-halt-ink",
  quiet: "bg-kuryer-quiet text-kuryer-ink-soft",
}

/** One word about the row it sits in. */
export function Chip({
  tone = "quiet",
  className,
  children,
}: {
  tone?: Act
  className?: string
  children: React.ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-nub px-2.5 py-1 text-micro font-semibold",
        CHIP[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/* ------------------------------------------------------------------- notices */

/**
 * A sentence the courier has to read: what the app could not do, and what is
 * still possible without it. Never a spinner and never silence — a screen that
 * has quietly given up is the reason a round stops.
 */
export function Notice({
  tone = "cash",
  title,
  children,
}: {
  tone?: Act
  title: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div
      className={cn(
        "rounded-tile border px-4 py-3",
        tone === "act"
          ? "border-kuryer-act-edge bg-kuryer-act-soft"
          : tone === "done"
            ? "border-kuryer-done-edge bg-kuryer-done-soft"
            : tone === "halt"
              ? "border-kuryer-halt-edge bg-kuryer-halt-soft"
              : "border-kuryer-cash-edge bg-kuryer-cash-soft",
      )}
    >
      <p
        className={cn(
          "text-small font-semibold",
          tone === "act"
            ? "text-kuryer-act-deep"
            : tone === "done"
              ? "text-kuryer-done-deep"
              : tone === "halt"
                ? "text-kuryer-halt-ink"
                : "text-kuryer-cash-ink",
        )}
      >
        {title}
      </p>
      {children ? (
        <p className="mt-1 text-micro text-kuryer-ink-soft">{children}</p>
      ) : null}
    </div>
  )
}

/** The refusal the server sent, in its own words — `api()` already hands back
 *  a translated sentence, so it is printed rather than replaced. */
export function Refusal({ error }: { error: unknown }) {
  if (!error) return null
  const said = error instanceof Error ? error.message : String(error)
  return (
    <div
      role="alert"
      className="rounded-tile border border-kuryer-halt-edge bg-kuryer-halt-soft px-4 py-3 text-small font-medium text-kuryer-halt-ink"
    >
      {said}
    </div>
  )
}

/** Nothing here, and why that is fine. */
export function Nothing({
  icon: Icon,
  title,
  what,
}: {
  icon: LucideIcon
  title: string
  what?: string
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-tile bg-kuryer-quiet px-6 py-10 text-center">
      <Icon className="size-8 text-kuryer-ink-faint" />
      <p className="text-body font-semibold text-kuryer-ink">{title}</p>
      {what ? <p className="text-small text-kuryer-ink-soft">{what}</p> : null}
    </div>
  )
}

/** The bar that says the app is still reading. */
export function Loading({ what = "Yuklanmoqda" }: { what?: string }) {
  return (
    <p className="py-6 text-center text-small text-kuryer-ink-faint">{what}…</p>
  )
}
