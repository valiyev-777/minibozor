import * as React from "react"
import { AlertCircle, Inbox, RotateCw } from "lucide-react"
import { Button } from "./button"
import { cn } from "./cn"

/**
 * Loading, nothing, and broken — one of each, for all three panels.
 *
 * They had six between them and no two agreed. Some said "Yuklanmoqda…", some
 * drew a skeleton, some drew nothing at all; an empty list was a sentence in
 * one place and a blank table in another; a failed request was a red line in
 * one panel and a toast in the next.
 *
 * Two rules hold here, and they are the reason this file exists rather than
 * three sets of near-identical markup:
 *
 * **An empty state says what to do next.** "Hech narsa yo'q" is a dead end. A
 * person looking at an empty screen either has a filter on and wants it off,
 * or has nothing yet and wants the button that makes the first one — so
 * `action` is a real slot and not decoration.
 *
 * **A failure says what failed and offers the retry.** The backend answers
 * with a translated sentence; that sentence goes on the screen. There is no
 * "something went wrong" in this codebase, because on the screen where
 * somebody reads their own money a shrug is worse than silence.
 */

export function Loading({
  lines = 3,
  className,
}: {
  lines?: number
  className?: string
}) {
  return (
    <div
      className={cn("space-y-3 px-5 py-5", className)}
      role="status"
      aria-live="polite"
      aria-label="Yuklanmoqda"
    >
      {Array.from({ length: lines }, (_, i) => (
        <span
          key={i}
          className="block h-4 animate-pulse rounded bg-line"
          style={{ width: `${88 - i * 14}%`, maxWidth: "28rem" }}
        />
      ))}
    </div>
  )
}

export function Empty({
  title,
  hint,
  action,
  className,
}: {
  title: string
  hint?: React.ReactNode
  /** The thing to do about it. An empty screen without one is a dead end. */
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 border-t border-line-soft px-5 py-12 text-center",
        className,
      )}
    >
      <Inbox className="size-6 text-ink-faint" />
      <p className="text-[length:var(--text-body)] font-medium text-ink">{title}</p>
      {hint ? (
        <p className="max-w-sm text-[length:var(--text-small)] text-ink-soft">{hint}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

/** The sentence the backend gave us, or a plain one if it gave none. */
export function messageOf(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const message = String((error as { message?: unknown }).message ?? "")
    if (message.trim()) return message
  }
  return "So'rov bajarilmadi."
}

export function Failed({
  error,
  onRetry,
  className,
}: {
  error: unknown
  onRetry?: () => void
  className?: string
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 border-t border-line",
        "bg-danger-soft px-5 py-4",
        className,
      )}
    >
      <p className="flex items-start gap-2 text-[length:var(--text-small)] text-danger">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        {messageOf(error)}
      </p>
      {onRetry ? (
        <Button size="sm" onClick={onRetry}>
          <RotateCw />
          Qaytadan
        </Button>
      ) : null}
    </div>
  )
}

/**
 * The three states around one query, so a screen does not write the branch.
 *
 * `children` runs only when there is data, which is also what stops the
 * `data!` that every one of these call sites used to need.
 */
export function Async<T>({
  query,
  empty,
  lines,
  children,
}: {
  query: {
    isPending: boolean
    isError: boolean
    error: unknown
    data: T | undefined
    refetch: () => unknown
  }
  empty?: React.ReactNode
  lines?: number
  children: (data: T) => React.ReactNode
}) {
  if (query.isPending) return <Loading lines={lines} />
  if (query.isError)
    return <Failed error={query.error} onRetry={() => void query.refetch()} />
  if (query.data === undefined) return <Loading lines={lines} />
  if (empty && Array.isArray(query.data) && query.data.length === 0) return <>{empty}</>
  return <>{children(query.data)}</>
}
