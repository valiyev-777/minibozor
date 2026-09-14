/**
 * The badge, speaking the same five meanings as `Pill` in
 * `components/page.tsx` — green happened, red did not, amber not yet, blue is
 * where the thing is now, grey is nothing in particular.
 *
 * `Pill` is what a screen reaches for. This is the shadcn-shaped one, kept in
 * step so that a component pasted in from anywhere lands in the same palette
 * instead of arriving with `bg-primary` and a radius of its own.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/cn"

const badgeVariants = cva(
  [
    "inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden",
    "rounded-full border border-transparent px-2 py-0.5",
    "text-micro font-medium whitespace-nowrap",
    "transition-colors focus-visible:ring-2 focus-visible:ring-brand/40",
    "[&>svg]:pointer-events-none [&>svg]:size-3",
  ].join(" "),
  {
    variants: {
      variant: {
        neutral: "bg-line-soft text-ink-soft",
        brand: "bg-brand-soft text-brand-deep",
        good: "bg-good-soft text-good",
        warn: "bg-warn-soft text-warn-ink",
        danger: "bg-danger-soft text-danger",
        /** Filled — for the one badge that has to be seen across a room. */
        solid: "bg-brand text-brand-ink",
        outline: "border-line text-ink-soft",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
)

function Badge({
  className,
  variant,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
