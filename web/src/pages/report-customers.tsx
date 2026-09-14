/**
 * Mijozlar — who is buying, who came back, and who has stopped.
 *
 * The lapsed list is the only thing on any of these six screens that is a
 * **list of things to do**: a name, a telephone number, what they used to
 * spend, and how long it has been. Everything else here describes the shop;
 * this one asks somebody to pick up the phone, so it gets the room and the
 * number is a `tel:` link rather than text to copy out by hand.
 *
 * How long counts as lapsed is the owner's judgement and not ours, so it is a
 * control — in the address bar with the period, because "the customers who
 * have not been back in three months" is a link somebody sends.
 */

import { PhoneOutgoing, Users } from "lucide-react"
import { useSearchParams } from "react-router-dom"

import { DataTable, type Column } from "@/components/data-table"
import { Segmented } from "@/components/page"
import { date, groups, money } from "@/lib/format"
import { useCustomersReport } from "@/lib/queries"
import type { CustomerRank } from "@/lib/types"
import { Figures, ReportBody, Trend, type ReportProps } from "@/pages/report-chrome"

/** A customer with no name is a real row, not a broken one — they signed up
 *  with a telephone number and never typed anything else. */
function called(row: CustomerRank): string {
  return row.name.trim() || "Ismi yozilmagan"
}

function Phone({ phone }: { phone: string }) {
  if (!phone) return <span className="text-ink-faint">—</span>
  return (
    <a
      href={`tel:${phone}`}
      className="tabular whitespace-nowrap text-brand-deep hover:underline"
    >
      {phone}
    </a>
  )
}

const TOP: Column<CustomerRank>[] = [
  {
    key: "name",
    header: "Mijoz",
    cell: (row) => (
      <>
        <div className="truncate font-medium">{called(row)}</div>
        <div className="text-micro text-ink-faint">
          oxirgi buyurtma: {row.last_order_at ? date(row.last_order_at) : "—"}
        </div>
      </>
    ),
  },
  { key: "phone", header: "Telefon", width: "1%", cell: (row) => <Phone phone={row.phone} /> },
  {
    key: "orders",
    header: "Buyurtma",
    numeric: true,
    width: "1%",
    cell: (row) => groups(row.orders),
  },
  {
    key: "spent",
    header: "Jami sarflagan",
    numeric: true,
    width: "1%",
    cell: (row) => <span className="font-semibold">{money(row.spent)}</span>,
  },
]

const LAPSED: Column<CustomerRank>[] = [
  ...TOP,
  {
    key: "days_since",
    header: "Ko'rinmagani",
    numeric: true,
    width: "1%",
    cell: (row) => (
      <span className="font-semibold text-warn-ink">{groups(row.days_since)} kun</span>
    ),
  },
]

const WINDOWS = [
  { key: "30", label: "30 kun" },
  { key: "60", label: "60 kun" },
  { key: "90", label: "90 kun" },
  { key: "180", label: "180 kun" },
]

export function CustomersReport({ period, onSpan }: ReportProps) {
  const [params, setParams] = useSearchParams()
  const lapsedAfter = params.get("lapsed") || "60"

  const report = useCustomersReport({
    ...period,
    extra: { lapsed_after: lapsedAfter },
  })
  const data = report.data

  const setWindow = (next: string) => {
    const query = new URLSearchParams(params)
    query.set("lapsed", next)
    setParams(query, { replace: true })
  }

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="buyers"
            hints={{
              buyers: "Shu davrda kamida bitta buyurtma bergan odamlar.",
              repeat_rate:
                "Shu davrda buyurtma berganlarning nechtasi ilgari ham olgan.",
              orders_per_customer: "Bitta xaridorga to'g'ri keladigan buyurtma.",
              signups: "Ro'yxatdan o'tgan, hali olmagan bo'lishi mumkin.",
            }}
          />

          <Trend
            title="Ro'yxatdan o'tganlar"
            note="Ro'yxatdan o'tgan kun bo'yicha."
            rows={data.buckets}
            unit="count"
            lines={[{ key: "signups", label: "Ro'yxatdan o'tgan", paint: "lead" }]}
            empty="Bu davrda yangi ro'yxatdan o'tgan yo'q."
          />

          <Trend
            title="Buyurtmalar: yangi va qaytib kelgan"
            note="Buyurtma berilgan kun bo'yicha. Ikki ustun qo'shilib o'sha kunning hamma buyurtmasini beradi."
            rows={data.buckets}
            unit="count"
            lines={[
              {
                key: "repeat_orders",
                label: "Qaytib kelgan",
                paint: "lead",
                stack: true,
              },
              {
                key: "first_orders",
                label: "Birinchi marta",
                paint: "quiet",
                stack: true,
              },
            ]}
            empty="Bu davrda buyurtma bo'lmagan."
          />

          <DataTable
            namespace="top"
            searchable={false}
            title="Eng ko'p sarflaganlar"
            rows={data.top_customers}
            columns={TOP}
            rowKey={(row) => row.user_id}
            count={(n) => `${groups(n)} ta mijoz`}
            empty={{
              icon: Users,
              title: "Mijoz yo'q",
              what: "Hali hech kim buyurtma bermagan.",
            }}
          />

          <DataTable
            namespace="lap"
            title="Qo'ng'iroq qilinadiganlar"
            rows={data.lapsed}
            columns={LAPSED}
            rowKey={(row) => row.user_id}
            search={(row) => `${called(row)} ${row.phone}`}
            count={(n) =>
              `${groups(n)} ta mijoz — ilgari olgan, ${groups(data.lapsed_after_days)} kundan beri yo'q`
            }
            beforeSearch={
              <Segmented
                label="Qancha vaqtdan beri"
                value={lapsedAfter}
                onChange={setWindow}
                options={WINDOWS}
              />
            }
            empty={{
              icon: PhoneOutgoing,
              title: "Yo'qolgan mijoz yo'q",
              what: `Ilgari olib, ${groups(data.lapsed_after_days)} kundan beri ko'rinmagan mijoz yo'q. Muddatni o'zgartirib ko'ring.`,
            }}
          />
        </>
      ) : null}
    </ReportBody>
  )
}
