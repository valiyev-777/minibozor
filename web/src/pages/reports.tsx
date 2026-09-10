/**
 * Hisobotlar — the ledger, which is the only report this shop needs a screen
 * for.
 *
 * Everything else somebody would call a report is a figure on the dashboard,
 * linked to the screen it is acted on from. What has no other home is the list
 * of *moves*: this many of this thing, from here to there, at this time, by
 * this person, for this reason.
 *
 * It exists because a count that looks wrong is not an argument. It is this
 * list, and the whole point of keeping the shelf as a ledger rather than as a
 * number somebody wrote is that the disagreement can be read rather than
 * debated.
 */

import { useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { api } from "@/lib/api"
import { dateTime, groups } from "@/lib/format"
import { useQuery } from "@tanstack/react-query"
import type { Page } from "@/lib/types"

type Movement = {
  id: number
  variant_id: number
  sku: string
  variant_label: string
  product_title: string
  kind: string
  quantity: number
  from_code: string
  to_code: string
  reason: string
  actor: string
  created_at: string
}

// The moves the room actually makes, in the words the people making them use.
const KINDS: { key: string; label: string }[] = [
  { key: "", label: "Hammasi" },
  { key: "receipt", label: "Qabul" },
  { key: "putaway", label: "Joylashtirish" },
  { key: "pick", label: "Terish" },
  { key: "delivered", label: "Yetkazildi" },
  { key: "damage", label: "Brak" },
  { key: "adjust", label: "Sanash farqi" },
  { key: "return", label: "Qaytgan" },
]

export function ReportsPage() {
  const [kind, setKind] = useState("")
  const [page, setPage] = useState(1)

  const ledger = useQuery({
    queryKey: ["movements", kind, page],
    queryFn: () => {
      const search = new URLSearchParams({ page: String(page), page_size: "50" })
      if (kind) search.set("kind", kind)
      return api<Page<Movement>>(`/warehouse/stock/movements?${search}`)
    },
  })

  return (
    <div className="space-y-4">
      <PageHeader
        title="Hisobotlar"
        subtitle="Daftar — har bir dona qayerdan qayerga ketgani" />

      <div className="flex flex-wrap gap-1">
        {KINDS.map((one) => (
          <button
            key={one.key}
            type="button"
            onClick={() => {
              setKind(one.key)
              setPage(1)
            }}
            className={cn(
              "h-control rounded-control border px-3 text-small",
              one.key === kind && "border-brand bg-brand-soft text-brand-deep",
            )}
          >
            {one.label}
          </button>
        ))}
      </div>

      <Problem error={ledger.error} />
      {ledger.isLoading ? <Waiting what="Daftar" /> : null}
      {ledger.data?.items.length === 0 ? (
        <Empty what="Bu turdagi harakat hali bo'lmagan." />
      ) : null}

      {ledger.data?.items.length ? (
        <div className="overflow-x-auto rounded-panel border border-line bg-surface shadow-panel">
          <table className="w-full text-small">
            <thead className="border-b text-micro text-ink-soft">
              <tr>
                <th className="p-2 text-left font-medium">Vaqt</th>
                <th className="p-2 text-left font-medium">Nima</th>
                <th className="p-2 text-right font-medium">Dona</th>
                <th className="p-2 text-left font-medium">Qayerdan</th>
                <th className="p-2 text-left font-medium">Qayerga</th>
                <th className="p-2 text-left font-medium">Kim</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {ledger.data.items.map((move) => (
                <tr key={move.id}>
                  <td className="whitespace-nowrap p-2 tabular text-ink-soft">
                    {dateTime(move.created_at)}
                  </td>
                  <td className="p-2">
                    <div className="truncate font-medium">{move.product_title}</div>
                    <div className="text-micro text-ink-faint">
                      {move.variant_label}
                      {move.reason ? ` · ${move.reason}` : ""}
                    </div>
                  </td>
                  <td className="p-2 text-right tabular font-semibold">
                    {groups(move.quantity)}
                  </td>
                  {/* "—" at either end is the outside world: a market run
                      arriving, a parcel out of the door. */}
                  <td className="whitespace-nowrap p-2 tabular">{move.from_code}</td>
                  <td className="whitespace-nowrap p-2 tabular">{move.to_code}</td>
                  <td className="whitespace-nowrap p-2 text-ink-soft">{move.actor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {ledger.data ? (
        <div className="flex items-center justify-between text-small text-ink-soft">
          <span>
            {ledger.data.total} ta harakat · {page}-sahifa
          </span>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={page === 1} onClick={() => setPage((was) => was - 1)}
            >
              Oldingi
            </Button>
            <Button variant="secondary" disabled={!ledger.data.has_more} onClick={() => setPage((was) => was + 1)}
            >
              Keyingi
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
