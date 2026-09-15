/**
 * Yorliqlar — the reprint bench.
 *
 * The first print of a receipt happens on `/qabul`, in the same minute the
 * goods are booked in. This screen is the second one: **printers jam**, a roll
 * runs out halfway, a sticker comes off in the rain — and the alternative to a
 * reprint is somebody writing a barcode on a box by hand.
 *
 * We generate the barcodes, because market goods arrive with none. A variant's
 * barcode is **permanent**: this screen reprints what is already on the row and
 * never asks for a new one, or the shelf ends up holding one thing under two
 * codes.
 *
 * Three ways in, and all three are in the URL so a receipt line can link
 * straight here: `?supply_id=12` is a whole market run in the order it was
 * received, `?variant_id=7` is one shoe, `?cells=1` is the shelf-edge labels.
 */

import { Printer, Search } from "lucide-react"
import { useMemo, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { CellRoll, LabelRoll, type RollLabel } from "@/components/label-roll"
import { Empty, PageHeader, Panel, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useLabels, useSupplies, useWhereIs } from "@/lib/queries"

export function LabelsPage() {
  // The URL is the state. A receipt line links in with `?supply_id=12`, the
  // buttons below write the same parameter, and the two cannot disagree.
  const [search, setSearch] = useSearchParams()
  const runId = Number(search.get("supply_id") ?? "") || null
  const variantIds = search.getAll("variant_id").filter((id) => Number(id) > 0)
  const wantsCells = search.get("cells") === "1"

  const params = wantsCells
    ? "cells=true"
    : runId
      ? `supply_id=${runId}`
      : variantIds.length
        ? variantIds.map((id) => `variant_id=${id}`).join("&")
        : ""
  const sheet = useLabels(params, Boolean(params))

  // How many of each, when the answer is not "as many as arrived". A jammed
  // print of one shoe is three stickers, not the twenty on the receipt.
  const [copies, setCopies] = useState("")

  const labels: RollLabel[] = useMemo(() => {
    const rows = sheet.data?.products ?? []
    const each = Number(copies)
    if (!each || each < 1) return rows
    return rows.map((row) => ({ ...row, copies: each }))
  }, [sheet.data, copies])

  const cells = sheet.data?.cells ?? []
  const something = labels.length > 0 || cells.length > 0

  function ask(next: Record<string, string | string[]>) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(next)) {
      for (const one of Array.isArray(value) ? value : [value]) params.append(key, one)
    }
    setSearch(params)
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Yorliqlar" subtitle="58 × 40 mm termal yorliq — har dona uchun bittadan">
        {something ? (
          <Button className="gap-2" onClick={() => window.print()}>
            <Printer className="size-4" />
            Chop etish
          </Button>
        ) : null}
      </PageHeader>

      <Panel title="Nimani chop etamiz" className="no-print">
        <div className="space-y-4">
          <ByRun runId={runId} copies={copies} onCopies={setCopies} onAsk={ask} />
          <ByVariant onAsk={ask} />
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <Button variant="secondary" onClick={() => ask({ cells: "1" })}>
              Katak yorliqlari
            </Button>
            <p className="text-micro text-ink-faint">
              Javon chetiga yopishtiriladi — kodi katta, ostida shtrix-kodi.
            </p>
          </div>
        </div>
      </Panel>

      {/* The five-minute support call every shop makes once, answered in the
          screen's own words — the same sentence /qabul says. */}
      <p className="no-print text-micro text-ink-faint">
        Birinchi marta chop etishda brauzer oynasida: <b>Headers and footers</b> belgisini
        oling, <b>Margins</b> ni <b>None</b> qiling. Har dona uchun bitta yorliq — 58 × 40 mm.
      </p>

      <Problem error={sheet.error} />
      {sheet.isFetching ? <Waiting what="Yorliqlar" /> : null}

      {labels.length ? <LabelRoll labels={labels} /> : null}
      {cells.length ? <CellRoll cells={cells} /> : null}

      {sheet.data && !something ? <Empty what="Bu tanlovda yorliq yo'q." /> : null}
    </div>
  )
}

/** A whole market run, in the order it was received. */
function ByRun({
  runId,
  copies,
  onCopies,
  onAsk,
}: {
  runId: number | null
  copies: string
  onCopies: (value: string) => void
  onAsk: (next: Record<string, string | string[]>) => void
}) {
  const runs = useSupplies("received")
  const [typed, setTyped] = useState(runId ? String(runId) : "")

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-40 flex-1">
          <span className="mb-1 block text-micro text-ink-soft">
            Qabul raqami — o'sha safarning hamma yorlig'i
          </span>
          <Input
            value={typed}
            onChange={(event) => setTyped(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="12"
            className="tabular"
            aria-label="Qabul raqami"
          />
        </label>
        <Button disabled={!typed} onClick={() => onAsk({ supply_id: typed })}>
          Tovar yorliqlari
        </Button>
        <label className="w-36">
          <span className="mb-1 block text-micro text-ink-soft">Har xildan</span>
          <Input
            value={copies}
            onChange={(event) => onCopies(event.target.value.replace(/\D/g, ""))}
            inputMode="numeric"
            placeholder="kelganicha"
            className="tabular"
            aria-label="Har xildan nechta yorliq"
          />
        </label>
      </div>

      {runs.data?.length ? (
        <p className="text-micro text-ink-soft">
          Oxirgi qabullar:{" "}
          {runs.data.slice(0, 6).map((run) => (
            <button
              key={run.id}
              type="button"
              onClick={() => {
                setTyped(String(run.id))
                onAsk({ supply_id: String(run.id) })
              }}
              className="mr-2 tabular underline underline-offset-2"
            >
              {run.code}
            </button>
          ))}
        </p>
      ) : null}
    </div>
  )
}

/**
 * One shoe, found the way the warehouse finds anything: by name, by SKU or by
 * scanning the sticker that is already on it. The server answers one copy per
 * variant, so the count beside it is the one that decides.
 */
function ByVariant({ onAsk }: { onAsk: (next: Record<string, string | string[]>) => void }) {
  const [needle, setNeedle] = useState("")
  const found = useWhereIs(needle)
  const rows = found.data ?? []

  return (
    <div className="space-y-2 border-t border-line pt-3">
      <label className="block">
        <span className="mb-1 block text-micro text-ink-soft">
          Bitta xil — nomi, SKU yoki shtrix-kodi
        </span>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 size-4 -translate-y-1/2 text-ink-faint" />
          <Input
            value={needle}
            onChange={(event) => setNeedle(event.target.value)}
            placeholder="Oq krossovka 43"
            className="pl-8"
            aria-label="Xilni qidirish"
          />
        </div>
      </label>

      {needle.trim().length > 1 && found.data && rows.length === 0 ? (
        <p className="text-micro text-ink-faint">Topilmadi.</p>
      ) : null}

      {rows.length ? (
        <ul className="divide-y divide-line rounded-control border border-line">
          {rows.slice(0, 8).map((row) => (
            <li key={row.variant_id} className="flex items-center gap-3 p-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-small font-medium">{row.product_title}</div>
                <div className="truncate text-micro text-ink-soft">
                  {row.variant_label || "—"} · <span className="tabular">{row.sku}</span>
                </div>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onAsk({ variant_id: String(row.variant_id) })}
              >
                Yorliq
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
