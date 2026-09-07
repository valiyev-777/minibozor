import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Store } from "lucide-react"
import { api } from "@/api/client"
import type { AdminProduct, AdminProductPage } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FieldError, Hint, Label, Textarea } from "@/components/ui/field"
import { PRODUCT_STATUS, PRODUCT_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { money, when } from "@/lib/utils"

const KEY = ["staff", "catalog", "moderation"]
const PAGE_SIZE = 25

export function ModerationPage() {
  const [page, setPage] = React.useState(1)
  const [rejecting, setRejecting] = React.useState<AdminProduct | null>(null)

  const query = useQuery({
    queryKey: [...KEY, page],
    queryFn: () =>
      api<AdminProductPage>("/staff/catalog/products", {
        query: { status: "moderating", page, page_size: PAGE_SIZE },
      }),
  })

  const publish = useAction<AdminProduct, AdminProduct>({
    run: (product) =>
      api<AdminProduct>(`/staff/catalog/products/${product.id}/status`, {
        method: "POST",
        json: { status: "published" },
      }),
    invalidate: [["staff", "catalog"]],
    success: (product) => `${product.title} — do'konda`,
  })

  const columns: Column<AdminProduct>[] = [
    {
      key: "title",
      header: "Kartochka",
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="max-w-72">
          <span className="block truncate font-medium text-ink">{row.title}</span>
          <span className="block truncate text-[12px] text-ink-faint">
            {row.subtitle || "—"}
          </span>
        </div>
      ),
    },
    {
      key: "sku",
      header: "SKU",
      sortValue: (row) => row.sku,
      cell: (row) => <span className="tabular text-ink-soft">{row.sku}</span>,
    },
    {
      key: "proposer",
      header: "Kimning mahsuloti",
      sortValue: (row) => row.proposed_by?.name ?? "",
      cell: (row) =>
        row.proposed_by ? (
          <span className="inline-flex items-center gap-1.5 text-ink">
            <Store className="size-3.5 shrink-0 text-ink-faint" />
            {row.proposed_by.name}
          </span>
        ) : (
          // A card with no proposer was written by the platform itself and
          // sent to moderation deliberately — not a seller's suggestion.
          <span className="text-ink-faint">Mini Bozor</span>
        ),
    },
    {
      key: "where",
      header: "Turkum",
      sortValue: (row) => row.category_slug,
      cell: (row) => (
        <div className="max-w-40">
          <span className="block truncate text-ink-soft">{row.category_slug}</span>
          <span className="block truncate text-[12px] text-ink-faint">
            {row.brand_slug || "brendsiz"}
          </span>
        </div>
      ),
    },
    {
      key: "content",
      header: "To'ldirilgan",
      cell: (row) => (
        <span className="tabular text-[12px] text-ink-soft">
          {row.image_count} rasm · {row.variant_count} variant
        </span>
      ),
    },
    {
      key: "price",
      header: "Narx",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.price,
      cell: (row) => money(row.price),
    },
    {
      key: "created",
      header: "Yuborilgan",
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
            <Button size="sm" variant="quiet" onClick={() => setRejecting(row)}>
              Rad etish
            </Button>
          ) : null}
        </div>
      ),
    },
  ]

  return (
    <Page
      title="Moderatsiya navbati"
      hint="Sotuvchi o'z mahsulotini o'zi qo'shadi. Bu navbat — tovar omborga kelishini kutayotganlar: ombor sanab qabul qilsa, mahsulot o'zi sotuvga chiqadi. Bu yerdan e'lon qilish — qo'lda tasdiqlash."
    >
      <DataTable
        rows={query.data?.items}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Navbat bo'sh"
        emptyHint="Ombor kutayotgan mahsulotlar shu yerda turadi, eng eskisi birinchi. Partiya qabul qilinsa, mahsulot bu navbatdan o'zi chiqadi."
        server={{
          page: query.data?.page ?? page,
          pageSize: query.data?.page_size ?? PAGE_SIZE,
          total: query.data?.total ?? 0,
          onPageChange: setPage,
        }}
        toolbar={
          <>
            <Badge tone={PRODUCT_TONE.moderating}>{PRODUCT_STATUS.moderating}</Badge>
            <Hint>{query.data?.total ?? 0} ta kartochka kutmoqda</Hint>
          </>
        }
      />

      {rejecting ? (
        <Reject product={rejecting} onClose={() => setRejecting(null)} />
      ) : null}
    </Page>
  )
}

function Reject({ product, onClose }: { product: AdminProduct; onClose: () => void }) {
  const [reason, setReason] = React.useState("")

  const reject = useAction<void, AdminProduct>({
    run: () =>
      api<AdminProduct>(`/staff/catalog/products/${product.id}/status`, {
        method: "POST",
        json: { status: "rejected", reason: reason.trim() },
      }),
    invalidate: [["staff", "catalog"]],
    success: "Kartochka rad etildi",
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Kartochkani rad etish"
      description={`${product.sku} · ${product.title}`}
      confirmLabel="Rad etish"
      destructive
      disabled={!reason.trim()}
      pending={reject.isPending}
      onConfirm={() => reject.mutate()}
    >
      <div className="space-y-1">
        <Label htmlFor="reject-reason">Sabab</Label>
        <Textarea
          id="reject-reason"
          autoFocus
          value={reason}
          placeholder="Rasm sifatsiz · tavsif yo'q · turkum noto'g'ri"
          onChange={(event) => setReason(event.target.value)}
        />
        {reason.trim() ? null : (
          <FieldError>Sababsiz rad etib bo'lmaydi.</FieldError>
        )}
        <Hint>
          Sababni{" "}
          {product.proposed_by ? `${product.proposed_by.name} ` : "kartochkani yozgan odam "}
          o'qiydi va shunga qarab tuzatadi — shuning uchun u majburiy. Yozilgani
          kartochkada qoladi va audit jurnaliga tushadi.
        </Hint>
      </div>
    </ConfirmDialog>
  )
}
