import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Lock, Plus, RefreshCw } from "lucide-react"
import { api } from "@/api/client"
import type { SellerStatement, SettlementPeriod } from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label } from "@/components/ui/field"
import { SETTLEMENT_STATUS, SETTLEMENT_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { day, isoDay, money, when } from "@/lib/utils"

/**
 * Payout runs: their dates, and the one act that cannot be undone.
 *
 * Generating is repeatable and closing is not, so the two are deliberately
 * not the same shape of button. Generate runs inline; closing goes through a
 * dialog that repeats what is about to be frozen and says what freezing
 * means — that the sellers' figures stop moving, and that anything arriving
 * afterwards lands in the next period instead of rewriting this one.
 */

export const PERIODS = ["staff", "payouts", "periods"]

export function Periods({
  onOpenPeriod,
}: {
  onOpenPeriod: (periodId: number) => void
}) {
  const [creating, setCreating] = React.useState(false)
  const [closing, setClosing] = React.useState<SettlementPeriod | null>(null)

  const query = useQuery({
    queryKey: PERIODS,
    queryFn: () => api<SettlementPeriod[]>("/staff/payouts/periods"),
  })

  const generate = useAction<SettlementPeriod, SellerStatement[]>({
    run: (period) =>
      api<SellerStatement[]>(`/staff/payouts/periods/${period.id}/generate`, {
        method: "POST",
      }),
    invalidate: [PERIODS, ["staff", "payouts", "statements"]],
    success: (rows) => `${rows.length} ta hisobot yig'ildi`,
  })

  const columns: Column<SettlementPeriod>[] = [
    {
      key: "label",
      header: "Davr",
      sortValue: (row) => row.starts_on,
      cell: (row) => (
        <>
          <span className="block truncate font-medium text-ink">{row.label}</span>
          <span className="tabular block text-[12px] text-ink-faint">
            {day(row.starts_on)} — {day(row.ends_on)}
          </span>
        </>
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
          {row.closed_at ? (
            <span className="tabular mt-0.5 block text-[12px] text-ink-faint">
              {when(row.closed_at)}
            </span>
          ) : null}
        </>
      ),
    },
    {
      key: "statements",
      header: "Hisobotlar",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.statement_count,
      cell: (row) =>
        row.statement_count || (
          <span className="text-ink-faint">yig'ilmagan</span>
        ),
    },
    {
      key: "payable",
      header: "Jami to'lanadi",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.total_payable,
      cell: (row) => (
        <span className={row.total_payable < 0 ? "font-medium text-danger" : "text-ink"}>
          {money(row.total_payable)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      headClassName: "text-right",
      className: "text-right",
      cell: (row) => (
        <div className="flex justify-end gap-1.5">
          <Button size="sm" onClick={() => onOpenPeriod(row.id)}>
            Hisobotlar
          </Button>
          {row.status === "open" ? (
            <>
              <Button
                size="sm"
                disabled={generate.isPending}
                onClick={() => generate.mutate(row)}
              >
                <RefreshCw />
                Yig'ish
              </Button>
              {/* Closing sits apart from the repeatable action beside it: one
                  can be run again on Friday, the other cannot be run back. */}
              <Button
                size="sm"
                variant="quiet"
                className="ml-2"
                disabled={!row.statement_count}
                title={
                  row.statement_count
                    ? undefined
                    : "Avval hisobotlarni yig'ing — yopish uchun hech narsa yo'q"
                }
                onClick={() => setClosing(row)}
              >
                <Lock />
                Yopish
              </Button>
            </>
          ) : null}
        </div>
      ),
    },
  ]

  return (
    <>
      <DataTable
        rows={query.data}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        emptyTitle="Hali davr yo'q"
        emptyHint="Hisob-kitob davri — to'lov to'plamining sanalari. Haftalik yoki oylik, o'zingiz tanlaysiz."
        toolbar={
          <>
            <Button size="sm" variant="primary" onClick={() => setCreating(true)}>
              <Plus />
              Davr ochish
            </Button>
            <Hint>
              Davrlar kesishmaydi — bitta sotuv ikki to'lovga tushib qolmasligi
              uchun server buni rad etadi.
            </Hint>
          </>
        }
      />

      {creating ? <NewPeriod onClose={() => setCreating(false)} /> : null}
      {closing ? (
        <ClosePeriod period={closing} onClose={() => setClosing(null)} />
      ) : null}
    </>
  )
}

function NewPeriod({ onClose }: { onClose: () => void }) {
  // This month, in local dates. See `isoDay`: going through UTC would offer
  // a range starting the day before, which in Tashkent is every time.
  const today = new Date()
  const first = new Date(today.getFullYear(), today.getMonth(), 1)
  const last = new Date(today.getFullYear(), today.getMonth() + 1, 0)

  const [starts, setStarts] = React.useState(isoDay(first))
  const [ends, setEnds] = React.useState(isoDay(last))
  const [label, setLabel] = React.useState("")

  const create = useAction<void, SettlementPeriod>({
    run: () =>
      api<SettlementPeriod>("/staff/payouts/periods", {
        method: "POST",
        json: { starts_on: starts, ends_on: ends, label: label.trim() },
      }),
    invalidate: [PERIODS],
    success: (row) => `${row.label} ochildi`,
    onDone: onClose,
  })

  const backwards = ends < starts
  const days =
    backwards
      ? 0
      : Math.round(
          (new Date(`${ends}T00:00:00`).getTime() -
            new Date(`${starts}T00:00:00`).getTime()) /
            86_400_000,
        ) + 1

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Hisob-kitob davri ochish"
      description={backwards ? undefined : `${days} kun`}
      confirmLabel="Ochish"
      disabled={backwards || create.isPending}
      pending={create.isPending}
      onConfirm={() => create.mutate()}
    >
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="p-from">Dan</Label>
            <Input
              id="p-from"
              type="date"
              value={starts}
              onChange={(event) => setStarts(event.target.value)}
            />
          </div>
          <div className="flex-1 space-y-1">
            <Label htmlFor="p-to">Gacha</Label>
            <Input
              id="p-to"
              type="date"
              value={ends}
              onChange={(event) => setEnds(event.target.value)}
            />
          </div>
        </div>
        {backwards ? (
          <p className="text-[12px] font-medium text-danger">
            Oxiri boshidan keyin bo'lishi kerak.
          </p>
        ) : null}

        <div className="space-y-1">
          <Label htmlFor="p-label">Nomi</Label>
          <Input
            id="p-label"
            value={label}
            placeholder={`${starts} — ${ends}`}
            onChange={(event) => setLabel(event.target.value)}
          />
          <Hint>Bo'sh qoldirilsa sanalar nom bo'ladi.</Hint>
        </div>

        <p className="rounded border border-line bg-line-soft/60 px-2.5 py-2 text-[12px] text-ink-soft">
          Sanalar tanlanadi, hisoblanmaydi: haftalik ham, oylik ham to'g'ri —
          bu biznes qarori. Davr yopilgunicha xohlaganingizcha qayta yig'ish
          mumkin.
        </p>
      </div>
    </ConfirmDialog>
  )
}

/**
 * The dialog for the one thing on this screen that cannot be walked back.
 *
 * It repeats the sum, names how many sellers are about to be frozen, and says
 * in plain words what closing does to a late refund — because the reason
 * closing exists is that a seller who reads a figure and is shown a different
 * one next week has been told the first figure meant nothing.
 */
function ClosePeriod({
  period,
  onClose,
}: {
  period: SettlementPeriod
  onClose: () => void
}) {
  const close = useAction<void, SettlementPeriod>({
    run: () =>
      api<SettlementPeriod>(`/staff/payouts/periods/${period.id}/close`, {
        method: "POST",
      }),
    invalidate: [PERIODS, ["staff", "payouts", "statements"]],
    success: `${period.label} yopildi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title={`${period.label} — yopish`}
      description={`${day(period.starts_on)} — ${day(period.ends_on)}`}
      confirmLabel="Yopish"
      destructive
      pending={close.isPending}
      onConfirm={() => close.mutate()}
    >
      <div className="space-y-3">
        {/* The figure repeated, because a confirmation that does not name the
            sum is a confirmation of nothing. */}
        <dl className="rounded border border-line bg-line-soft/60 px-2.5 py-2">
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-[12px] text-ink-soft">Sotuvchilar</dt>
            <dd className="tabular text-[13px] font-medium text-ink">
              {period.statement_count}
            </dd>
          </div>
          <div className="mt-1 flex items-baseline justify-between gap-3 border-t border-line pt-1">
            <dt className="text-[12px] text-ink-soft">Jami to'lanadi</dt>
            <dd
              className={`tabular text-[15px] font-semibold ${
                period.total_payable < 0 ? "text-danger" : "text-ink"
              }`}
            >
              {money(period.total_payable)} so'm
            </dd>
          </div>
        </dl>

        <p className="text-[13px] text-ink">
          Yopilgandan keyin bu davrning raqamlari{" "}
          <span className="font-semibold">o'zgarmaydi</span>. Qatorlar qayta
          hisoblanmaydi va ularga tayangan buyurtmalar boshqa davrga tushmaydi.
        </p>
        <p className="text-[12px] text-ink-soft">
          Kech kelgan qaytarish — masalan bir oylik buyurtma bo'yicha — bu
          hisobotni qayta yozmaydi, keyingi davrga tushadi. Shu bilan sotuvchi
          bir marta o'qigan raqam keyin boshqa bo'lib chiqmaydi.
        </p>
        <p className="text-[12px] text-ink-soft">
          Yopish — to'lash emas. Pul har bir sotuvchiga alohida, o'z havolasi
          bilan chiqadi.
        </p>
      </div>
    </ConfirmDialog>
  )
}
