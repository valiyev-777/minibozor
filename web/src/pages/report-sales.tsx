/**
 * Savdo — what the shop took, and what happened to the sales it did not make.
 *
 * **Two charts, on purpose, because there are two axes here.** Revenue is
 * counted on the day the goods were *delivered* — that is the day the shop
 * earned it — and orders are counted on the day somebody *placed* them,
 * because a cancellation happened on the day the sale was called off. Put
 * both on one axis and the last day of every period reads as a collapse:
 * orders placed yesterday have not been delivered yet. So each chart says
 * which day it counts under, in a line under its own title.
 *
 * Cancelled and returned ride alongside the placed-order bars rather than
 * inside them. They are a *subset* of those orders, not a third category, and
 * stacking a subset on top of its own total is the commonest way a chart
 * doubles a number.
 */

import { CreditCard } from "lucide-react"

import { DataTable, type Column } from "@/components/data-table"
import { Panel } from "@/components/page"
import { groups, money } from "@/lib/format"
import { useSalesReport } from "@/lib/queries"
import type { SplitRow } from "@/lib/types"
import {
  Figures,
  Move,
  Note,
  ReportBody,
  Trend,
  type ReportProps,
} from "@/pages/report-chrome"

const SPLIT: Column<SplitRow>[] = [
  { key: "label", header: "Nomi", cell: (row) => row.label },
  {
    key: "orders",
    header: "Buyurtma",
    numeric: true,
    cell: (row) => groups(row.orders),
  },
  {
    key: "revenue",
    header: "Tushum",
    numeric: true,
    cell: (row) => money(row.revenue),
  },
  {
    key: "previous_revenue",
    header: "Oldingi davr",
    numeric: true,
    cell: (row) => (
      <span className="text-ink-soft">{money(row.previous_revenue)}</span>
    ),
  },
  {
    key: "delta",
    header: "O'zgarish",
    numeric: true,
    cell: (row) => <Move delta={row.revenue - row.previous_revenue} money />,
  },
]

export function SalesReport({ period, onSpan }: ReportProps) {
  const report = useSalesReport(period)
  const data = report.data

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="revenue"
            hints={{
              revenue: "Yetkazilgan buyurtmalar bo'yicha.",
              orders: "Buyurtma berilgan kun bo'yicha, hamma holatlar.",
              net: "Tushumdan qaytarilgan pul ayrilgan.",
              average_order: "Yetkazilgan buyurtmaga to'g'ri keladi.",
            }}
          />

          {/* The series knows it is short and says so. Nought is the expected
              answer; anything else is orders whose delivery has no time on
              it, so the revenue chart is missing them. */}
          {data.delivered_without_a_time > 0 ? (
            <Note tone="warn">
              {groups(data.delivered_without_a_time)} ta yetkazilgan buyurtmada
              yetkazilgan vaqt yozilmagan — quyidagi tushum grafigi shuncha
              buyurtmani ko'rsatmaydi. Yuqoridagi umumiy tushumda ular bor.
            </Note>
          ) : null}

          <Trend
            title="Tushum"
            note="Yetkazilgan kun bo'yicha — pul shu kuni ishlangan."
            rows={data.buckets}
            unit="money"
            kind="area"
            lines={[{ key: "revenue", label: "Tushum", paint: "lead" }]}
            empty="Bu davrda hech narsa yetkazilmagan."
          />

          <Trend
            title="Buyurtmalar"
            note="Buyurtma berilgan kun bo'yicha. Bekor qilingan va qaytarilgan — o'sha buyurtmalarning ichida, ustiga qo'shilmaydi."
            rows={data.buckets}
            unit="count"
            lines={[
              { key: "orders", label: "Berilgan", paint: "lead" },
              { key: "cancelled", label: "Bekor qilingan", paint: "danger" },
              { key: "returned", label: "Qaytarilgan", paint: "warn" },
            ]}
            empty="Bu davrda buyurtma bo'lmagan."
          />

          <div className="grid items-start gap-(--gap-page) xl:grid-cols-2">
            <DataTable
              namespace="pay"
              searchable={false}
              title="To'lov turi bo'yicha"
              rows={data.by_payment}
              columns={SPLIT}
              rowKey={(row) => row.key}
              count={() => "Yetkazilgan buyurtmalar"}
              empty={{
                icon: CreditCard,
                title: "To'lov yo'q",
                what: "Bu davrda yetkazilgan buyurtma bo'lmagan.",
              }}
            />
            <DataTable
              namespace="dlv"
              searchable={false}
              title="Yetkazish turi bo'yicha"
              rows={data.by_delivery}
              columns={SPLIT}
              rowKey={(row) => row.key}
              count={() => "Yetkazilgan buyurtmalar"}
              empty={{
                icon: CreditCard,
                title: "Yetkazish yo'q",
                what: "Bu davrda yetkazilgan buyurtma bo'lmagan.",
              }}
            />
          </div>

          <Panel title="Nima nimani anglatadi">
            <ul className="space-y-1.5 text-small text-ink-soft">
              <li>
                <b className="text-ink">Tushum</b> — faqat yetkazilgan
                buyurtmalar. Berilgan buyurtma hali va'da, bekor qilingani esa
                hech nima.
              </li>
              <li>
                <b className="text-ink">Sof tushum</b> — tushumdan qaytarilgan
                pul ayrilgan. Holati «qaytarilgan»ga o'tgan buyurtma tushumdan
                allaqachon chiqib ketgan, shuning uchun uning puli ikkinchi
                marta ayrilmaydi.
              </li>
              <li>
                <b className="text-ink">Bekor qilish ulushi</b> — berilgan
                buyurtmalarga nisbatan.
              </li>
            </ul>
          </Panel>
        </>
      ) : null}
    </ReportBody>
  )
}
