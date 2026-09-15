/**
 * "Is this a phone?" — asked once, in one place.
 *
 * The rail appears at Tailwind's `md` (48rem) and everything else about the
 * phone treatment has to happen at exactly that pixel: the bottom bar appears,
 * the rail disappears, and the density steps up. Three of those are CSS and
 * one of them is a class name React has to choose, so the breakpoint is
 * written here as a media query string and the `md:` variants elsewhere are
 * its other half. A window dragged across 768px flips all four together or it
 * ends up with two navigations, or none.
 */

import { useEffect, useState } from "react"

/** The same 48rem `md:` is. */
export const PHONE = "(width < 48rem)"

export function useIsPhone(): boolean {
  const [phone, setPhone] = useState(
    () => typeof window !== "undefined" && window.matchMedia(PHONE).matches,
  )

  useEffect(() => {
    const query = window.matchMedia(PHONE)
    const read = () => setPhone(query.matches)
    read()
    query.addEventListener("change", read)
    return () => query.removeEventListener("change", read)
  }, [])

  return phone
}
