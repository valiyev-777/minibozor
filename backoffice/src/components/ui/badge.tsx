import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badge = cva(
  "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold " +
    "uppercase tracking-wide whitespace-nowrap",
  {
    variants: {
      tone: {
        neutral: "bg-line-soft text-ink-soft",
        accent: "bg-accent-soft text-accent",
        good: "bg-good-soft text-good",
        warn: "bg-warn-soft text-warn",
        danger: "bg-danger-soft text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
)

export type BadgeProps = { className?: string; children?: React.ReactNode } &
  VariantProps<typeof badge>

export function Badge({ className, tone, children }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)}>{children}</span>
}
