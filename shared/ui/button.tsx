import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "./cn"

/**
 * One button for all three panels.
 *
 * The three had three: the back office's was 32px with a `variant`/`size`
 * pair, the seller's 40px with the same names and different numbers, and the
 * courier's a fork with a `tone` prop, no sizes at all and a hard-coded 64px
 * height. The courier's comment defended that as the design working. It was
 * not: the reason its buttons are big is real, but "big" is a property of the
 * screen it is on, not of a different component.
 *
 * So the height comes from `--control-*`, which the density class on `<html>`
 * sets. The same `<Button size="lg">` is 44px in the back office, 48px in the
 * cabinet and 64px in the courier's app, and there is one definition of what a
 * primary button looks like.
 *
 * `focus-visible` is a ring on every variant. It was on two of the three
 * before; the courier's had `active:scale` and nothing for a keyboard.
 */
const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] " +
    "font-medium transition-colors outline-none " +
    "focus-visible:ring-2 focus-visible:ring-brand/45 focus-visible:ring-offset-1 " +
    "focus-visible:ring-offset-surface " +
    "disabled:pointer-events-none disabled:opacity-45 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-brand text-brand-ink hover:bg-brand/90",
        outline: "border border-line bg-surface text-ink hover:bg-line-soft",
        ghost: "text-ink-soft hover:bg-line-soft hover:text-ink",
        danger: "bg-danger text-danger-ink hover:bg-danger/90",
        good: "bg-good text-good-ink hover:bg-good/90",
        /** A refusal that is not the main action: outlined, in danger's ink. */
        quiet: "border border-line bg-surface text-danger hover:bg-danger-soft",
      },
      size: {
        sm: "h-[var(--control-sm)] px-2.5 text-[length:var(--text-small)] [&_svg]:size-3.5",
        md: "h-[var(--control-md)] px-3.5 text-[length:var(--text-body)] [&_svg]:size-4",
        lg: "h-[var(--control-lg)] px-5 text-[length:var(--text-body)] font-semibold [&_svg]:size-5",
        icon: "size-[var(--control-md)] [&_svg]:size-4",
      },
      /** The courier's actions fill the width; a toolbar's do not. */
      block: { true: "w-full", false: "" },
    },
    defaultVariants: { variant: "outline", size: "md", block: false },
  },
)

export type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof button> & { asChild?: boolean }

export function Button({
  className,
  variant,
  size,
  block,
  asChild,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : "button"
  return (
    <Component
      className={cn(button({ variant, size, block }), className)}
      {...props}
    />
  )
}

export { button as buttonClasses }
