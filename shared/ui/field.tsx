import * as React from "react"
import { cn } from "./cn"

/**
 * Inputs, and where an error about one goes.
 *
 * The height comes from `--control-md`, so a field lines up with the button
 * beside it in every panel without either of them knowing which panel it is.
 */
const box =
  "w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 " +
  "h-[var(--control-md)] text-[length:var(--text-body)] text-ink " +
  "placeholder:text-ink-faint outline-none " +
  "focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/25 " +
  "disabled:bg-line-soft disabled:text-ink-faint " +
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-2 " +
  "aria-[invalid=true]:ring-danger/20"

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn(
        "block text-[length:var(--text-small)] font-medium text-ink",
        className,
      )}
      {...props}
    />
  )
}

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return <input className={cn(box, className)} {...props} />
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(box, "min-h-20 resize-y py-2 h-auto", className)}
      {...props}
    />
  )
}

export function Select({ className, ...props }: React.ComponentProps<"select">) {
  return <select className={cn(box, "pr-8", className)} {...props} />
}

export function Hint({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      className={cn("text-[length:var(--text-small)] text-ink-soft", className)}
      {...props}
    />
  )
}

/**
 * The message about *this* field, under *this* field.
 *
 * Not a summary at the top of the form. A person who typed the wrong thing
 * into the fourth box has to be told at the fourth box — a banner above the
 * first one makes them read the whole form again to find out which. Rendered
 * as nothing when there is no error, so the caller does not need a
 * conditional.
 */
export function FieldError({
  children,
  id,
}: {
  children?: React.ReactNode
  id?: string
}) {
  if (!children) return null
  return (
    <p
      id={id}
      role="alert"
      className="text-[length:var(--text-small)] font-medium text-danger"
    >
      {children}
    </p>
  )
}

/**
 * A labelled field with its hint and its error, wired together.
 *
 * The wiring is the point: `htmlFor`/`id`, and `aria-describedby` pointing at
 * whichever of the two is showing, and `aria-invalid` when it is the error.
 * Doing that by hand at every call site is how half of them end up not doing
 * it.
 */
export function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string
  label: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  children: (props: {
    id: string
    "aria-invalid": boolean
    "aria-describedby": string | undefined
  }) => React.ReactNode
  className?: string
}) {
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  return (
    <div className={cn("space-y-1.5", className)}>
      <Label htmlFor={id}>{label}</Label>
      {children({
        id,
        "aria-invalid": Boolean(error),
        "aria-describedby": error ? errorId : hint ? hintId : undefined,
      })}
      {error ? (
        <FieldError id={errorId}>{error}</FieldError>
      ) : hint ? (
        <Hint id={hintId}>{hint}</Hint>
      ) : null}
    </div>
  )
}
