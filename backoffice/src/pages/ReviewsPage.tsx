import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Star } from "lucide-react"
import { api } from "@/api/client"
import type { ReviewStatus, StaffReview } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FieldError, Hint, Label, Select, Textarea } from "@/components/ui/field"
import { REVIEW_STATUS, REVIEW_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { when } from "@/lib/utils"

const KEY = ["staff", "reviews"]
const FILTERS: { value: "" | ReviewStatus; label: string }[] = [
  { value: "moderating", label: "Tekshirilmoqda" },
  { value: "published", label: "E'lon qilingan" },
  { value: "rejected", label: "Rad etilgan" },
  { value: "", label: "Hammasi" },
]

export function ReviewsPage() {
  const [status, setStatus] = React.useState<"" | ReviewStatus>("moderating")
  const [rejecting, setRejecting] = React.useState<StaffReview | null>(null)
  const [reason, setReason] = React.useState("")

  const query = useQuery({
    queryKey: [...KEY, status],
    queryFn: () => api<StaffReview[]>("/staff/reviews", { query: { status } }),
  })

  const publish = useAction<StaffReview, StaffReview>({
    run: (review) =>
      api<StaffReview>(`/staff/reviews/${review.id}/publish`, { method: "POST", json: {} }),
    invalidate: [KEY],
    success: "Sharh e'lon qilindi",
  })

  const reject = useAction<StaffReview, StaffReview>({
    run: (review) =>
      api<StaffReview>(`/staff/reviews/${review.id}/reject`, {
        method: "POST",
        json: { reason },
      }),
    invalidate: [KEY],
    success: "Sharh e'lon qilinmadi",
    onDone: () => {
      setRejecting(null)
      setReason("")
    },
  })

  const columns: Column<StaffReview>[] = [
    {
      key: "product",
      header: "Mahsulot",
      sortValue: (row) => row.product_title,
      cell: (row) => <span className="block max-w-56 truncate text-ink">{row.product_title}</span>,
    },
    {
      key: "author",
      header: "Muallif",
      sortValue: (row) => row.author_name,
      cell: (row) => (
        <>
          <span className="block truncate text-ink">{row.author_name || "—"}</span>
          <span className="tabular block text-[12px] text-ink-faint">{row.author_phone}</span>
        </>
      ),
    },
    {
      key: "rating",
      header: "Baho",
      sortValue: (row) => row.rating,
      cell: (row) => (
        <span className="tabular inline-flex items-center gap-1 text-ink">
          {row.rating}
          <Star className="size-3 fill-warn text-warn" />
        </span>
      ),
    },
    {
      key: "text",
      header: "Matn",
      cell: (row) => (
        <div className="max-w-96">
          <p className="line-clamp-2 text-ink-soft">{row.text || "—"}</p>
          {row.photos.length ? (
            <p className="text-[12px] text-ink-faint">{row.photos.length} ta rasm</p>
          ) : null}
        </div>
      ),
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => (
        <Badge tone={REVIEW_TONE[row.status]}>{REVIEW_STATUS[row.status]}</Badge>
      ),
    },
    {
      key: "created",
      header: "Yozilgan",
      sortValue: (row) => row.created_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.created_at)}</span>,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      // Drawn from what the API says is possible, not from a list here.
      cell: (row) => (
        <div className="flex justify-end gap-1.5">
          {row.next_statuses.includes("published") ? (
            <Button
              size="sm"
              variant="primary"
              disabled={publish.isPending}
              onClick={() => publish.mutate(row)}
            >
              E'lon qilish
            </Button>
          ) : null}
          {row.next_statuses.includes("rejected") ? (
            <Button
              size="sm"
              variant="quiet"
              onClick={() => {
                setReason("")
                setRejecting(row)
              }}
            >
              Rad etish
            </Button>
          ) : null}
        </div>
      ),
    },
  ]

  return (
    <Page
      title="Sharhlar"
      hint="E'lon qilinmagan sharh mahsulot reytingiga qo'shilmaydi."
    >
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Sharh yo'q"
        emptyHint="Bu holatda hech narsa qolmagan."
        toolbar={
          <>
            <Label htmlFor="review-status" className="sr-only">
              Holat
            </Label>
            <Select
              id="review-status"
              className="w-48"
              value={status}
              onChange={(event) => setStatus(event.target.value as "" | ReviewStatus)}
            >
              {FILTERS.map((filter) => (
                <option key={filter.value} value={filter.value}>
                  {filter.label}
                </option>
              ))}
            </Select>
            <Hint>{query.data?.length ?? 0} ta sharh</Hint>
          </>
        }
      />

      {rejecting ? (
        <ConfirmDialog
          open
          onOpenChange={(next) => !next && setRejecting(null)}
          title="Sharhni rad etish"
          description={rejecting.product_title}
          confirmLabel="Rad etish"
          destructive
          disabled={!reason.trim()}
          pending={reject.isPending}
          onConfirm={() => reject.mutate(rejecting)}
        >
          <div className="space-y-1">
            <Label htmlFor="review-reason">Sabab — muallif shuni o'qiydi</Label>
            <Textarea
              id="review-reason"
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Boshqa mahsulot haqida"
            />
            <FieldError>{reason.trim() ? null : "Sabab yozilishi shart."}</FieldError>
          </div>
        </ConfirmDialog>
      ) : null}
    </Page>
  )
}
