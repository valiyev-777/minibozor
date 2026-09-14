/**
 * Pul — cash in, cash out, and the one thing on this screen that is not
 * either of them.
 *
 * **`Farq` is not profit and the screen says so out loud.** It is what came in
 * less what went out, and a market run that lands on the 3rd puts a month's
 * buying into one day: the figure swings hard and says nothing about whether
 * the shop made money. Calling it *foyda* would be the single most expensive
 * mislabel available here, because somebody would act on it.
 *
 * **Margin is only real from the day costs started being recorded.** Every
 * line sold before the cost column existed carries none, and no backfill can
 * invent what a shirt sold in March cost. So the margin block shows what it
 * could see — `units_costed` of `units` — and when it could see nothing it
 * says *unknowable*. Never 0%: nought per cent is a claim about the business,
 * and the true statement is that the shop does not know yet.
 */

import { Coins, Store, Wallet } from "lucide-react"

import { DataTable, type Column } from "@/components/data-table"
import { Empty, Panel } from "@/components/page"
import { date, groups, money } from "@/lib/format"
import { useMoneyReport } from "@/lib/queries"
import type { BuyerSpend, MarketSpend, Margin } from "@/lib/types"
import {
  Figures,
  Move,
  Note,
  ReportBody,
  Trend,
  percentText,
  type ReportProps,
} from "@/pages/report-chrome"

const MARKETS: Column<MarketSpend>[] = [
  { key: "place", header: "Bozor", cell: (row) => row.place },
  { key: "runs", header: "Safar", numeric: true, cell: (row) => groups(row.runs) },
  { key: "units", header: "Dona", numeric: true, cell: (row) => groups(row.units) },
  {
    key: "cost",
    header: "Xarajat",
    numeric: true,
    cell: (row) => <span className="font-semibold">{money(row.cost)}</span>,
  },
  {
    key: "previous_cost",
    header: "Oldingi davr",
    numeric: true,
    cell: (row) => <span className="text-ink-soft">{money(row.previous_cost)}</span>,
  },
  {
    key: "delta",
    header: "O'zgarish",
    numeric: true,
    // More spent at the market is neither good nor bad on its own — it is
    // buying, not a loss — so the arrow here is factual and never green.
    cell: (row) => <Move delta={row.cost - row.previous_cost} money goodWhenUp />,
  },
]

const BUYERS: Column<BuyerSpend>[] = [
  { key: "name", header: "Kim olgan", cell: (row) => row.name },
  { key: "runs", header: "Safar", numeric: true, cell: (row) => groups(row.runs) },
  {
    key: "cost",
    header: "Sarflagan",
    numeric: true,
    cell: (row) => <span className="font-semibold">{money(row.cost)}</span>,
  },
  {
    key: "previous_cost",
    header: "Oldingi davr",
    numeric: true,
    cell: (row) => <span className="text-ink-soft">{money(row.previous_cost)}</span>,
  },
]

export function MoneyReport({ period, onSpan }: ReportProps) {
  const report = useMoneyReport(period)
  const data = report.data

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="money_in"
            hints={{
              money_in: "Yetkazilgan buyurtmalardan tushgan pul.",
              difference: "Kirgan pul ayirib chiqqan pul. Bu foyda EMAS.",
              transport: "Bozor safari shaklida yozilgani.",
              gross_margin: "Faqat tannarxi ma'lum bo'lgan qatorlar bo'yicha.",
            }}
          />

          <Note>
            <b className="text-ink">Farq</b> — kirgan pul ayirib chiqqan pul, va
            u foyda emas. Bitta katta bozor safari bir kunda bir oylik xaridni
            ko'rsatadi, shuning uchun bu raqam keskin tebranadi. Foyda —
            quyidagi <b className="text-ink">yalpi foyda</b> bloki, va u faqat
            tannarxi yozilgan kunlarni ko'radi.
          </Note>

          <Trend
            title="Kirgan va chiqqan pul"
            note="Kirgan pul — yetkazilgan kun bo'yicha. Chiqqan pul — bozor safari qabul qilingan kun bo'yicha."
            rows={data.buckets}
            unit="money"
            lines={[
              { key: "money_in", label: "Kirgan", paint: "lead" },
              { key: "money_out", label: "Chiqqan", paint: "quiet" },
            ]}
            empty="Bu davrda pul harakati bo'lmagan."
          />

          <MarginPanel margin={data.margin} />

          {/* Stacked, not side by side: six columns of so'm in half a
              screen scrolls the last one out of sight, and the change
              against the period before is the column somebody came for. */}
          <div className="space-y-(--gap-page)">
            <DataTable
              namespace="mkt"
              searchable={false}
              title="Bozorlar bo'yicha"
              rows={data.by_market}
              columns={MARKETS}
              rowKey={(row) => row.place}
              count={(n) => `${groups(n)} ta bozor`}
              empty={{
                icon: Store,
                title: "Bozor safari yo'q",
                what: "Bu davrda qabul qilingan safar bo'lmagan.",
              }}
            />
            <DataTable
              namespace="byr"
              searchable={false}
              title="Kim olgan"
              rows={data.by_buyer}
              columns={BUYERS}
              rowKey={(row) => row.buyer_id ?? row.name}
              count={(n) => `${groups(n)} ta xodim`}
              empty={{
                icon: Wallet,
                title: "Xarid yo'q",
                what: "Bu davrda hech kim bozorga chiqmagan.",
              }}
            />
          </div>
        </>
      ) : null}
    </ReportBody>
  )
}

/**
 * Gross margin, and how much of the period it could actually see.
 *
 * Three states and only one of them is a percentage.
 *
 * * Nothing costed anywhere — `known_from` is null. The block says so and
 *   shows no number at all. This is the state the shop is in today.
 * * Some of it costed — the percentage is real *for those lines*, and the
 *   coverage bar beside it is what stops it being read as the shop's margin.
 * * All of it costed — the same drawing, with the bar full.
 */
function MarginPanel({ margin }: { margin: Margin }) {
  const unknowable = margin.known_from === null || margin.units_costed === 0

  return (
    <Panel
      title="Yalpi foyda"
      aside={
        margin.known_from ? (
          <span className="text-micro text-ink-soft">
            {date(margin.known_from)} dan beri ma'lum
          </span>
        ) : null
      }
    >
      {unknowable ? (
        <Empty
          bare
          icon={Coins}
          title="Hali hisoblab bo'lmaydi"
          what={
            `Bu davrda sotilgan ${groups(margin.units)} donadan hech birining tannarxi yozilmagan, ` +
            "shuning uchun foyda noma'lum — nol emas, noma'lum. Bozordan olingan mol qabul qilinayotganda " +
            "tannarx yozila boshlagach, shu yerda ko'rinadi."
          }
        />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Cell label="Tushum (tannarxi ma'lum)" value={money(margin.revenue)} />
            <Cell label="Tannarx" value={money(margin.cost)} />
            <Cell
              label="Yalpi foyda"
              value={`${money(margin.margin)} · ${percentText(margin.margin_percent)}`}
            />
          </div>

          {/* The half of the answer the percentage above cannot carry: how
              much of the period it was measured over. */}
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="caption">Qamrov</span>
              <span className="tabular text-small">
                {groups(margin.units_costed)} / {groups(margin.units)} dona ·{" "}
                {percentText(margin.coverage_percent)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-line-soft">
              <div
                className="h-full rounded-full bg-brand"
                style={{
                  width: `${Math.min(100, Math.max(0, margin.coverage_percent / 100))}%`,
                }}
              />
            </div>
            <p className="text-micro text-ink-faint">
              Yuqoridagi foiz — faqat shu qatorlar bo'yicha. Qolgan donalar
              tannarx ustuni paydo bo'lishidan oldin sotilgan va ularni hech
              qanday hisob tiklay olmaydi.
            </p>
          </div>
        </div>
      )}
    </Panel>
  )
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="caption truncate">{label}</div>
      <div className="mt-1 truncate text-figure font-semibold tabular">{value}</div>
    </div>
  )
}
