import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const button = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded font-medium " +
    "transition-colors outline-none focus-visible:ring-2 focus-visible:ring-accent/40 " +
    "disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent/90",
        outline: "border border-line bg-surface text-ink hover:bg-line-soft",
        ghost: "text-ink-soft hover:bg-line-soft hover:text-ink",
        danger: "bg-danger text-white hover:bg-danger/90",
        quiet: "border border-line bg-surface text-danger hover:bg-danger-soft",
      },
      size: {
        sm: "h-7 px-2.5 text-[12px]",
        md: "h-8 px-3 text-[13px]",
        icon: "size-7",
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
