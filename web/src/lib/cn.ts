/**
 * Class names, merged — and taught this project's own type scale.
 *
 * ------------------------------------------------------------------- why
 *
 * `twMerge` exists to let a component's own classes be overridden by a
 * caller's: the last `px-*` wins, the last `bg-*` wins. It does that by
 * knowing which Tailwind group every class belongs to.
 *
 * It does not know ours. This project's sizes are `text-body`, `text-small`
 * and `text-micro` — names, not Tailwind's `text-sm`/`text-base` — and
 * `twMerge` reads anything shaped `text-<word>` as a **colour**. So in
 *
 *     cn("text-small", isActive ? "text-white" : "text-ink-soft")
 *
 * it saw two colours, kept the last, and **deleted the size**. The element
 * then fell back to whatever it inherited — 15px from the body — and the
 * whole rail was a size and a half too big beside the same rail in the
 * design it was ported from. The bug is invisible in the source: every file
 * says `text-small` and means it.
 *
 * Naming the scale here fixes it once, for every `cn()` in the app. The
 * figure classes are listed too: `.figure` and `.display` set a font size,
 * and a component that sets a colour beside one was silently unsizing it.
 */

import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

const merge = extendTailwindMerge({
  extend: {
    classGroups: {
      // The size scale from `shared/theme.css`, declared as font sizes so a
      // colour written beside one stops eating it.
      "font-size": ["text-body", "text-small", "text-micro", "figure", "display"],
    },
  },
})

export function cn(...inputs: ClassValue[]) {
  return merge(clsx(inputs))
}
