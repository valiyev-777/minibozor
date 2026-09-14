/**
 * The table, in the house style.
 *
 * Three things make it that table rather than a generic one, and all three
 * are decisions about reading hundreds of rows at a desk:
 *
 * **The header is a filled band, not a bordered one.** `bg-line-soft` with
 * `text-micro` labels in 500 — quiet, but a different material from the body,
 * so the eye finds the top of the table without a rule doing it.
 *
 * **Rows have no bottom border.** They are striped instead. A striped table
 * *and* rules is two separators doing one job, and the result is a grid of
 * boxes in which no row is a unit. The stripe comes from `.table-striped` in
 * `index.css`, because `:nth-child` is not something a utility class can say.
 *
 * **Cells are `px-4 py-cell`.** The vertical half is a density token, so the
 * office sees more rows and the van sees bigger ones from the same markup.
 *
 * Put it in a `bare` `Panel` — the panel supplies the border and clips the
 * corners, so the table itself draws no outline of its own.
 */

import * as React from "react"

import { cn } from "@/lib/cn"

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="scroll-slim relative w-full overflow-x-auto"
    >
      <table
        data-slot="table"
        className={cn("table-striped w-full caption-bottom text-small", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("bg-line-soft [&_tr]:border-b [&_tr]:border-line", className)}
      {...props}
    />
  )
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn(className)} {...props} />
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn("border-t border-line bg-line-soft font-medium", className)}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      data-slot="table-row"
      className={cn(
        "transition-colors data-[state=selected]:bg-brand-soft",
        className,
      )}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "px-4 py-3 text-left align-middle text-micro font-medium whitespace-nowrap text-ink-soft",
        className,
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn("px-4 py-cell align-middle", className)}
      {...props}
    />
  )
}

function TableCaption({ className, ...props }: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-3 text-micro text-ink-faint", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
