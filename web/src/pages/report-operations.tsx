/**
 * Ish — the door, the bench, and what came back.
 *
 * Two things here refuse to render as numbers and both refusals are
 * deliberate.
 *
 * **A courier who knocked on no doors has no success rate.** The server sends
 * null rather than nought, because nought per cent would put somebody who
 * never went out at the bottom of a league table they never entered.
 *
 * **A duration measured over three parcels is not a fact about the shop.** So
 * every duration carries how many it was measured over, and a thin sample
 * says so beside itself rather than being quietly averaged into a number
 * somebody plans around. Median as well as average, because one parcel that
 * sat over a weekend moves an average and does not move a median — and the
 * question ("how long does this normally take") is about the middle one.
 */

import { PackageX, Truck, Undo2 } from "lucide-react"

import { DataTable, type Column } from "@/components/data-table"
import { Empty, Panel } from "@/components/page"
import { age, groups, money } from "@/lib/format"
import { useOperationsReport } from "@/lib/queries"
import type { CourierRow, Duration, ReasonRow } from "@/lib/types"
import {
  Figures,
  Move,
  ReportBody,
  Share,
  percentText,
  type ReportProps,
} from "@/pages/report-chrome"

/** Under this many measurements a duration describes a handful of parcels
 *  rather than the way the shop works, and it says so. */
const THIN = 5

const COURIERS: Column<CourierRow>[] = [
  {
    key: "name",
    header: "Kuryer",
    cell: (row) => (
      <>
        <div className="truncate font-medium">{row.name || "Ismi yozilmagan"}</div>
        <div className="tabular text-micro text-ink-faint">{row.phone}</div>
      </>
    ),
  },
  {
    key: "attempts",
    header: "Eshik qoqqan",
    numeric: true,
    width: "1%",
    cell: (row) => groups(row.attempts),
  },
  {
    key: "delivered",
    header: "Yetkazgan",
    numeric: true,
    width: "1%",
    cell: (row) => <span className="font-semibold">{groups(row.delivered)}</span>,
  },
  {
    key: "failed",
    header: "Chiqmagan",
    numeric: true,
    width: "1%",
    cell: (row) =>
      row.failed ? (
        <span className="text-danger">{groups(row.failed)}</span>
      ) : (
        groups(0)
      ),
  },
  {
    key: "success_percent",
    header: "Ulush",
    numeric: true,
    width: "1%",
    // Null, never nought: they knocked on no doors.
    cell: (row) =>
      row.success_percent === null ? (
        <span className="text-ink-faint">—</span>
      ) : (
        percentText(row.success_percent)
      ),
  },
  {
    key: "cash_collected",
    header: "Olingan naqd",
    numeric: true,
    width: "1%",
    cell: (row) => money(row.cash_collected),
  },
  {
    key: "previous_delivered",
    header: "O'zgarish",
    numeric: true,
    width: "1%",
    cell: (row) => <Move delta={row.delivered - row.previous_delivered} />,
  },
]

export function OperationsReport({ period, onSpan }: ReportProps) {
  const report = useOperationsReport(period)
  const data = report.data

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="deliveries"
            hints={{
              first_attempt: "Birinchi qoqishdayoq eshik ochilgan buyurtmalar.",
              returns_rate: "Yetkazilgan buyurtmalarga nisbatan.",
              cash_collected: "Eshikda kuryer qo'liga tushgan pul.",
            }}
          />

          <DataTable
            namespace="crr"
            searchable={false}
            title="Kuryerlar"
            rows={data.couriers}
            columns={COURIERS}
            rowKey={(row) => row.courier_id}
            count={(n) => `${groups(n)} ta kuryer ishlagan`}
            empty={{
              icon: Truck,
              title: "Kuryer chiqmagan",
              what: "Bu davrda hech kim eshik qoqmagan.",
            }}
          />

          <div className="grid items-start gap-(--gap-page) xl:grid-cols-2">
            <Reasons
              title="Nega yetkazilmagan"
              rows={data.failure_reasons}
              icon={PackageX}
              what="Bu davrda muvaffaqiyatsiz urinish bo'lmagan."
            />
            <Reasons
              title="Nega qaytarilgan"
              rows={data.return_reasons}
              icon={Undo2}
              what="Bu davrda qaytarish ochilmagan."
            />
          </div>

          <Durations rows={data.durations} />
        </>
      ) : null}
    </ReportBody>
  )
}

/**
 * A free-text reason and how often it was given, commonest first.
 *
 * Ranked rather than totalled, because the action is always "deal with the
 * top one". An empty reason keeps its own row: a failure recorded without a
 * reason is a gap in the work, and folding it into the others hides it.
 */
function Reasons({
  title,
  rows,
  icon,
  what,
}: {
  title: string
  rows: ReasonRow[]
  icon: React.ComponentType<{ className?: string }>
  what: string
}) {
  return (
    <Panel title={title} bare>
      {rows.length === 0 ? (
        <Empty bare icon={icon} title="Sabab yo'q" what={what} />
      ) : (
        <ol className="divide-y divide-line">
          {rows.map((row, index) => (
            <li key={`${row.reason}-${index}`} className="px-4 py-(--cell-y)">
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-small">
                  {row.reason || (
                    <span className="text-ink-faint italic">sabab yozilmagan</span>
                  )}
                </span>
                <span className="shrink-0 tabular text-small font-semibold">
                  {groups(row.count)}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-3">
                <Share percent={row.share_percent / 100} />
                <span className="shrink-0 tabular text-micro text-ink-faint">
                  {percentText(row.share_percent)}
                </span>
              </div>
              {row.previous > 0 ? (
                <div className="mt-1 text-micro text-ink-faint">
                  oldingi davrda {groups(row.previous)}
                </div>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}

/** How long a step of the work took — with how many parcels it was measured
 *  over, always, and a warning when that is a handful. */
function Durations({ rows }: { rows: Duration[] }) {
  return (
    <Panel title="Ish qancha vaqt oladi" bare>
      <ul className="divide-y divide-line">
        {rows.map((row) => (
          <li
            key={row.key}
            className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-4 py-(--cell-y)"
          >
            <div className="min-w-0">
              <div className="truncate text-small font-medium">{row.label}</div>
              <div className="text-micro text-ink-faint">
                {row.samples === 0
                  ? "o'lchanmagan"
                  : row.samples < THIN
                    ? `atigi ${groups(row.samples)} ta o'lchov — bu do'kon haqidagi fakt emas`
                    : `${groups(row.samples)} ta o'lchov`}
              </div>
            </div>
            <div className="flex shrink-0 items-baseline gap-6">
              <span className="text-end">
                <span className="caption block">O'rtacha</span>
                <span className="tabular text-small">
                  {row.average_minutes === null ? "—" : age(row.average_minutes)}
                </span>
              </span>
              <span className="text-end">
                <span className="caption block">Mediana</span>
                <span className="tabular text-small font-semibold">
                  {row.median_minutes === null ? "—" : age(row.median_minutes)}
                </span>
              </span>
            </div>
          </li>
        ))}
      </ul>
      <p className="border-t border-line px-4 py-2 text-micro text-ink-faint">
        Mediana — o'rtada turgani. Dam olishda qolib ketgan bitta buyurtma
        o'rtachani suradi, medianani surmaydi, va «odatda qancha vaqt oladi»
        degan savol o'rtada turgani haqida.
      </p>
    </Panel>
  )
}
