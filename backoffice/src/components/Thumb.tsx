import * as React from "react"
import { mediaUrl } from "@/api/client"
import { cn } from "@/ui/cn"

/**
 * A product photograph, or the space where one would be.
 *
 * Three states and not two. A card with no picture gets the grey square; a
 * card whose picture is *missing from the server* would otherwise get the
 * browser's broken-image glyph, which reads as a bug in our screen rather
 * than as a gap in the media folder — and on a development database, where
 * the rows outlive the files, that is most of them. So a failed load falls
 * back to the same grey square, and the row still lines up.
 */
export function Thumb({
  src,
  className,
}: {
  src: string | undefined
  className?: string
}) {
  const [broken, setBroken] = React.useState(false)
  const box = cn(
    "shrink-0 rounded-[var(--radius-control)] border border-line object-cover",
    className,
  )

  // The API's paths are relative; `mediaUrl` is what turns one into somewhere
  // this browser can reach. Resolved here rather than at every call site,
  // because a raw `row.images[0]` in a `src` renders as a 404 against the
  // *panel's* origin and looks exactly like a missing file.
  const url = mediaUrl(src)
  if (!url || broken) {
    return <span className={cn(box, "block bg-line-soft")} aria-hidden="true" />
  }
  return <img src={url} alt="" className={box} onError={() => setBroken(true)} />
}
