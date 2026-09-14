/**
 * Mahsulotlar — what sold, what is rising, what is falling, what is dead.
 *
 * This report has no time series and does not pretend to: it is four ranked
 * lists, and a rank is read as a list. The one place a picture beats a column
 * of numbers is the top of the revenue list, where the question is not "how
 * much did the palto take" but "is the whole shop one product" — so that one
 * gets bars, and the bars are the same figure a second time, never instead
 * of it.
 *
 * **Dead stock has no arrow anywhere on it.** What is standing still today is
 * a fact; what was standing still a month ago was never written down. The two
 * headline figures for it arrive with a null previous and the tiles draw no
 * comparison — which is why the window it is measured over is a control, and
 * the only honest way to ask "is this getting worse" is to change it.
 */

import { PackageX, TrendingDown, TrendingUp } from "lucide-react"
import { useSearchParams } from "react-router-dom"

import { DataTable, type Column } from "@/components/data-table"
import { Empty, Panel, Segmented } from "@/components/page"
import { date, groups, money } from "@/lib/format"
import { useProductsReport } from "@/lib/queries"
import type { DeadStock, ProductSale, VariantSale } from "@/lib/types"
import {
  Figures,
  Move,
  Note,
  ReportBody,
  Share,
  percentText,
  type ReportProps,
} from "@/pages/report-chrome"

const PRODUCTS: Column<ProductSale>[] = [
  { key: "title", header: "Mahsulot", cell: (row) => row.title },
  { key: "units", header: "Dona", numeric: true, width: "1%", cell: (row) => groups(row.units) },
  {
    key: "revenue",
    header: "Tushum",
    numeric: true,
    width: "1%",
    cell: (row) => <span className="font-semibold">{money(row.revenue)}</span>,
  },
  {
    key: "previous_revenue",
    header: "Oldingi davr",
    numeric: true,
    width: "1%",
    cell: (row) => <span className="text-ink-soft">{money(row.previous_revenue)}</span>,
  },
  {
    key: "delta_revenue",
    header: "O'zgarish",
    numeric: true,
    width: "1%",
    cell: (row) => <Move delta={row.delta_revenue} money />,
  },
]

const VARIANTS: Column<VariantSale>[] = [
  {
    key: "variant",
    header: "Variant",
    cell: (row) => (
      <>
        <div className="truncate font-medium">{row.product_title}</div>
        <div className="text-micro text-ink-faint">{row.variant_label}</div>
      </>
    ),
  },
  { key: "units", header: "Sotilgan", numeric: true, width: "1%", cell: (row) => groups(row.units) },
  {
    key: "stock_left",
    header: "Javonda qolgani",
    numeric: true,
    width: "1%",
    cell: (row) => groups(row.stock_left),
  },
  {
    key: "sell_through_percent",
    header: "Sotilish ulushi",
    numeric: true,
    width: "1%",
    // Null is not nought: it means neither sold nor stocked, and a row of
    // "0%" would put a variant nobody has ever had at the bottom of a league
    // table it never entered.
    cell: (row) =>
      row.sell_through_percent === null ? (
        <span className="text-ink-faint">—</span>
      ) : (
        percentText(row.sell_through_percent)
      ),
  },
  {
    key: "revenue",
    header: "Tushum",
    numeric: true,
    width: "1%",
    cell: (row) => money(row.revenue),
  },
]

const DEAD: Column<DeadStock>[] = [
  {
    key: "variant",
    header: "Variant",
    cell: (row) => (
      <>
        <div className="truncate font-medium">{row.product_title}</div>
        <div className="text-micro text-ink-faint">{row.variant_label}</div>
      </>
    ),
  },
  {
    key: "stock_left",
    header: "Javonda",
    numeric: true,
    width: "1%",
    cell: (row) => groups(row.stock_left),
  },
  {
    key: "unit_price",
    header: "Narxi",
    numeric: true,
    width: "1%",
    cell: (row) => money(row.unit_price),
  },
  {
    key: "shelf_value",
    header: "Javondagi qiymat",
    numeric: true,
    width: "1%",
    cell: (row) => <span className="font-semibold">{money(row.shelf_value)}</span>,
  },
  {
    key: "last_delivered_at",
    header: "Oxirgi sotilgan",
    width: "1%",
    cell: (row) =>
      row.last_delivered_at ? (
        <span className="whitespace-nowrap tabular text-ink-soft">
          {date(row.last_delivered_at)}
        </span>
      ) : (
        <span className="text-ink-faint">hech qachon</span>
      ),
  },
]

const MOVERS: Column<ProductSale>[] = [
  { key: "title", header: "Mahsulot", cell: (row) => row.title },
  {
    key: "units",
    header: "Dona",
    numeric: true,
    width: "1%",
    cell: (row) => (
      <>
        {groups(row.units)}
        <div className="text-micro text-ink-faint">
          oldin {groups(row.previous_units)}
        </div>
      </>
    ),
  },
  {
    key: "delta_revenue",
    header: "Tushum o'zgarishi",
    numeric: true,
    width: "1%",
    cell: (row) => (
      <>
        <Move delta={row.delta_revenue} money />
        <div className="text-micro text-ink-faint">{money(row.revenue)}</div>
      </>
    ),
  },
]

const WINDOWS = [
  { key: "30", label: "30 kun" },
  { key: "45", label: "45 kun" },
  { key: "90", label: "90 kun" },
  { key: "180", label: "180 kun" },
]

export function ProductsReport({ period, onSpan }: ReportProps) {
  const [params, setParams] = useSearchParams()
  const deadAfter = params.get("dead") || "45"

  const report = useProductsReport({ ...period, extra: { dead_after: deadAfter } })
  const data = report.data

  const setWindow = (next: string) => {
    const query = new URLSearchParams(params)
    query.set("dead", next)
    setParams(query, { replace: true })
  }

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="units_sold"
            hints={{
              revenue: "Yetkazilgan buyurtmalarning qatorlari bo'yicha.",
              dead_stock: `Javonda turibdi, ${groups(data.dead_after_days)} kundan beri sotilmagan.`,
              dead_stock_value: "Sotuv narxida — ya'ni qancha pul qimirlamay turibdi.",
            }}
          />

          <Top rows={data.products} />

          <div className="grid items-start gap-(--gap-page) xl:grid-cols-2">
            <DataTable
              namespace="ris"
              searchable={false}
              title="Ko'tarilayotgani"
              rows={data.rising}
              columns={MOVERS}
              rowKey={(row) => row.product_id ?? row.title}
              count={(n) => `${groups(n)} ta mahsulot`}
              empty={{
                icon: TrendingUp,
                title: "Ko'tarilgani yo'q",
                what: "Oldingi davrga nisbatan tushumi oshgan mahsulot yo'q.",
              }}
            />
            <DataTable
              namespace="fal"
              searchable={false}
              title="Tushayotgani"
              rows={data.falling}
              columns={MOVERS}
              rowKey={(row) => row.product_id ?? row.title}
              count={(n) => `${groups(n)} ta mahsulot`}
              empty={{
                icon: TrendingDown,
                title: "Tushgani yo'q",
                what: "Oldingi davrga nisbatan tushumi kamaygan mahsulot yo'q.",
              }}
            />
          </div>

          <DataTable
            namespace="prd"
            title="Mahsulotlar"
            rows={data.products}
            columns={PRODUCTS}
            rowKey={(row) => row.product_id ?? row.title}
            search={(row) => row.title}
            count={(n) => `${groups(n)} ta mahsulot sotilgan`}
            empty={{
              icon: PackageX,
              title: "Sotuv yo'q",
              what: "Bu davrda hech narsa yetkazilmagan.",
            }}
          />

          <DataTable
            namespace="var"
            searchable={false}
            title="Variantlar"
            rows={data.variants}
            columns={VARIANTS}
            rowKey={(row) => row.variant_id}
            count={(n) => `${groups(n)} ta variant sotilgan`}
            empty={{
              icon: PackageX,
              title: "Sotuv yo'q",
              what: "Bu davrda hech narsa yetkazilmagan.",
            }}
          />

          <Note>
            <b className="text-ink">Sotilish ulushi</b> — shu davrda sotilgani,
            sotilgan va javonda qolganining yig'indisiga nisbatan. U oqim bilan
            bugungi holatni ataylab aralashtiradi, chunki javab beradigan savol
            «bulardan ortiqcha olib qo'yganmizmi» — va javonda qolgani shu
            savolning davr ayta olmaydigan yarmi.
          </Note>

          <DataTable
            namespace="ded"
            searchable={false}
            title="Qimirlamayotgan mol"
            rows={data.dead_stock}
            columns={DEAD}
            rowKey={(row) => row.variant_id}
            count={(n) =>
              `${groups(n)} ta variant — ${groups(data.dead_after_days)} kundan beri sotilmagan`
            }
            beforeSearch={
              <Segmented
                label="Qancha vaqtdan beri"
                value={deadAfter}
                onChange={setWindow}
                options={WINDOWS}
              />
            }
            empty={{
              icon: PackageX,
              title: "Hammasi qimirlayapti",
              what: `Javonda ${groups(data.dead_after_days)} kundan beri turgan variant yo'q.`,
            }}
          />
        </>
      ) : null}
    </ReportBody>
  )
}

/**
 * The top of the revenue list, with bars.
 *
 * One hue for every bar and not a ramp: these are product names, which have
 * no order of their own, and painting the biggest one darkest spends the only
 * free channel on information the bar's own length already carries.
 */
function Top({ rows }: { rows: ProductSale[] }) {
  const top = rows.slice(0, 6)
  const most = Math.max(...top.map((one) => one.revenue), 1)

  return (
    <Panel title="Eng ko'p tushum keltirgani" bare>
      {top.length === 0 ? (
        <Empty
          bare
          icon={PackageX}
          title="Hali sotuv yo'q"
          what="Bu davrda yetkazilgan buyurtma bo'lmagan."
        />
      ) : (
        <ol className="divide-y divide-line">
          {top.map((row, index) => (
            <li
              key={row.product_id ?? row.title}
              className="flex items-center gap-3 px-4 py-(--cell-y)"
            >
              <span className="w-4 shrink-0 tabular text-micro text-ink-faint">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-small">{row.title}</div>
                <div className="mt-1">
                  <Share percent={(row.revenue / most) * 100} />
                </div>
              </div>
              <div className="shrink-0 text-end">
                <div className="tabular text-small font-semibold">
                  {money(row.revenue)}
                </div>
                <div className="tabular text-micro text-ink-faint">
                  {groups(row.units)} dona
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  )
}
