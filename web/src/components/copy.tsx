/**
 * Copy a code without selecting it by hand.
 *
 * Half the identifiers in this app exist to be typed into something else: a
 * barcode read to somebody on the telephone, an order code pasted into a
 * message, a customer's number dialled. Selecting `MB-000007-QORA-48` inside a
 * table row with a mouse is three attempts and usually catches the row's other
 * column too.
 *
 * The tick is the whole feedback. A toast for a copied code would be a toast
 * fired by a hover-sized gesture, several times a minute.
 */

import { Check, Copy as CopyGlyph } from "lucide-react"
import { useEffect, useState } from "react"

import { cn } from "@/lib/cn"

export function Copy({
  text,
  label,
  className,
}: {
  text: string
  /** What to announce to a screen reader. Defaults to the text itself. */
  label?: string
  className?: string
}) {
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!done) return
    const timer = window.setTimeout(() => setDone(false), 1600)
    return () => window.clearTimeout(timer)
  }, [done])

  if (!text) return null

  return (
    <button
      type="button"
      aria-label={`${label ?? text} — nusxa olish`}
      title="Nusxa olish"
      onClick={(event) => {
        // The row underneath is usually a link to somewhere else.
        event.stopPropagation()
        void navigator.clipboard?.writeText(text).then(
          () => setDone(true),
          () => setDone(false),
        )
      }}
      className={cn(
        "inline-grid size-5 shrink-0 place-items-center rounded-control text-ink-faint transition-colors",
        "hover:bg-line-soft hover:text-ink",
        done && "text-good",
        className,
      )}
    >
      {done ? <Check className="size-3.5" /> : <CopyGlyph className="size-3.5" />}
    </button>
  )
}

/** A code with its copy button — the pairing every table row wants. */
export function Code({ children, className }: { children: string; className?: string }) {
  return (
    <span className={cn("group/code inline-flex items-center gap-1 whitespace-nowrap", className)}>
      <span className="tabular">{children}</span>
      <Copy
        text={children}
        className="opacity-0 transition-opacity group-hover/code:opacity-100 focus-visible:opacity-100"
      />
    </span>
  )
}
