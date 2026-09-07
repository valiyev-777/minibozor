import { cn } from "@/lib/utils"

/**
 * A strip of sections inside one screen.
 *
 * The showcase is banners, rails and promo codes; the catalogue is products,
 * categories and brands. Each of those is one job done in one place, and
 * giving every part its own sidebar row would turn a menu of nine rows into a
 * menu of fifteen — the sidebar is how somebody finds the *area* they work in,
 * not every table in it.
 *
 * No routing. Which tab is open is a detail of the screen, not a place you
 * link somebody to, and putting it in the URL would mean a route per table
 * after all.
 */
export function Tabs<T extends string>({
  value,
  onChange,
  items,
  className,
}: {
  value: T
  onChange: (value: T) => void
  items: { value: T; label: string; count?: number }[]
  className?: string
}) {
  return (
    <div
      role="tablist"
      className={cn("flex items-center gap-0.5 rounded border border-line bg-surface p-0.5", className)}
    >
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-[13px] transition-colors",
              active
                ? "bg-accent-soft font-medium text-accent"
                : "text-ink-soft hover:bg-line-soft hover:text-ink",
            )}
          >
            {item.label}
            {item.count === undefined ? null : (
              <span
                className={cn(
                  "tabular rounded px-1 text-[11px] font-semibold",
                  active ? "bg-accent/12 text-accent" : "bg-line-soft text-ink-faint",
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
