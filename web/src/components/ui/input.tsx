/**
 * The field, filled rather than outlined.
 *
 * That is the house style and it is not only a look: a back-office form is
 * eight fields in two columns, and eight outlined boxes on a white card is a
 * grid of empty rectangles where the labels are the quietest thing on the
 * screen. A filled field reads as *a place to put something* at a glance and
 * leaves the card's own border as the only line in the region.
 *
 * The border is transparent rather than absent, so focus and error can bring
 * one in without the control changing size and shifting the row.
 */

import * as React from "react"

import { cn } from "@/lib/cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-control w-full min-w-0 rounded-control border border-transparent bg-line-soft px-3 text-small text-ink",
        "outline-none transition-[background-color,border-color,box-shadow]",
        "placeholder:text-ink-faint",
        "focus-visible:border-brand focus-visible:bg-surface focus-visible:ring-2 focus-visible:ring-brand/25",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "file:mr-3 file:border-0 file:bg-transparent file:text-small file:font-medium file:text-ink",
        // Numbers typed into a warehouse form are compared down a column as
        // often as they are read on their own line.
        "[&[type=number]]:tabular-nums",
        "aria-invalid:border-danger aria-invalid:bg-danger-soft aria-invalid:ring-danger/20",
        className,
      )}
      {...props}
    />
  )
}

export { Input }
