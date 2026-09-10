/**
 * Yorliqlar — an A4 sheet the browser prints.
 *
 * We generate the barcodes, because market goods arrive with none: no label,
 * no code, and two sacks of the same shoe from two traders would collide if
 * there were. A variant's barcode is permanent — this screen **reprints** what
 * is on the row and never asks for a new one, or the shelf ends up holding
 * one thing under two codes.
 *
 * The barcode is drawn in the browser. A barcode is a picture of a string, so
 * rendering it here means no image to store, no font to install on a server,
 * and a reprint that cannot drift from the code it claims to be.
 */

import bwipjs from "bwip-js/browser"
import { Printer } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Empty, PageHeader, Problem, Waiting } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { money } from "@/lib/format"
import { useLabels, useSupplies } from "@/lib/queries"

type What = { kind: "cells" } | { kind: "supply"; id: number }

export function LabelsPage() {
  const [what, setWhat] = useState<What | null>(null)
  const runs = useSupplies("received")
  const [runId, setRunId] = useState("")

  const params =
    what?.kind === "cells" ? "cells=true" : what ? `supply_id=${what.id}` : ""
  const sheet = useLabels(params, Boolean(params))

  return (
    <div className="space-y-4">
      <PageHeader title="Yorliqlar" subtitle="A4 varaq — brauzerdan chop etiladi">
        {sheet.data ? (
          <Button onClick={() => window.print()} className="h-control gap-2">
            <Printer className="size-4" />
            Chop etish
          </Button>
        ) : null}
      </PageHeader>

      <div className="no-print space-y-3 rounded-panel border border-line bg-surface shadow-panel p-3">
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex-1">
            <span className="mb-1 block text-micro text-ink-soft">
              Qabul raqami — o'sha safarning hamma yorlig'i
            </span>
            <Input
              value={runId}
              onChange={(event) => setRunId(event.target.value.replace(/\D/g, ""))}
              inputMode="numeric"
              placeholder="12"
              className="h-control tabular"
              aria-label="Qabul raqami" />
          </label>
          <Button disabled={!runId} onClick={() => setWhat({ kind: "supply", id: Number(runId) })}
          >
            Tovar yorliqlari
          </Button>
          <Button variant="secondary" onClick={() => setWhat({ kind: "cells" })}
          >
            Katak yorliqlari
          </Button>
        </div>

        {runs.data?.length ? (
          <p className="text-micro text-ink-soft">
            Oxirgi qabullar:{" "}
            {runs.data.slice(0, 6).map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => {
                  setRunId(String(run.id))
                  setWhat({ kind: "supply", id: run.id })
                }}
                className="mr-2 tabular underline underline-offset-2">
                {run.code}
              </button>
            ))}
          </p>
        ) : null}
      </div>

      <Problem error={sheet.error} />
      {sheet.isFetching ? <Waiting what="Yorliqlar" /> : null}

      {sheet.data?.products.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {sheet.data.products.map((label) => (
            <ProductLabel key={label.variant_id} {...label} />
          ))}
        </div>
      ) : null}

      {sheet.data?.cells.length ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {sheet.data.cells.map((cell) => (
            <div
              key={cell.code}
              className="grid aspect-[2/1] place-items-center rounded-control border bg-surface">
              {/* A cell label is read across a room, so it is one enormous
                  string and nothing else. */}
              <span className="tabular text-2xl font-bold tracking-tight">
                {cell.code}
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {sheet.data && !sheet.data.products.length && !sheet.data.cells.length ? (
        <Empty what="Bu tanlovda yorliq yo'q." />
      ) : null}
    </div>
  )
}

function ProductLabel({
  product_title,
  variant_label,
  sku,
  barcode,
  price,
}: {
  product_title: string
  variant_label: string
  sku: string
  barcode: string
  price: number
}) {
  return (
    <div className="break-inside-avoid rounded-control border bg-surface p-2">
      <div className="truncate text-micro text-ink-soft">{product_title}</div>
      <div className="truncate text-small font-semibold">{variant_label || "—"}</div>
      <Barcode value={barcode} />
      <div className="flex items-baseline justify-between text-micro">
        <span className="tabular text-ink-faint">{sku}</span>
        <span className="tabular font-medium">{money(price)}</span>
      </div>
    </div>
  )
}

function Barcode({ value }: { value: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvas.current || !value) return
    try {
      bwipjs.toCanvas(canvas.current, {
        bcid: "code128",
        text: value,
        scale: 2,
        height: 10,
        includetext: true,
        textxalign: "center",
      })
    } catch {
      // A code that will not encode is a code somebody has to look at, and a
      // thrown error here would take the whole sheet down with it.
    }
  }, [value])

  return <canvas ref={canvas} className="my-1 w-full" aria-label={value} />
}
