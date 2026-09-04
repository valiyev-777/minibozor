import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { toast } from "sonner"
import { api } from "@/api/client"
import type { StaffOffer, StockCount, StockCountStatus } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Hint, Input, Label, Select, Textarea } from "@/components/ui/field"
import { CountStepper, ScanInput } from "@/components/ui/scan"
import { COUNT_STATUS, COUNT_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "counts"]
const FILTERS: { value: "" | StockCountStatus; label: string }[] = [
  { value: "open", label: "Ochiq" },
  { value: "closed", label: "Yopilgan" },
  { value: "", label: "Hammasi" },
]

export function CountsPage() {
  const [status, setStatus] = React.useState<"" | StockCountStatus>("open")
  const [open, setOpen] = React.useState<StockCount | null>(null)
  const [opening, setOpening] = React.useState(false)

  const query = useQuery({
    queryKey: [...KEY, status],
    queryFn: () => api<StockCount[]>("/staff/stock-counts", { query: { status } }),
  })

  const columns: Column<StockCount>[] = [
    {
      key: "code",
      header: "Kod",
      sortValue: (row) => row.code,
      cell: (row) => <span className="tabular font-semibold text-ink">{row.code}</span>,
    },
    {
      key: "product",
      header: "Mahsulot",
      sortValue: (row) => row.product_title,
      cell: (row) => (
        <>
          <span className="block max-w-72 truncate text-ink">{row.product_title}</span>
          <span className="block text-[12px] text-ink-faint">{row.seller.name}</span>
        </>
      ),
    },
    {
      key: "expected",
      header: "Kutilgan",
      headClassName: "text-right",
      className: "text-right tabular",
      cell: (row) => row.lines.reduce((sum, line) => sum + line.expected, 0),
    },
    {
      key: "difference",
      header: "Farq",
      headClassName: "text-right",
      className: "text-right tabular",
      cell: (row) => {
        if (row.status === "open") return <span className="text-warn">sanalmoqda</span>
        const total = row.lines.reduce((sum, line) => sum + (line.difference ?? 0), 0)
        return total === 0 ? (
          <span className="text-good">0</span>
        ) : (
          <span className="font-semibold text-danger">
            {total > 0 ? "+" : ""}
            {total}
          </span>
        )
      },
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => <Badge tone={COUNT_TONE[row.status]}>{COUNT_STATUS[row.status]}</Badge>,
    },
    {
      key: "opened",
      header: "Ochilgan",
      sortValue: (row) => row.opened_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.opened_at)}</span>,
    },
  ]

  return (
    <Page
      floor
      title="Inventarizatsiya"
      hint="Kutilgan son ochilganda muzlatiladi — sanoq paytida sotilgani farq emas."
      actions={
        <Button size="lg" variant="primary" onClick={() => setOpening(true)}>
          <Plus />
          Sanoq ochish
        </Button>
      }
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={setOpen}
        emptyTitle="Sanoq yo'q"
        toolbar={
          <>
            <Label htmlFor="count-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="count-status"
              className="w-44"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | StockCountStatus)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.length ?? 0} ta sanoq</Hint>
          </>
        }
      />

      {opening ? <OpenCount onClose={() => setOpening(false)} /> : null}
      {open ? <CountSheet count={open} onClose={() => setOpen(null)} /> : null}
    </Page>
  )
}

function OpenCount({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = React.useState("")
  const [offerId, setOfferId] = React.useState<number | null>(null)
  const [note, setNote] = React.useState("")

  const offers = useQuery({
    queryKey: ["staff", "shelf", "offers"],
    queryFn: () => api<StaffOffer[]>("/staff/offers"),
  })

  const needle = query.trim().toLowerCase()
  const matches = (offers.data ?? [])
    .filter(
      (offer) =>
        !needle ||
        offer.product_title.toLowerCase().includes(needle) ||
        offer.seller.name.toLowerCase().includes(needle),
    )
    .slice(0, 12)

  const start = useAction<void, StockCount>({
    run: () =>
      api<StockCount>("/staff/stock-counts", {
        method: "POST",
        json: { offer_id: offerId, note },
      }),
    invalidate: [KEY],
    success: (count) => `${count.code} ochildi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Sanoq ochish"
      description="Qaysi javon sanaladi"
      confirmLabel="Ochish"
      disabled={offerId === null}
      pending={start.isPending}
      onConfirm={() => start.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="count-search">Javon</Label>
          <Input
            id="count-search"
            autoFocus
            value={query}
            placeholder="Mahsulot yoki sotuvchi"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <ul className="max-h-64 space-y-1 overflow-y-auto">
          {matches.map((offer) => (
            <li key={offer.id}>
              <button
                type="button"
                onClick={() => setOfferId(offer.id)}
                className={
                  offerId === offer.id
                    ? "w-full rounded border-2 border-accent bg-accent-soft px-2.5 py-2 text-left"
                    : "w-full rounded border border-line px-2.5 py-2 text-left hover:bg-line-soft"
                }
              >
                <span className="block text-[14px] font-medium text-ink">
                  {offer.product_title}
                </span>
                <span className="tabular block text-[12px] text-ink-faint">
                  {offer.seller.name} · javonda {offer.stock_left}
                </span>
              </button>
            </li>
          ))}
          {offers.data && matches.length === 0 ? <Hint>Topilmadi.</Hint> : null}
        </ul>
        <div className="space-y-1">
          <Label htmlFor="count-note">Izoh</Label>
          <Textarea
            id="count-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Chorak sanog'i"
          />
        </div>
      </div>
    </ConfirmDialog>
  )
}

/**
 * The count sheet.
 *
 * The scanner counts: one scan is one item found. The expected figure and the
 * difference stay on screen the whole time, because a discrepancy is worth
 * seeing while somebody is still standing in front of the shelf and can go and
 * look again — reading it afterwards in a report is too late to be useful.
 */
function CountSheet({ count, onClose }: { count: StockCount; onClose: () => void }) {
  const [found, setFound] = React.useState<Record<string, number>>(() =>
    Object.fromEntries(
      count.lines.map((line) => [String(line.variant_id ?? "all"), line.counted ?? 0]),
    ),
  )
  const [note, setNote] = React.useState("")
  const [confirming, setConfirming] = React.useState(false)
  const [lastScan, setLastScan] = React.useState<string | null>(null)

  const editable = count.status === "open"
  const key = (line: { variant_id: number | null }) => String(line.variant_id ?? "all")

  const close = useAction<void, StockCount>({
    run: () =>
      api<StockCount>(`/staff/stock-counts/${count.id}/close`, {
        method: "POST",
        json: {
          lines: count.lines.map((line) => ({
            variant_id: line.variant_id,
            counted: found[key(line)] ?? 0,
          })),
          note,
        },
      }),
    invalidate: [KEY, ["staff", "shelf"], ["staff", "movements"]],
    success: (result) => `${result.code} yopildi`,
    onDone: onClose,
  })

  function scan(code: string) {
    const needle = code.trim().toLowerCase()
    const hits = count.lines.filter(
      (line) =>
        line.sku.toLowerCase() === needle || line.variant_label.toLowerCase() === needle,
    )
    if (hits.length === 0) {
      toast.error(`${code} bu sanoqda yo'q`)
      return
    }
    if (hits.length > 1) {
      toast.warning(`${code} — bir nechta uya, o'lchamni tanlang`)
      setLastScan(key(hits[0]!))
      return
    }
    const line = hits[0]!
    setFound((current) => ({ ...current, [key(line)]: (current[key(line)] ?? 0) + 1 }))
    setLastScan(key(line))
  }

  const expected = count.lines.reduce((sum, line) => sum + line.expected, 0)
  const counted = count.lines.reduce((sum, line) => sum + (found[key(line)] ?? 0), 0)

  return (
    <>
      <Dialog open onOpenChange={(next) => !next && onClose()}>
        <DialogPanel
          className="floor w-[min(96vw,52rem)]"
          title={`${count.code} · ${count.product_title}`}
          description={
            editable
              ? "Har bir skan bitta dona sanaladi"
              : `Yopilgan ${when(count.closed_at)}`
          }
          footer={
            editable ? (
              <Button size="lg" variant="primary" onClick={() => setConfirming(true)}>
                Sanoqni yopish
              </Button>
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
                hint={
                  <>
                    Sanalgan {counted} / kutilgan {expected}
                    {counted !== expected ? (
                      <span className="ml-1 font-semibold text-danger">
                        farq {counted - expected > 0 ? "+" : ""}
                        {counted - expected}
                      </span>
                    ) : null}
                  </>
                }
              />
            ) : null}

            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-line text-[12px] uppercase tracking-wide text-ink-soft">
                  <th className="py-2">Uya</th>
                  <th className="py-2 text-right">Kutilgan</th>
                  <th className="py-2 text-center">Sanalgan</th>
                  <th className="py-2 text-right">Farq</th>
                </tr>
              </thead>
              <tbody>
                {count.lines.map((line) => {
                  const value = found[key(line)] ?? 0
                  const difference = value - line.expected
                  return (
                    <tr
                      key={key(line)}
                      className={
                        lastScan === key(line)
                          ? "border-b border-line-soft bg-accent-soft"
                          : "border-b border-line-soft"
                      }
                    >
                      <td className="py-2 font-medium text-ink">{line.variant_label}</td>
                      <td className="tabular py-2 text-right">{line.expected}</td>
                      <td className="py-2">
                        {editable ? (
                          <div className="flex justify-center">
                            <CountStepper
                              value={value}
                              onChange={(next) =>
                                setFound((current) => ({ ...current, [key(line)]: next }))
                              }
                            />
                          </div>
                        ) : (
                          <p className="tabular text-center font-semibold">
                            {line.counted ?? 0}
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
                <Label htmlFor="close-note">Izoh</Label>
                <Textarea
                  id="close-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Bittasi yo'q"
                />
                <Hint>Har bir tuzatish harakatining sababi bo'lib yoziladi.</Hint>
              </div>
            ) : (
              <Hint>{count.note || "Izoh yo'q"}</Hint>
            )}
          </div>
        </DialogPanel>
      </Dialog>

      {confirming ? (
        <ConfirmDialog
          open
          onOpenChange={setConfirming}
          title="Sanoqni yopish"
          description={`${count.code} · sanalgan ${counted}, kutilgan ${expected}`}
          confirmLabel="Yopish va tuzatish"
          destructive={counted !== expected}
          pending={close.isPending}
          onConfirm={() => close.mutate()}
        >
          {counted === expected ? (
            <Hint>Farq yo'q — hech qanday tuzatish yozilmaydi.</Hint>
          ) : (
            <p className="rounded border border-danger/20 bg-danger-soft px-2.5 py-2 text-[14px] font-medium text-danger">
              {counted - expected > 0 ? "+" : ""}
              {counted - expected} farq harakat sifatida yoziladi va javon
              shunga tuzatiladi. Yopilgandan keyin qaytarib bo'lmaydi.
            </p>
          )}
        </ConfirmDialog>
      ) : null}
    </>
  )
}
