/* Re-exported from the one design system in ../../ui (a symlink to
 * ../../../shared/ui), shared with the other two panels.
 *
 * This file used to hold a button of its own — 32px, its own focus ring, its
 * own five variants — while the seller's cabinet held a 40px one with the same
 * variant names and different numbers, and the courier's app a fork with a
 * `tone` prop and no sizes at all. There is one now, and its height is a
 * density token, so `size="lg"` is 44px here and 64px in the courier's app
 * without either of them being a different component.
 *
 * Kept as a file rather than rewriting eighty import statements: the path
 * `@/components/ui/button` is not wrong, and a re-export is a smaller change
 * than a sweep.
 */
export { Button, buttonClasses, type ButtonProps } from "@/ui/button"
