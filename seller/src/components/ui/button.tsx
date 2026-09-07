import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Bigger than the backoffice's, on purpose.
 *
 * That one is a tool: 28px tall, sized for somebody clicking a hundred times
 * an hour. This is a product a seller opens twice a week, sometimes on a
 * phone, so the default is a comfortable target rather than the smallest one
 * that works.
 */
const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium " +
    "transition-colors outline-none focus-visible:ring-2 focus-visible:ring-brand/40 " +
    "disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-brand/90",
        outline: "border border-line bg-surface text-ink hover:bg-line-soft",
        ghost: "text-ink-soft hover:bg-line-soft hover:text-ink",
        danger: "bg-danger text-white hover:bg-danger/90",
        quiet: "border border-line bg-surface text-danger hover:bg-danger-soft",
      },
      size: {
        sm: "h-8 px-3 text-[14px]",
        md: "h-10 px-4 text-[15px]",
        lg: "h-12 px-5 text-[16px]",
        icon: "size-10",
      },
    },
    defaultVariants: { variant: "outline", size: "md" },
  },
)

export type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof button> & { asChild?: boolean }

export function Button({ className, variant, size, asChild, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button"
  return <Component className={cn(button({ variant, size }), className)} {...props} />
}
