import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Removal, RemovalStatus } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Label, Select } from "@/components/ui/field"
import { CountStepper } from "@/components/ui/scan"
import { REMOVAL_REASON, REMOVAL_STATUS, REMOVAL_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "removals"]
const FILTERS: { value: "" | RemovalStatus; label: string }[] = [
  { value: "requested", label: "So'ralgan" },
  { value: "ready", label: "Tayyorlangan" },
  { value: "collected", label: "Olib ketilgan" },
  { value: "", label: "Hammasi" },
]

export function RemovalsPage() {
  const [status, setStatus] = React.useState<"" | RemovalStatus>("requested")
  const [open, setOpen] = React.useState<Removal | null>(null)

  const query = useQuery({
    queryKey: [...KEY, status],
    queryFn: () => api<Removal[]>("/staff/removals", { query: { status } }),
  })

  const columns: Column<Removal>[] = [
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
      key: "reason",
      header: "Sabab",
      sortValue: (row) => row.reason,
      cell: (row) => (
        <Badge tone={row.reason === "unsellable" ? "danger" : "neutral"}>
          {REMOVAL_REASON[row.reason]}
        </Badge>
      ),
    },
    {
      key: "quantity",
      header: "So'ralgan",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.lines.reduce((sum, line) => sum + line.quantity, 0),
      cell: (row) => row.lines.reduce((sum, line) => sum + line.quantity, 0),
    },
    {
      key: "prepared",
      header: "Tayyorlangan",
      headClassName: "text-right",
      className: "text-right tabular",
      cell: (row) =>
        row.status === "requested"
          ? "—"
          : row.lines.reduce((sum, line) => sum + (line.prepared_quantity ?? 0), 0),
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge tone={REMOVAL_TONE[row.status]}>{REMOVAL_STATUS[row.status]}</Badge>
      ),
    },
    {
      key: "requested_at",
      header: "So'ralgan",
      sortValue: (row) => row.requested_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.requested_at)}</span>,
    },
  ]

  return (
    <Page
      floor
      title="Qaytarib olish"
      hint="Tayyorlangandan keyin tovar band — javonda turadi, lekin sotilmaydi."
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={setOpen}
        emptyTitle="Buyruq yo'q"
        toolbar={
          <>
            <Label htmlFor="removal-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="removal-status"
              className="w-48"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | RemovalStatus)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.length ?? 0} ta buyruq</Hint>
          </>
        }
      />

      {open ? <RemovalSheet removal={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

/**
 * Picking a removal, then handing it over.
 *
 * Two separate acts on purpose. Marking it ready says the goods are on a
 * pallet by the door: still ours to account for, nobody's to buy — which is
 * what stops something being sold out from under its own collection. Handing
 * it over is when it actually leaves, and only then does the ledger say so.
 */
function RemovalSheet({ removal, onClose }: { removal: Removal; onClose: () => void }) {
  const [picked, setPicked] = React.useState<Record<number, number>>(() =>
    Object.fromEntries(
      removal.lines.map((line) => [line.id, line.prepared_quantity ?? line.quantity]),
    ),
  )
  const [confirming, setConfirming] = React.useState<"prepare" | "collect" | null>(null)

  const prepare = useAction<void, Removal>({
    run: () =>
      api<Removal>(`/staff/removals/${removal.id}/prepare`, {
        method: "POST",
        json: {
          lines: removal.lines.map((line) => ({
            line_id: line.id,
            prepared_quantity: picked[line.id] ?? 0,
          })),
        },
      }),
    invalidate: [KEY, ["staff", "shelf"]],
    success: (result) => `${result.code} tayyorlandi`,
    onDone: onClose,
  })

  const collect = useAction<void, Removal>({
    run: () => api<Removal>(`/staff/removals/${removal.id}/collect`, { method: "POST" }),
    invalidate: [KEY, ["staff", "shelf"], ["staff", "movements"]],
    success: (result) => `${result.code} sotuvchiga berildi`,
    onDone: onClose,
  })

  const total = removal.lines.reduce((sum, line) => sum + (picked[line.id] ?? 0), 0)

  return (
    <>
      <Dialog open onOpenChange={(next) => !next && onClose()}>
        <DialogPanel
          className="floor w-[min(96vw,52rem)]"
          title={`${removal.code} · ${removal.seller.name}`}
          description={`${REMOVAL_REASON[removal.reason]} · ${removal.note || "izohsiz"}`}
          footer={
            removal.status === "requested" ? (
              <Button size="lg" variant="primary" onClick={() => setConfirming("prepare")}>
                Tayyorlandi deb belgilash
              </Button>
            ) : removal.status === "ready" ? (
              <Button size="lg" variant="primary" onClick={() => setConfirming("collect")}>
                Sotuvchiga berildi
              </Button>
            ) : (
              <Hint>Bu buyruq yopilgan.</Hint>
            )
          }
        >
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-line text-[12px] uppercase tracking-wide text-ink-soft">
                <th className="py-2">Tovar</th>
                <th className="py-2 text-right">So'ralgan</th>
                <th className="py-2 text-center">Topilgan</th>
              </tr>
            </thead>
            <tbody>
              {removal.lines.map((line) => (
                <tr key={line.id} className="border-b border-line-soft">
                  <td className="py-2">
                    <span className="block font-medium text-ink">{line.product_title}</span>
                    <span className="tabular block text-[12px] text-ink-faint">
                      {line.sku} · {line.variant_label}
                    </span>
                  </td>
                  <td className="tabular py-2 text-right">{line.quantity}</td>
                  <td className="py-2">
                    {removal.status === "requested" ? (
                      <div className="flex justify-center">
                        <CountStepper
                          value={picked[line.id] ?? 0}
                          onChange={(next) =>
                            setPicked((current) => ({ ...current, [line.id]: next }))
                          }
                        />
                      </div>
                    ) : (
                      <p className="tabular text-center font-semibold">
                        {line.prepared_quantity ?? 0}
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {removal.status === "ready" ? (
            <p className="mt-3 rounded border border-warn/20 bg-warn-soft px-2.5 py-2 text-[14px] font-medium text-warn">
              Bu tovar hozir band: javonda turadi, lekin sotilmaydi.
            </p>
          ) : null}
        </DialogPanel>
      </Dialog>

      {confirming === "prepare" ? (
        <ConfirmDialog
          open
          onOpenChange={() => setConfirming(null)}
          title="Tayyorlandi deb belgilash"
          description={`${removal.code} · ${total} dona`}
          confirmLabel="Belgilash"
          pending={prepare.isPending}
          onConfirm={() => prepare.mutate()}
        >
          <Hint>
            Tovar javonda qoladi, lekin bandga o'tadi — hech kimga sotilmaydi.
            Jurnalga hozir hech narsa yozilmaydi.
          </Hint>
        </ConfirmDialog>
      ) : null}

      {confirming === "collect" ? (
        <ConfirmDialog
          open
          onOpenChange={() => setConfirming(null)}
          title="Sotuvchiga berildi"
          description={removal.code}
          confirmLabel="Berildi"
          destructive
          pending={collect.isPending}
          onConfirm={() => collect.mutate()}
        >
          <p className="rounded border border-danger/20 bg-danger-soft px-2.5 py-2 text-[14px] font-medium text-danger">
            Tovar shu paytda javondan chiqadi va jurnalga «sotuvchiga
            qaytarildi» deb yoziladi. Qaytarib bo'lmaydi.
          </p>
        </ConfirmDialog>
      ) : null}
    </>
  )
}
