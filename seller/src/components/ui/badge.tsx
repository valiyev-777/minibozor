import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badge = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[13px] font-medium",
  {
    variants: {
      tone: {
        neutral: "bg-line-soft text-ink-soft",
        brand: "bg-brand-soft text-brand-ink",
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
