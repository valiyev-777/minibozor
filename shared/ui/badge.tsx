import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "./cn"

/**
 * A state, as a colour that means one thing.
 *
 * Three tones and no more, matching the three meanings in the palette: it
 * happened, it did not, it has not yet. `neutral` is for a state that carries
 * no verdict — archived, withdrawn — and `brand` for one that is merely
 * notable. A fourth colour would be a decision nobody could defend at a
 * glance, which is the only speed a badge is read at.
 */
const badge = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 font-medium " +
    "text-[length:var(--text-micro)] [&_svg]:size-3 [&_svg]:shrink-0",
  {
    variants: {
      tone: {
        neutral: "bg-line-soft text-ink-soft",
        brand: "bg-brand-soft text-brand-deep",
        good: "bg-good-soft text-good",
        warn: "bg-warn-soft text-warn-ink",
        danger: "bg-danger-soft text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
)

export type BadgeProps = {
  className?: string
  children?: React.ReactNode
} & VariantProps<typeof badge>

export function Badge({ className, tone, children }: BadgeProps) {
  return <span className={cn(badge({ tone }), className)}>{children}</span>
}
