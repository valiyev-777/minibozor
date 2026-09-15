/**
 * The small repeated parts of the card form, in one place.
 *
 * Four of them, and each exists because the form uses it five to ten times:
 * a section heading with its asterisk, a character counter, a folded-away
 * field, and a colour swatch. Written once because a form whose eleven
 * headings are eleven hand-made `<h3>` lines is a form where the ninth one is
 * a different size and nobody notices until the owner does.
 */

import { ChevronDown, Plus } from "lucide-react"
import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"

/**
 * One numbered section of the form.
 *
 * The number is on screen, not only in the brief: the form is ten sections
 * long and "the fourth one" is how two people standing at the bench refer to
 * a part of it.
 */
export function Section({
  step,
  title,
  hint,
  required = false,
  aside,
  children,
}: {
  step: number
  title: string
  hint?: string
  required?: boolean
  aside?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="border-t border-line pt-5 first:border-t-0 first:pt-0">
      <header className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-baseline gap-2 text-small font-semibold">
          <span className="tabular text-ink-faint">{step}</span>
          <span>
            {title}
            {required ? <Required /> : null}
          </span>
        </h3>
        {aside ? <div className="flex items-center gap-2">{aside}</div> : null}
      </header>
      {hint ? <p className="mb-2 text-micro text-ink-soft">{hint}</p> : null}
      {children}
    </section>
  )
}

/** The red asterisk, and the line at the top of the form that explains it. */
export function Required() {
  return (
    <span aria-hidden className="ml-0.5 text-danger">
      *
    </span>
  )
}

/**
 * `0/90`.
 *
 * Not decoration: a name that runs past the card in the phone app is a name
 * that gets truncated in the one place it matters, so the limit is shown
 * while it is being approached rather than enforced after the fact.
 */
export function Counter({ value, max }: { value: string; max: number }) {
  const over = value.length > max
  return (
    <span
      className={cn(
        "tabular text-micro",
        over ? "text-danger" : value.length > max * 0.9 ? "text-warn" : "text-ink-faint",
      )}
    >
      {value.length}/{max}
    </span>
  )
}

/**
 * A field that is not there until somebody wants it — §5.2 ·9.
 *
 * A form that shows eleven empty textareas is a form nobody finishes. Four
 * buttons is four words, and the field a person asked for is the field they
 * are about to fill in.
 */
export function Folded({
  title,
  filled,
  children,
}: {
  title: string
  /** Already written on this card — it opens with its answer showing. */
  filled: boolean
  children: ReactNode
}) {
  const [open, setOpen] = useState(filled)

  if (!open) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="w-full justify-between"
        onClick={() => setOpen(true)}
      >
        <span className="text-ink">{title}</span>
        <span className="flex items-center gap-1 text-ink-faint">
          <Plus className="size-4" />
          Qo'shish
        </span>
      </Button>
    )
  }

  return (
    <div className="rounded-control border border-line p-3">
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="mb-2 flex w-full items-center justify-between text-left text-small font-medium"
      >
        {title}
        <ChevronDown className="size-4 rotate-180 text-ink-faint" />
      </button>
      {children}
    </div>
  )
}

/**
 * A colour, as a square.
 *
 * A palette row may carry no hex — a melange is not one colour — and painting
 * an empty string black would be a lie about the goods, so it is drawn as a
 * hatched square instead and the name beside it does the work.
 */
export function Swatch({ hex, className }: { hex?: string; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block size-4 shrink-0 rounded-full border border-line",
        !hex && "bg-line-soft",
        className,
      )}
      // The one place a raw colour is legitimate: it is the shop's data, not
      // the design system's — the whole point of the palette is that a colour
      // is a value somebody chose and stored.
      style={hex ? { backgroundColor: hex } : undefined}
    />
  )
}
