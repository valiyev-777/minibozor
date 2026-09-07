import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { ArrowRight, Info } from "lucide-react"
import { api } from "@/api/client"
import type { Statement } from "@/api/types"
import { Empty, Failed, Loading, Panel, Row } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint } from "@/components/ui/field"
import { SETTLEMENT_STATUS, SETTLEMENT_TONE } from "@/lib/labels"
import { day, money, when } from "@/lib/utils"

export const STATEMENTS = ["statements"]

/**
 * What I have been paid, and what is still being counted.
 *
 * The backend scopes these to the caller — for a seller these are not a
 * filtered view of everybody's statements, they are the only rows that
 * exist — so there is nothing to choose here and no seller column.
 *
 * `payable` is what a period comes to and it can be negative: a period of
 * refunds and storage against no sales means the seller owes the platform.
 * Shown in red and named rather than clamped to zero, because a debt hidden
 * is a debt that turns up as a surprise deduction next month.
 */
export function StatementsPage() {
  const query = useQuery({
    queryKey: STATEMENTS,
    queryFn: () => api<Statement[]>("/staff/payouts/statements"),
  })

  const rows = query.data ?? []
  const paid = rows.filter((row) => row.status === "paid")
  const owed = rows
    .filter((row) => row.status === "closed")
    .reduce((sum, row) => sum + row.payable, 0)

  return (
    <>
      <PageHead
        title="Hisobotlar"
        hint="Har bir davr uchun alohida hisob: sotilgani, ushlab qolinganlari va qo'lga tegadigan summa."
      />

      {rows.length ? (
        <div className="mb-5 grid gap-3 sm:grid-cols-2">
          <Panel className="px-5 py-4">
            <p className="text-[13px] text-ink-soft">To'lovni kutayotgan</p>
            <p
              className={`figure mt-0.5 ${owed < 0 ? "text-danger" : "text-brand-ink"}`}
            >
              {money(owed)}
            </p>
            <p className="mt-0.5 text-[13px] text-ink-faint">
              Tasdiqlangan, hali to'lanmagan davrlar
            </p>
          </Panel>
          <Panel className="px-5 py-4">
            <p className="text-[13px] text-ink-soft">To'langan, jami</p>
            <p className="figure mt-0.5 text-good">
              {money(paid.reduce((sum, row) => sum + row.payable, 0))}
            </p>
            <p className="mt-0.5 text-[13px] text-ink-faint">
              {paid.length} ta davr bo'yicha
            </p>
          </Panel>
        </div>
      ) : null}

      <Panel title={`${rows.length} ta davr`}>
        {query.isPending ? <Loading /> : null}
        {query.error ? (
          <Failed error={query.error} onRetry={() => void query.refetch()} />
        ) : null}
        {!query.isPending && !query.error && rows.length === 0 ? (
          <Empty
            title="Hali hisobot yo'q"
            hint="Hisobot davr yopilganda tuziladi. Birinchi sotuvdan keyin ham darhol chiqmaydi — administrator davrni yig'ib, tasdiqlaydi."
          />
        ) : null}

        {rows.map((row) => (
          <Row key={row.id}>
            <div className="min-w-[10rem] flex-1">
              <p className="text-[16px] font-medium text-ink">{row.period_label}</p>
              <p className="tabular text-[13px] text-ink-faint">
                {day(row.starts_on)} — {day(row.ends_on)}
              </p>
            </div>

            <Badge tone={SETTLEMENT_TONE[row.status]}>
              {SETTLEMENT_STATUS[row.status]}
            </Badge>

            <div className="w-32 text-right">
              <p className="text-[12px] text-ink-faint">Sotilgan</p>
              <p className="tabular text-[15px] text-ink-soft">
                {money(row.gross_sales)}
              </p>
            </div>

            <div className="w-36 text-right">
              <p className="text-[12px] text-ink-faint">Qo'lga tegadi</p>
              <p
                className={`tabular text-[20px] font-semibold ${
                  row.payable < 0 ? "text-danger" : "text-ink"
                }`}
              >
                {money(row.payable)}
              </p>
              {row.paid_at ? (
                <p className="tabular text-[12px] text-good">{when(row.paid_at)}</p>
              ) : null}
            </div>

            <Button asChild>
              <Link to={`/statements/${row.id}`}>
                Tafsilot
                <ArrowRight />
              </Link>
            </Button>
          </Row>
        ))}

        {rows.some((row) => row.status === "open") ? (
          <p className="flex items-start gap-2 border-t border-line-soft px-5 py-3 text-[13px] text-ink-soft">
            <Info className="mt-0.5 size-4 shrink-0 text-ink-faint" />
            <span>
              «Ochiq» davrning raqamlari hali qayta hisoblanishi mumkin.
              Tasdiqlangandan keyin ular o'zgarmaydi — keyin kelgan
              qaytarish keyingi davrga tushadi.
            </span>
          </p>
        ) : null}
      </Panel>

      <Hint className="mt-4">
        Komissiya va haqlar sotilgan kundagi stavkalar bo'yicha hisoblanadi.
        Keyin stavka o'zgarsa, o'tgan hisobot o'zgarmaydi.
      </Hint>
    </>
  )
}
