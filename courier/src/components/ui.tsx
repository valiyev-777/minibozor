import * as React from "react"
import clsx from "clsx"

/**
 * The five primitives the whole app is built from.
 *
 * Copied in spirit from the seller cabinet's components and then allowed to
 * diverge, which is the same decision that file records: sharing them would
 * need a workspace and a version to keep two applications in step, and these
 * two are not going to agree for long. A cabinet's button is 40px and sits in
 * a toolbar. This one is 64px because it is pressed outdoors with a glove on,
 * and there is no small variant to reach for by mistake.
 */

type ButtonTone = "brand" | "good" | "bad" | "ghost"

const TONES: Record<ButtonTone, string> = {
  brand: "bg-brand text-brand-ink border-brand",
  good: "bg-good text-good-ink border-good",
  bad: "bg-bad text-bad-ink border-bad",
  ghost: "bg-transparent text-ink border-line",
}

export function Button({
  tone = "brand",
  busy = false,
  className,
  children,
  disabled,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: ButtonTone; busy?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      className={clsx(
        "flex h-16 w-full items-center justify-center gap-3 rounded-[var(--radius-work)]",
        "border-2 text-xl font-bold",
        "active:scale-[0.99] disabled:opacity-45",
        TONES[tone],
        className,
      )}
    >
      {busy ? <Spinner /> : children}
    </button>
  )
}

/** A link that has to look and feel exactly like a button — the call action. */
export function ButtonLink({
  tone = "brand",
  className,
  children,
  ...rest
}: React.AnchorHTMLAttributes<HTMLAnchorElement> & { tone?: ButtonTone }) {
  return (
    <a
      {...rest}
      className={clsx(
        "flex h-16 w-full items-center justify-center gap-3 rounded-[var(--radius-work)]",
        "border-2 text-xl font-bold",
        TONES[tone],
        className,
      )}
    >
      {children}
    </a>
  )
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="size-6 animate-spin rounded-full border-[3px] border-current border-t-transparent"
    />
  )
}

/** A bordered block. Fills wash out in daylight; a 2px edge does not. */
export function Panel({
  className,
  tone,
  children,
}: {
  className?: string
  tone?: "plain" | "cash" | "pending" | "good" | "bad"
  children: React.ReactNode
}) {
  return (
    <div
      className={clsx(
        "rounded-[var(--radius-work)] border-2 p-4",
        tone === "cash" && "border-line bg-cash-fill",
        tone === "pending" && "border-pending bg-pending-fill",
        tone === "good" && "border-good bg-good-fill",
        tone === "bad" && "border-bad bg-bad-fill",
        (!tone || tone === "plain") && "border-line",
        className,
      )}
    >
      {children}
    </div>
  )
}

/** A one-word state, in the colour that word means. */
export function Pill({
  children,
  tone = "plain",
  className,
}: {
  children: React.ReactNode
  tone?: "plain" | "good" | "bad" | "pending" | "brand"
  className?: string
}) {
  return (
    <span
      className={clsx(
        "inline-block rounded-lg px-2.5 py-1 text-sm font-semibold whitespace-nowrap",
        tone === "good" && "bg-good text-good-ink",
        tone === "bad" && "bg-bad text-bad-ink",
        tone === "pending" && "bg-pending text-page",
        tone === "brand" && "bg-brand text-brand-ink",
        tone === "plain" && "bg-panel text-muted",
        className,
      )}
    >
      {children}
    </span>
  )
}

/**
 * A text field sized for one gloved finger.
 *
 * There are four of these in the whole application — a phone number, a code, a
 * recipient's name and a reason — and that is the budget. Typing on a doorstep
 * is the slowest thing a courier can be asked to do, so anything that can be a
 * tap is a tap.
 */
export function Field({
  label,
  hint,
  error,
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string
  hint?: string
  error?: string | null
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-base font-semibold text-muted">{label}</span>
      <input
        {...rest}
        className={clsx(
          "h-16 w-full rounded-[var(--radius-work)] border-2 bg-transparent px-4 text-2xl",
          "outline-none focus:border-brand",
          error ? "border-bad" : "border-line",
          className,
        )}
      />
      {error ? (
        <span className="mt-1.5 block text-base font-semibold text-bad">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-base text-muted">{hint}</span>
      ) : null}
    </label>
  )
}

/** A label above a value — most of the detail screen is this shape. */
export function Labelled({
  label,
  children,
  className,
}: {
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <div className="text-base text-muted">{label}</div>
      <div className="text-xl font-semibold">{children}</div>
    </div>
  )
}

/** Nothing here, said in a way that does not look like a failure. */
export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="px-1 py-10 text-center text-lg text-muted">{children}</p>
}
