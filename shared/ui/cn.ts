import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Join classes and let the later one win.
 *
 * All three panels had their own copy of this, byte for byte. `twMerge` is
 * what makes `className` on a shared component an override rather than a
 * fight: `<Button className="h-12">` beats the variant's height instead of
 * both landing in the class list and the cascade deciding.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
