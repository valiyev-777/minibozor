import * as React from "react"
import { Badge } from "@/ui/badge"
import { Button as Base } from "@/ui/button"
import { cn } from "@/ui/cn"
import { FieldError, Hint, Label } from "@/ui/field"
import { Empty as SharedEmpty } from "@/ui/states"

/**
 * The courier's primitives, on the shared design system.
 *
 * This file used to hold its own button, its own pill and its own field, and
 * its comment defended that: "copied in spirit from the seller cabinet's
 * components and then allowed to diverge… sharing them would need a workspace
 * and a version to keep two applications in step". That was rejected, and it
 * was wrong twice over — the sharing needed neither (it needed a symlink), and
 * the divergence was not a design decision but the residue of two sessions.
 *
 * **What was genuinely right about it is kept, as system variants:**
 *
 * - Every action is 64px and full width. That is `size="lg" block` reading
 *   `--control-lg`, which `.density-comfortable` sets to 4rem on `<html>`.
 *   The same `size="lg"` is 44px in the back office. One component, one
 *   definition of what a primary button looks like, three heights.
 * - Near-black on near-white, colour only where it carries a decision. That is
 *   the shared palette; the tokens were renamed onto it (`bad`→`danger`,
 *   `pending`→`warn`, `muted`→`ink-soft`, `page`→`canvas`, `panel`→`surface`).
 * - The lifted dark palette for the evening half of a round: `.allow-dark`.
 * - No accidental text selection under a thumb: `.no-select`.
 *
 * What is gone is the accidental part: a `tone` prop that meant `variant`
 * everywhere else, a focus style that lived only on `:active` so a keyboard
 * showed nothing, and a field whose error was its own markup.
 */

/** The tones this app's screens ask for, mapped onto the shared variants. */
type Tone = "brand" | "good" | "bad" | "pending" | "cash" | "ghost" | "plain"

const VARIANT: Record<Tone, "primary" | "good" | "danger" | "outline"> = {
  brand: "primary",
  good: "good",
  bad: "danger",
  // Amber is a state, not an action. "Not sent yet" is drawn outlined rather
  // than filled, because a filled amber button beside a filled green one reads
  // as two equal choices.
  pending: "outline",
  cash: "outline",
  ghost: "outline",
  plain: "outline",
}

export function Button({
  tone = "brand",
  busy = false,
  className,
  children,
  disabled,
  ...rest
}: React.ComponentProps<"button"> & { tone?: Tone; busy?: boolean }) {
  return (
    <Base
      {...rest}
      variant={VARIANT[tone]}
      size="lg"
      block
      disabled={disabled || busy}
      className={cn("border-2 text-xl active:scale-[0.99]", className)}
    >
      {busy ? <Spinner /> : children}
    </Base>
  )
}

/** A link that has to look and feel exactly like a button — the call action. */
export function ButtonLink({
  tone = "brand",
  className,
  children,
  ...rest
}: React.ComponentProps<"a"> & { tone?: Tone }) {
  return (
    <Base
      asChild
      variant={VARIANT[tone]}
      size="lg"
      block
      className={cn("border-2 text-xl active:scale-[0.99]", className)}
    >
      <a {...rest}>{children}</a>
    </Base>
  )
}

function Spinner() {
  return (
    <span
      className="size-6 animate-spin rounded-full border-[3px] border-current border-t-transparent"
      aria-label="Yuklanmoqda"
    />
  )
}

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
      className={cn(
        "rounded-[var(--radius-panel)] border-2 p-4",
        tone === "cash" && "border-line bg-warn-soft",
        tone === "pending" && "border-warn bg-warn-soft",
        tone === "good" && "border-good bg-good-soft",
        tone === "bad" && "border-danger bg-danger-soft",
        (!tone || tone === "plain") && "border-line bg-surface",
        className,
      )}
    >
      {children}
    </div>
  )
}

/**
 * A one-word state, in the colour that word means.
 *
 * The shared `Badge` with this app's filled look: outdoors, a tinted pill on a
 * white card is two greys, so a state is drawn as solid colour here. Same five
 * meanings as the other two panels — it happened, it did not, it has not yet.
 */
export function Pill({
  children,
  tone = "plain",
  className,
}: {
  children: React.ReactNode
  tone?: "plain" | "good" | "bad" | "pending" | "brand"
  className?: string
}) {
  const solid =
    tone === "good"
      ? "bg-good text-good-ink"
      : tone === "bad"
        ? "bg-danger text-danger-ink"
        : tone === "pending"
          ? "bg-warn text-warn-ink"
          : tone === "brand"
            ? "bg-brand text-brand-ink"
            : "border border-line bg-surface text-ink-soft"
  return (
    <Badge
      className={cn(
        "rounded-lg px-2.5 py-1 text-[length:var(--text-small)] font-semibold",
        solid,
        className,
      )}
    >
      {children}
    </Badge>
  )
}

/**
 * A text field sized for one gloved finger.
 *
 * There are four of these in the whole application — a phone number, a code, a
 * recipient's name and a reason — and that is the budget. Typing on a doorstep
 * is the slowest thing a courier can be asked to do, so anything that can be a
 * tap is a tap.
 *
 * Wired the way the other two panels' fields are now: the error is
 * `role="alert"` under the field it is about, with `aria-invalid` and
 * `aria-describedby` pointing at it, so a screen reader and a sighted user are
 * told the same thing in the same place.
 */
export function Field({
  label,
  hint,
  error,
  className,
  id,
  ...rest
}: React.ComponentProps<"input"> & {
  label: string
  hint?: string
  error?: string | null
}) {
  const own = React.useId()
  const fieldId = id ?? own
  const errorId = `${fieldId}-error`
  const hintId = `${fieldId}-hint`
  return (
    <div>
      <Label
        htmlFor={fieldId}
        className="mb-1.5 text-[length:var(--text-body)] font-semibold text-ink-soft"
      >
        {label}
      </Label>
      <input
        {...rest}
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : hint ? hintId : undefined}
        className={cn(
          "h-[var(--control-lg)] w-full rounded-[var(--radius-panel)] border-2",
          "bg-transparent px-4 text-2xl text-ink outline-none",
          "focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/25",
          error ? "border-danger" : "border-line",
          className,
        )}
      />
      {error ? (
        <FieldError id={errorId}>{error}</FieldError>
      ) : hint ? (
        <Hint id={hintId} className="mt-1.5">
          {hint}
        </Hint>
      ) : null}
    </div>
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
      <div className="text-[length:var(--text-body)] text-ink-soft">{label}</div>
      <div className="text-xl font-semibold">{children}</div>
    </div>
  )
}

/**
 * Nothing here, said in a way that does not look like a failure.
 *
 * The shared `Empty`, so an empty round looks the same in this app as an empty
 * batch list does in the other two — and so this one gains the slot for what to
 * do about it, which it did not have.
 */
export function Empty({
  children,
  action,
}: {
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return typeof children === "string" ? (
    <SharedEmpty title={children} action={action} className="border-t-0" />
  ) : (
    <SharedEmpty title="" hint={children} action={action} className="border-t-0" />
  )
}
