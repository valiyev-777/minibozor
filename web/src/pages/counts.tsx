/**
 * Sanash — recounting one cell.
 *
 * A cell at a time, because a stocktake of the whole warehouse is a day
 * nobody has and a cell is what one person can count without stopping the
 * shop.
 *
 * The screen shows what the system thinks is there and takes what is actually
 * there beside it. **Both are kept.** The difference is the whole point of a
 * count — it becomes an `adjust` movement with the counter's name on it — and
 * a screen that only took the new figure would leave nobody able to say how
 * far the shelf had drifted.
 */

import { Check } from "lucide-react"
import { useEffect, useState } from "react"

import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { groups } from "@/lib/format"
import { useCount, useStartCount, useSubmitCount } from "@/lib/queries"

export function CountsPage() {
  const [code, setCode] = useState("")
  const [id, setId] = useState<number | null>(null)
  const start = useStartCount()

  if (id) return <Counting id={id} onDone={() => setId(null)} />

  return (
    <div className="space-y-4">
      <PageHeader title="Sanash" subtitle="Bitta katakni qayta sanash" />
      <Panel>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            start.mutate(code.trim().toUpperCase(), {
              onSuccess: (count) => {
                setId(count.id)
                setCode("")
              },
            })
          }}
          className="flex flex-wrap gap-2">
          <Input
            autoFocus
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder="A-02-03"
            aria-label="Katak kodi"
            className="h-control-lg flex-1 tabular text-body" />
          <Button size="lg" type="submit" disabled={start.isPending || !code.trim()} >
            Sanashni boshlash
          </Button>
        </form>
      </Panel>
      <Problem error={start.error} />
    </div>
  )
}

/**
 * The count itself, and it is **the whole screen** rather than an overlay.
 *
 * Named `Sheet` once, which was the only thing overlay about it: a person
 * counting a cell has a trolley in one hand and is reading a column of
 * figures off a shelf, and the list they are filling in is the screen's
 * entire job — not something laid over the screen they came from. The way
 * back is the page header's own button.
 */
function Counting({ id, onDone }: { id: number; onDone: () => void }) {
  const count = useCount(id)
  const submit = useSubmitCount(id)
  const [counted, setCounted] = useState<Record<number, string>>({})
  const [note, setNote] = useState("")

  // Seeded with what the system believes, so a cell that is exactly right is
  // one tap. The figures a person changes are the findings.
  useEffect(() => {
    if (!count.data) return
    setCounted(
      Object.fromEntries(
        count.data.lines.map((line) => [line.variant_id, String(line.expected_qty)]),
      ),
    )
  }, [count.data])

  if (count.isLoading) return <Waiting what="Katak" />
  if (!count.data) return <Problem error={count.error} />

  const closed = count.data.status === "closed"

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${count.data.location_code} — sanash`}
        subtitle={closed ? "Yakunlangan" : "Nechta borligini yozing"}
      >
        <Button variant="ghost" onClick={onDone}>
          Orqaga
        </Button>
      </PageHeader>

      <Problem error={submit.error} />

      {count.data.lines.length === 0 ? (
        <Empty what="Tizim bu katakni bo'sh deb biladi. Agar ichida narsa bo'lsa, uni mahsulot bo'yicha qidirib qo'shing." />
      ) : null}

      <ul className="space-y-2">
        {count.data.lines.map((line) => {
          const value = counted[line.variant_id] ?? String(line.expected_qty)
          const difference = Number(value || 0) - line.expected_qty
          return (
            <li key={line.variant_id}>
              <Panel>
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-small text-ink-soft">
                      {line.product_title}
                    </div>
                    <div className="text-body font-semibold">{line.variant_label}</div>
                    <div className="text-micro tabular text-ink-faint">{line.barcode}</div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-micro text-ink-faint">tizimda</div>
                    <div className="tabular text-body">{groups(line.expected_qty)}</div>
                  </div>
                  <div className="w-24 shrink-0">
                    <Input
                      value={value}
                      disabled={closed}
                      inputMode="numeric"
                      aria-label={`${line.variant_label} — sanalgan`}
                      onChange={(event) =>
                        setCounted((was) => ({
                          ...was,
                          [line.variant_id]: event.target.value.replace(/\D/g, ""),
                        }))
                      }
                      className="h-control-lg tabular text-body" />
                    {difference ? (
                      <div
                        className={cn(
                          "mt-1 text-center text-micro tabular",
                          difference > 0 ? "text-good" : "text-danger",
                        )}
                      >
                        {difference > 0 ? "+" : ""}
                        {difference}
                      </div>
                    ) : null}
                  </div>
                </div>
              </Panel>
            </li>
          )
        })}
      </ul>

      {!closed && count.data.lines.length ? (
        <Panel>
          <div className="space-y-2">
            <Input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Izoh (ixtiyoriy)"
              aria-label="Izoh"
              className="h-control" />
            <Button size="lg" className="w-full gap-2" disabled={submit.isPending} onClick={() =>
                submit.mutate(
                  {
                    lines: count.data.lines.map((line) => ({
                      variant_id: line.variant_id,
                      counted_qty: Number(counted[line.variant_id] ?? line.expected_qty),
                    })),
                    note,
                  },
                  { onSuccess: onDone },
                )
              }
            >
              <Check className="size-5" />
              Sanashni yakunlash
            </Button>
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
