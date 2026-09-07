import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { SellerStatement, SettlementPeriod, SettlementStatus } from "@/api/types"
import { DataTable, type Column } from "@/components/DataTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Label, Select } from "@/components/ui/field"
import { SETTLEMENT_STATUS, SETTLEMENT_TONE } from "@/lib/labels"
import { day, money, when } from "@/lib/utils"

export const STATEMENTS = ["staff", "payouts", "statements"]

const STATES: ("" | SettlementStatus)[] = ["", "open", "closed", "paid"]

/**
 * Every seller's account, filtered by run and by state.
 *
 * The payable column is the only one anybody scans, so it is the only one
 * given weight: right-aligned, tabular, and coloured when it is negative — a
 * period of refunds and storage against no sales means the seller owes us,
 * and a debt shown in the same ink as a credit is a debt nobody notices.
 */
export function Statements({
  periodId,
  onPeriodChange,
  onOpen,
}: {
  periodId: number | null
  onPeriodChange: (periodId: number | null) => void
  onOpen: (statementId: number) => void
}) {
  const [state, setState] = React.useState<"" | SettlementStatus>("")

  const periods = useQuery({
    queryKey: ["staff", "payouts", "periods"],
    queryFn: () => api<SettlementPeriod[]>("/staff/payouts/periods"),
  })

  const query = useQuery({
    queryKey: [...STATEMENTS, periodId, state],
    queryFn: () =>
      api<SellerStatement[]>("/staff/payouts/statements", {
        query: {
          ...(periodId ? { period_id: periodId } : {}),
          ...(state ? { status: state } : {}),
        },
      }),
  })

  const rows = query.data ?? []
  const total = rows.reduce((sum, row) => sum + row.payable, 0)

  const columns: Column<SellerStatement>[] = [
    {
      key: "seller",
      header: "Sotuvchi",
      sortValue: (row) => row.seller_name,
      cell: (row) => (
        <span className="block truncate font-medium text-ink">{row.seller_name}</span>
      ),
    },
    {
      key: "period",
      header: "Davr",
      sortValue: (row) => row.starts_on,
      cell: (row) => (
        <>
          <span className="block truncate text-ink-soft">{row.period_label}</span>
          <span className="tabular block text-[12px] text-ink-faint">
            {day(row.starts_on)} — {day(row.ends_on)}
          </span>
        </>
      ),
    },
    {
      key: "gross",
      header: "Sotilgan",
      headClassName: "text-right",
      className: "text-right tabular text-ink-soft",
      sortValue: (row) => row.gross_sales,
      cell: (row) => money(row.gross_sales),
    },
    {
      key: "deductions",
      header: "Chegirmalar",
      headClassName: "text-right",
      className: "text-right tabular text-ink-soft",
      sortValue: (row) =>
        row.commission + row.fulfilment + row.refunds + row.storage,
      cell: (row) => (
        <span title="Komissiya + yig'ish + qaytarishlar + saqlash">
          {money(row.commission + row.fulfilment + row.refunds + row.storage)}
        </span>
      ),
    },
    {
      key: "payable",
      header: "To'lanadi",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.payable,
      cell: (row) => (
        <span
          className={
            row.payable < 0 ? "font-semibold text-danger" : "font-medium text-ink"
          }
        >
          {money(row.payable)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Holat",
      sortValue: (row) => row.status,
      cell: (row) => (
        <>
          <Badge tone={SETTLEMENT_TONE[row.status]}>
            {SETTLEMENT_STATUS[row.status]}
          </Badge>
          {row.paid_at ? (
            <span className="tabular mt-0.5 block text-[12px] text-ink-faint">
              {when(row.paid_at)}
              {row.payment_reference ? ` · ${row.payment_reference}` : ""}
            </span>
          ) : null}
        </>
      ),
    },
    {
      key: "lines",
      header: "Qatorlar",
      headClassName: "text-right",
      className: "text-right tabular text-ink-faint",
      sortValue: (row) => row.line_count,
      cell: (row) => row.line_count,
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <Button size="sm" onClick={() => onOpen(row.id)}>
          Tafsilot
        </Button>
      ),
    },
  ]

  return (
    <DataTable
      rows={query.data}
      columns={columns}
      rowKey={(row) => row.id}
      loading={query.isPending}
      error={query.error}
      onRetry={() => void query.refetch()}
      onRowClick={(row) => onOpen(row.id)}
      emptyTitle="Hisobot yo'q"
      emptyHint="Davrni ochib «Yig'ish» bosilganda har bir sotuvchi uchun hisobot tuziladi."
      clientPageSize={40}
      toolbar={
        <>
          <div className="flex items-center gap-1.5">
            <Label htmlFor="s-period">Davr</Label>
            <Select
              id="s-period"
              className="w-56"
              value={periodId ?? ""}
              onChange={(event) =>
                onPeriodChange(event.target.value ? Number(event.target.value) : null)
              }
            >
              <option value="">Hammasi</option>
              {(periods.data ?? []).map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex items-center gap-1.5">
            <Label htmlFor="s-state">Holat</Label>
            <Select
              id="s-state"
              className="w-36"
              value={state}
              onChange={(event) => setState(event.target.value as "" | SettlementStatus)}
            >
              {STATES.map((value) => (
                <option key={value} value={value}>
                  {value ? SETTLEMENT_STATUS[value] : "Hammasi"}
                </option>
              ))}
            </Select>
          </div>
          <Hint>
            {rows.length} ta hisobot · jami{" "}
            <span className="tabular font-medium text-ink">{money(total)}</span> so'm
          </Hint>
        </>
      }
    />
  )
}
