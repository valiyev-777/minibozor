/**
 * The button, speaking this project's design system.
 *
 * It arrived as shadcn's own — `h-9`, `text-sm`, `rounded-md` — which are
 * Tailwind's numbers and not ours. So the height did not follow the density
 * class, the radius did not match a panel's, and the type was a size the
 * theme does not have. Every screen then wrote `className="h-control …"` over
 * the top of it, one screen at a time, and no two buttons in the app were the
 * same object: some 36px, some 40, some full width because the class went on
 * whatever was nearest.
 *
 * Now the size *is* a token. `sm`/`md`/`lg` are `--control-sm/md/lg`, which
 * means one button component is a desk button in the office and a glove-sized
 * one in the warehouse without a single caller asking for it.
 *
 * **Four variants, and they mean different things.** `primary` is the one act
 * this screen exists for — one per screen, and it is the only filled one.
 * `secondary` is everything else that is a real action. `ghost` is for what
 * sits inside a row and must not compete with it. `danger` is for the act
 * somebody has to mean. A screen with three filled buttons has told the
 * reader nothing about which to press.
 */

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/cn"

const buttonVariants = cva(
  [
    "inline-flex shrink-0 select-none items-center justify-center gap-2 rounded-control",
    "font-medium whitespace-nowrap",
    // Colour and shadow move; nothing here changes size on hover, because a
    // button that grows under the cursor moves the row it is in.
    "transition-[background-color,border-color,box-shadow,color] duration-150",
    "outline-none focus-visible:ring-2 focus-visible:ring-brand/45 focus-visible:ring-offset-1 focus-visible:ring-offset-surface",
    "disabled:pointer-events-none disabled:opacity-45",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        primary:
          "bg-brand text-brand-ink shadow-panel hover:bg-brand-deep active:bg-brand-deep",
        secondary:
          "border border-line bg-surface text-ink shadow-panel hover:border-line hover:bg-line-soft active:bg-line-soft",
        ghost: "text-ink-soft hover:bg-line-soft hover:text-ink active:bg-line-soft",
        danger:
          "bg-danger text-danger-ink shadow-panel hover:brightness-95 active:brightness-90",
        link: "text-brand-deep underline-offset-4 hover:underline",
      },
      size: {
        // Padding is in ems of the button's own type so a warehouse button
        // gets wider as it gets taller, rather than becoming a tall pill with
        // a word rattling around in it.
        sm: "h-control-sm px-2.5 text-micro [&_svg]:size-3.5",
        md: "h-control px-3.5 text-small [&_svg]:size-4",
        lg: "h-control-lg px-5 text-body [&_svg]:size-5",
        icon: "size-control [&_svg]:size-4",
        "icon-sm": "size-control-sm [&_svg]:size-3.5",
        "icon-lg": "size-control-lg [&_svg]:size-5",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button"
  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Button, buttonVariants }
