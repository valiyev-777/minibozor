import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { ReturnStatus, StaffReturn } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { FieldError, Hint, Label, Select, Textarea } from "@/components/ui/field"
import { RETURN_STATUS, RETURN_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { money, when } from "@/lib/utils"

const KEY = ["staff", "returns"]
const FILTERS: { value: "" | ReturnStatus; label: string }[] = [
  { value: "submitted", label: "Javob kutayotgan" },
  { value: "approved", label: "Tasdiqlangan" },
  { value: "rejected", label: "Rad etilgan" },
  { value: "refunded", label: "Puli qaytarilgan" },
  { value: "", label: "Hammasi" },
]

type Decision = "approve" | "reject" | "refund"

const DECISION: Record<Decision, { title: string; confirm: string; destructive?: boolean }> = {
  approve: { title: "Qaytarishni tasdiqlash", confirm: "Tasdiqlash" },
  reject: { title: "Qaytarishni rad etish", confirm: "Rad etish", destructive: true },
  refund: { title: "Pulni qaytarish", confirm: "Qaytarildi deb belgilash" },
}

export function ReturnsPage() {
  const [status, setStatus] = React.useState<"" | ReturnStatus>("submitted")
  const [open, setOpen] = React.useState<StaffReturn | null>(null)

  const query = useQuery({
    queryKey: [...KEY, status],
    queryFn: () => api<StaffReturn[]>("/staff/returns", { query: { status } }),
  })

  const columns: Column<StaffReturn>[] = [
    {
      key: "order",
      header: "Buyurtma",
      sortValue: (row) => row.order_code,
      cell: (row) => <span className="tabular font-medium text-ink">{row.order_code}</span>,
    },
    {
      key: "customer",
      header: "Mijoz",
      sortValue: (row) => row.customer_name,
      cell: (row) => (
        <>
          <span className="block truncate text-ink">{row.customer_name || "—"}</span>
          <span className="tabular block text-[12px] text-ink-faint">{row.customer_phone}</span>
        </>
      ),
    },
    {
      key: "reason",
      header: "Sabab",
      cell: (row) => <span className="line-clamp-2 max-w-72 text-ink-soft">{row.reason}</span>,
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge tone={RETURN_TONE[row.status]}>{RETURN_STATUS[row.status]}</Badge>
      ),
    },
    {
      key: "refund",
      header: "Qaytarilgan",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.refund_amount,
      cell: (row) => (row.refund_amount ? money(row.refund_amount) : "—"),
    },
    {
      key: "created",
      header: "Yuborilgan",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
  ]

  return (
    <Page
      title="Qaytarishlar"
      hint="Mijoz javob kutib turadi — har bir ariza tasdiqlanadi yoki sabab bilan rad etiladi."
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={setOpen}
        emptyTitle="Ariza yo'q"
        emptyHint="Bu holatda hech narsa qolmagan."
        toolbar={
          <>
            <Label htmlFor="return-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="return-status"
              className="w-48"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | ReturnStatus)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.length ?? 0} ta ariza</Hint>
          </>
        }
      />

      {open ? (
        <ReturnDetail
          request={open}
          onClose={() => setOpen(null)}
          onChanged={(next) => setOpen(next)}
        />
      ) : null}
    </Page>
  )
}

function ReturnDetail({
  request,
  onClose,
  onChanged,
}: {
  request: StaffReturn
  onClose: () => void
  onChanged: (next: StaffReturn) => void
}) {
  const [decision, setDecision] = React.useState<Decision | null>(null)
  const [reason, setReason] = React.useState("")
  const [note, setNote] = React.useState("")
  // No default, on purpose. The backend refuses a refund that does not say
  // where the goods went, and putting a default here would answer for the
  // operator — which is the one thing that endpoint exists to prevent.
  const [restock, setRestock] = React.useState<boolean | null>(null)

  const act = useAction<void, StaffReturn>({
    run: async () => {
      if (decision === "reject") {
        return api<StaffReturn>(`/staff/returns/${request.id}/reject`, {
          method: "POST",
          json: { reason, note },
        })
      }
      if (decision === "refund") {
        return api<StaffReturn>(`/staff/returns/${request.id}/refund`, {
          method: "POST",
          json: { note, restock },
        })
      }
      return api<StaffReturn>(`/staff/returns/${request.id}/approve`, {
        method: "POST",
        json: { note },
      })
    },
    invalidate: [KEY],
    success: (next) => `Ariza holati: ${RETURN_STATUS[next.status]}`,
    onDone: (next) => {
      setDecision(null)
      setReason("")
      setNote("")
      setRestock(null)
      onChanged(next)
    },
  })

  const canSend =
    decision === "reject"
      ? reason.trim().length > 0
      : decision === "refund"
        ? restock !== null
        : true

  return (
    <>
      <Dialog open onOpenChange={(next) => !next && onClose()}>
        <DialogPanel
          title={`Ariza · ${request.order_code}`}
          description={`${request.customer_name || "Mijoz"} · ${request.customer_phone}`}
          footer={
            <>
              {request.next_statuses.length === 0 ? (
                <Hint>Bu ariza yopilgan.</Hint>
              ) : null}
              {request.next_statuses.includes("approved") ? (
                <Button size="sm" variant="primary" onClick={() => setDecision("approve")}>
                  Tasdiqlash
                </Button>
              ) : null}
              {request.next_statuses.includes("rejected") ? (
                <Button size="sm" variant="quiet" onClick={() => setDecision("reject")}>
                  Rad etish
                </Button>
              ) : null}
              {request.next_statuses.includes("refunded") ? (
                <Button size="sm" variant="primary" onClick={() => setDecision("refund")}>
                  Pulni qaytarish
                </Button>
              ) : null}
            </>
          }
        >
          <dl className="grid grid-cols-[8rem_1fr] gap-y-2 text-[13px]">
            <dt className="text-ink-soft">Holat</dt>
            <dd>
              <Badge tone={RETURN_TONE[request.status]}>{RETURN_STATUS[request.status]}</Badge>
            </dd>
            <dt className="text-ink-soft">Sabab</dt>
            <dd className="text-ink">{request.reason || "—"}</dd>
            <dt className="text-ink-soft">Mijoz izohi</dt>
            <dd className="text-ink">{request.comment || "—"}</dd>
            <dt className="text-ink-soft">Bizning qarorimiz</dt>
            <dd className="text-ink">{request.resolution || "—"}</dd>
            <dt className="text-ink-soft">Qaytarilgan summa</dt>
            <dd className="tabular text-ink">
              {request.refund_amount ? `${money(request.refund_amount)} so'm` : "—"}
            </dd>
            <dt className="text-ink-soft">Qaysi satr</dt>
            <dd className="text-ink">
              {request.order_item_id
                ? `Buyurtmaning bitta satri (#${request.order_item_id})`
                : "Butun buyurtma"}
            </dd>
            <dt className="text-ink-soft">Yuborilgan</dt>
            <dd className="tabular text-ink">{when(request.created_at)}</dd>
          </dl>

          {request.photos.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {request.photos.map((photo) => (
                <img
                  key={photo}
                  src={photo}
                  alt=""
                  className="size-20 rounded border border-line object-cover"
                />
              ))}
            </div>
          ) : null}
        </DialogPanel>
      </Dialog>

      {decision ? (
        <ConfirmDialog
          open
          onOpenChange={(next) => !next && setDecision(null)}
          title={DECISION[decision].title}
          description={`${request.order_code} · ${request.customer_name || request.customer_phone}`}
          confirmLabel={DECISION[decision].confirm}
          {...(DECISION[decision].destructive ? { destructive: true } : {})}
          disabled={!canSend}
          pending={act.isPending}
          onConfirm={() => act.mutate()}
        >
          <div className="space-y-3">
            {decision === "reject" ? (
              <div className="space-y-1">
                <Label htmlFor="reason">Sabab — mijoz shuni o'qiydi</Label>
                <Textarea
                  id="reason"
                  autoFocus
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Kiyilgan holda qaytarilgan"
                />
                <FieldError>{reason.trim() ? null : "Sabab yozilishi shart."}</FieldError>
              </div>
            ) : null}

            {decision === "refund" ? (
              <fieldset className="space-y-1.5">
                <legend className="text-[12px] font-medium text-ink-soft">
                  Tovar javonga qaytadimi?
                </legend>
                <Hint>
                  Ko'zdan kechirilgani javonga qaytadi, yaroqsizi hech kimning hisobiga
                  tushmaydi. Tanlamasdan yuborib bo'lmaydi.
                </Hint>
                {[
                  { value: true, label: "Ha — butun, javonga qaytdi" },
                  { value: false, label: "Yo'q — yaroqsiz, hisobdan chiqdi" },
                ].map((choice) => (
                  <label
                    key={String(choice.value)}
                    className="flex cursor-pointer items-center gap-2 rounded border border-line px-2.5 py-2 text-[13px] hover:bg-line-soft has-checked:border-brand has-checked:bg-brand-soft"
                  >
                    <input
                      type="radio"
                      name="restock"
                      className="brand-brand"
                      checked={restock === choice.value}
                      onChange={() => setRestock(choice.value)}
                    />
                    {choice.label}
                  </label>
                ))}
                <FieldError>{restock === null ? "Tanlov majburiy." : null}</FieldError>
              </fieldset>
            ) : null}

            <div className="space-y-1">
              <Label htmlFor="note">Ichki izoh (ixtiyoriy)</Label>
              <Textarea
                id="note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="TKT-4417, telefonda gaplashildi"
              />
              <Hint>Audit jurnaliga tushadi, mijoz ko'rmaydi.</Hint>
            </div>
          </div>
        </ConfirmDialog>
      ) : null}
    </>
  )
}
