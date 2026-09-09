/**
 * A screen that exists as a route and not yet as a screen.
 *
 * Named rather than blank, because a nav item that leads to an empty page is
 * indistinguishable from one that is broken — and this app is being built in
 * front of the person who will use it.
 */

import { Construction } from "lucide-react"

export function Soon({ title, what }: { title: string; what: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
      <div className="flex items-start gap-3 rounded-panel border border-dashed bg-surface p-6 text-ink-soft">
        <Construction className="size-5 shrink-0 text-warn" />
        <p className="text-small">{what}</p>
      </div>
    </div>
  )
}
