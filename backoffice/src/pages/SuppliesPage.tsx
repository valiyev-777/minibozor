import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { toast } from "sonner"
import { api } from "@/api/client"
import type { Supply, SupplyStatus } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Label, Select, Textarea } from "@/components/ui/field"
import { CountStepper, ScanInput } from "@/components/ui/scan"
import { SUPPLY_STATUS, SUPPLY_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "supplies"]
const FILTERS: { value: "" | SupplyStatus; label: string }[] = [
  { value: "declared", label: "Kutilmoqda" },
  { value: "received", label: "Qabul qilingan" },
  { value: "cancelled", label: "Bekor qilingan" },
  { value: "", label: "Hammasi" },
]

export function SuppliesPage() {
  const [status, setStatus] = React.useState<"" | SupplyStatus>("declared")
  const [open, setOpen] = React.useState<Supply | null>(null)

  const query = useQuery({
    queryKey: [...KEY, status],
    queryFn: () => api<Supply[]>("/staff/supplies", { query: { status } }),
  })

  const columns: Column<Supply>[] = [
    {
      key: "code",
      header: "Kod",
      sortValue: (row) => row.code,
      cell: (row) => <span className="tabular font-semibold text-ink">{row.code}</span>,
    },
    {
      key: "seller",
      header: "Sotuvchi",
      sortValue: (row) => row.seller.name,
      cell: (row) => row.seller.name,
    },
    {
      key: "lines",
      header: "Satrlar",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.lines.length,
      cell: (row) => row.lines.length,
    },
    {
      key: "declared",
      header: "E'lon qilingan",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.lines.reduce((sum, line) => sum + line.declared_quantity, 0),
      cell: (row) => row.lines.reduce((sum, line) => sum + line.declared_quantity, 0),
    },
    {
      key: "received",
      header: "Sanalgan",
      headClassName: "text-right",
      className: "text-right tabular",
      cell: (row) => {
        const counted = row.lines.reduce((sum, line) => sum + (line.received_quantity ?? 0), 0)
        const declared = row.lines.reduce((sum, line) => sum + line.declared_quantity, 0)
        if (row.status !== "received") return "—"
        return (
          <>
            {counted}
            {counted !== declared ? (
              <span className="ml-1 font-semibold text-danger">
                {counted > declared ? "+" : ""}
                {counted - declared}
              </span>
            ) : null}
          </>
        )
      },
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => <Badge tone={SUPPLY_TONE[row.status]}>{SUPPLY_STATUS[row.status]}</Badge>,
    },
    {
      key: "declared_at",
      header: "E'lon",
      sortValue: (row) => row.declared_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.declared_at)}</span>,
    },
  ]

  return (
    <Page
      floor
      title="Partiyalar"
      hint="Sotuvchi e'lon qiladi, ombor sanaydi. Javon sanalganda ko'tariladi."
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={setOpen}
        emptyTitle="Partiya yo'q"
        emptyHint="Bu holatda hech narsa qolmagan."
        toolbar={
          <>
            <Label htmlFor="supply-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="supply-status"
              className="w-48"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | SupplyStatus)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.length ?? 0} ta partiya</Hint>
          </>
        }
      />

      {open ? <ReceiveSupply supply={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

/**
 * Counting a batch in.
 *
 * The scanner drives it: a scan finds the line by SKU and counts one more.
 * The declared figure sits beside the count with the difference between them,
 * because that gap is the only thing the seller and the warehouse will want to
 * talk about afterwards — and it has to be visible while there is still time
 * to go and look in the box again.
 */
function ReceiveSupply({ supply, onClose }: { supply: Supply; onClose: () => void }) {
  const [counted, setCounted] = React.useState<Record<number, number>>(() =>
    Object.fromEntries(supply.lines.map((line) => [line.id, line.received_quantity ?? 0])),
  )
  const [note, setNote] = React.useState("")
  const [confirming, setConfirming] = React.useState(false)
  const [lastScan, setLastScan] = React.useState<number | null>(null)

  const editable = supply.status === "declared"

  const receive = useAction<void, Supply>({
    run: () =>
      api<Supply>(`/staff/supplies/${supply.id}/receive`, {
        method: "POST",
        json: {
          lines: supply.lines.map((line) => ({
            line_id: line.id,
            received_quantity: counted[line.id] ?? 0,
          })),
          note,
        },
      }),
    invalidate: [KEY, ["staff", "shelf"], ["staff", "movements"]],
    success: (result) => `${result.code} qabul qilindi`,
    onDone: onClose,
  })

  const cancel = useAction<void, Supply>({
    run: () => api<Supply>(`/staff/supplies/${supply.id}/cancel`, { method: "POST" }),
    invalidate: [KEY],
    success: "Partiya bekor qilindi",
    onDone: onClose,
  })

  function scan(code: string) {
    const needle = code.trim().toLowerCase()
    const hits = supply.lines.filter(
      (line) =>
        line.sku.toLowerCase() === needle ||
        line.variant_label.toLowerCase() === needle ||
        `${line.sku}-${line.variant_label}`.toLowerCase() === needle,
    )
    if (hits.length === 0) {
      // Not a silence: an item that is not on the batch cannot be received
      // against it, and somebody has to decide what it is.
      toast.error(`${code} bu partiyada yo'q`)
      return
    }
    if (hits.length > 1) {
      toast.warning(`${code} — bir nechta satr, qo'lda tanlang`)
      setLastScan(hits[0]!.id)
      return
    }
    const line = hits[0]!
    setCounted((current) => ({ ...current, [line.id]: (current[line.id] ?? 0) + 1 }))
    setLastScan(line.id)
  }

  const declaredTotal = supply.lines.reduce((sum, line) => sum + line.declared_quantity, 0)
  const countedTotal = supply.lines.reduce((sum, line) => sum + (counted[line.id] ?? 0), 0)

  return (
    <>
      <Dialog open onOpenChange={(next) => !next && onClose()}>
        <DialogPanel
          className="floor w-[min(96vw,56rem)]"
          title={`${supply.code} · ${supply.seller.name}`}
          description={
            editable
              ? "Skanerlang yoki qo'lda kiriting — har bir skan bitta dona"
              : `Qabul qilingan ${when(supply.received_at)}`
          }
          footer={
            editable ? (
              <>
                <Button size="lg" variant="quiet" onClick={() => cancel.mutate()}>
                  Bekor qilish
                </Button>
                <Button size="lg" variant="primary" onClick={() => setConfirming(true)}>
                  Qabul qilish
                </Button>
              </>
            ) : (
              <Button size="lg" variant="ghost" onClick={onClose}>
                Yopish
              </Button>
            )
          }
        >
          <div className="space-y-3">
            {editable ? (
              <ScanInput
                onScan={scan}
                hint={`Jami sanalgan: ${countedTotal} / e'lon qilingan ${declaredTotal}`}
              />
            ) : null}

            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line text-[12px] uppercase tracking-wide text-ink-soft">
                  <th className="py-2">Tovar</th>
                  <th className="py-2 text-right">E'lon</th>
                  <th className="py-2 text-center">Sanoq</th>
                  <th className="py-2 text-right">Farq</th>
                </tr>
              </thead>
              <tbody>
                {supply.lines.map((line) => {
                  const value = counted[line.id] ?? 0
                  const difference = value - line.declared_quantity
                  return (
                    <tr
                      key={line.id}
                      className={
                        lastScan === line.id
                          ? "border-b border-line-soft bg-accent-soft"
                          : "border-b border-line-soft"
                      }
                    >
                      <td className="py-2">
                        <span className="block font-medium text-ink">{line.product_title}</span>
                        <span className="tabular block text-[12px] text-ink-faint">
                          {line.sku} · {line.variant_label}
                        </span>
                      </td>
                      <td className="tabular py-2 text-right">{line.declared_quantity}</td>
                      <td className="py-2">
                        {editable ? (
                          <div className="flex justify-center">
                            <CountStepper
                              value={value}
                              onChange={(next) =>
                                setCounted((current) => ({ ...current, [line.id]: next }))
                              }
                            />
                          </div>
                        ) : (
                          <p className="tabular text-center font-semibold">
                            {line.received_quantity ?? 0}
                          </p>
                        )}
                      </td>
                      <td className="tabular py-2 text-right">
                        {difference === 0 ? (
                          <span className="text-ink-faint">0</span>
                        ) : (
                          <span className="font-semibold text-danger">
                            {difference > 0 ? "+" : ""}
                            {difference}
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>

            {editable ? (
              <div className="space-y-1">
                <Label htmlFor="supply-note">Izoh</Label>
                <Textarea
                  id="supply-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="2 tasi yetib kelmadi"
                />
                <Hint>Har bir kirim harakatining sababi bo'lib yoziladi.</Hint>
              </div>
            ) : (
              <Hint>{supply.note || "Izoh yo'q"}</Hint>
            )}
          </div>
        </DialogPanel>
      </Dialog>

      {confirming ? (
        <ConfirmDialog
          open
          onOpenChange={setConfirming}
          title="Partiyani qabul qilish"
          description={`${supply.code} · sanalgan ${countedTotal}, e'lon qilingan ${declaredTotal}`}
          confirmLabel="Javonga qo'shish"
          pending={receive.isPending}
          onConfirm={() => receive.mutate()}
        >
          {countedTotal === declaredTotal ? (
            <Hint>Sanoq e'lon bilan to'liq mos.</Hint>
          ) : (
            <p className="rounded border border-danger/20 bg-danger-soft px-2.5 py-2 text-[14px] font-medium text-danger">
              Farq: {countedTotal - declaredTotal > 0 ? "+" : ""}
              {countedTotal - declaredTotal}. Sanoq faktdir, e'lon esa va'da —
              ikkalasi ham saqlanadi.
            </p>
          )}
        </ConfirmDialog>
      ) : null}
    </>
  )
}
