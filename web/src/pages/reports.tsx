/**
 * Hisobotlar — six reports, one period, one address.
 *
 * ---------------------------------------------------------------- what was
 *
 * This route was a single paged table of raw `stock_movements`: "3 × Qora/42,
 * A-01-03 → YIGIM, Aziz, 14:22", thousands of rows deep, no date filter, no
 * totals, and not one so'm anywhere. It answered "where did this pair of
 * shoes go", which is a warehouse supervisor's question, and it was filed
 * under the menu item an owner opens to ask whether the shop is making money.
 * The owner's own words were *junlar va chalkashlik* — fluff and confusion.
 *
 * The table is gone rather than renamed. The owner's second instruction was
 * plain: the panel does not watch movements. `GET /warehouse/stock/movements`
 * still exists and now has no caller here; a count that looks wrong is
 * settled at the shelf map and by opening a stocktake.
 *
 * ------------------------------------------------------- one screen, six tabs
 *
 * Six sibling routes were the other option and this is not one. The deciding
 * argument is the period: it is **one control, above everything it scopes**,
 * and six routes means six copies of it — moving between them through the
 * rail would silently change the slice under somebody who had just set it.
 * Tabs keep one control over one slice, keep the drawer two items long
 * instead of eight, and cost one render rather than six route files.
 *
 * Everything that decides what is on screen is in the query string:
 * `?report=pul&from=2026-08-01&to=2026-08-31&bucket=week`. A report somebody
 * is looking at is a link they can send — which is the same rule the list
 * screens already follow for their page and their filters, and the reason
 * anybody can be shown a number rather than told where to click.
 *
 * **Only the open tab fetches.** Six endpoints on one screen is six queries
 * per visit for five answers nobody asked for.
 */

import {
  Boxes,
  Coins,
  Package,
  TrendingUp,
  Truck,
  Users,
  type LucideIcon,
} from "lucide-react"
import { useCallback, useState } from "react"
import { useSearchParams } from "react-router-dom"

import { PageHeader, Panel } from "@/components/page"
import { cn } from "@/lib/cn"
import type { ReportPeriod } from "@/lib/types"
import { CustomersReport } from "@/pages/report-customers"
import { MoneyReport } from "@/pages/report-money"
import { OperationsReport } from "@/pages/report-operations"
import { ProductsReport } from "@/pages/report-products"
import { SalesReport } from "@/pages/report-sales"
import { StockReport } from "@/pages/report-stock"
import {
  PeriodControls,
  usePeriod,
  type ReportProps,
} from "@/pages/report-chrome"

type Tab = {
  key: string
  label: string
  /** The line under the page title while this tab is open — what question
   *  this report answers, in the words somebody would ask it in. */
  asks: string
  icon: LucideIcon
  body: (props: ReportProps) => React.ReactNode
}

const TABS: Tab[] = [
  {
    key: "savdo",
    label: "Savdo",
    asks: "Qancha sotdik, va oldingi davrga nisbatan qanday",
    icon: TrendingUp,
    body: (props) => <SalesReport {...props} />,
  },
  {
    key: "pul",
    label: "Pul",
    asks: "Qancha pul kirdi, qancha chiqdi, va foyda qayerda",
    icon: Coins,
    body: (props) => <MoneyReport {...props} />,
  },
  {
    key: "mijozlar",
    label: "Mijozlar",
    asks: "Kim olyapti, kim qaytib kelyapti, kim yo'qolgan",
    icon: Users,
    body: (props) => <CustomersReport {...props} />,
  },
  {
    key: "mahsulotlar",
    label: "Mahsulotlar",
    asks: "Nima ketyapti, nima ko'tarilyapti, nima qimirlamayapti",
    icon: Package,
    body: (props) => <ProductsReport {...props} />,
  },
  {
    key: "ombor",
    label: "Ombor",
    asks: "Omborda nima turibdi va u qancha turadi",
    icon: Boxes,
    body: (props) => <StockReport {...props} />,
  },
  {
    key: "ish",
    label: "Ish",
    asks: "Eshik, stol va qaytib kelgani — ish qanday ketyapti",
    icon: Truck,
    body: (props) => <OperationsReport {...props} />,
  },
]

export function ReportsPage() {
  const [params, setParams] = useSearchParams()
  const period = usePeriod()

  // The period the *server* chose to compare against. It travels back up from
  // whichever report is open, because the sentence beside the control names a
  // stretch of days this screen must not guess at.
  const [span, setSpan] = useState<ReportPeriod | undefined>(undefined)
  const onSpan = useCallback((next: ReportPeriod | undefined) => setSpan(next), [])

  const wanted = params.get("report")
  const tab = TABS.find((one) => one.key === wanted) ?? TABS[0]

  const open = (key: string) => {
    const next = new URLSearchParams(params)
    if (key === TABS[0].key) next.delete("report")
    else next.set("report", key)
    setParams(next, { replace: true })
  }

  return (
    <div className="space-y-(--gap-page)">
      <PageHeader title="Hisobotlar" subtitle={tab.asks}>
        <PeriodControls period={period} span={span} />
      </PageHeader>

      {/* One row of tabs, scrollable rather than wrapping: six chips that
          reflow to two lines move the content under them every time the
          window changes width. */}
      <Panel bare>
        <div
          role="tablist"
          aria-label="Hisobotlar"
          className="flex overflow-x-auto"
        >
          {TABS.map((one) => (
            <button
              key={one.key}
              type="button"
              role="tab"
              aria-selected={one.key === tab.key}
              onClick={() => open(one.key)}
              className={cn(
                "inline-flex h-control-lg shrink-0 items-center gap-2 border-b-2 px-4 text-small transition-colors",
                one.key === tab.key
                  ? "border-brand font-medium text-ink"
                  : "border-transparent text-ink-soft hover:bg-line-soft hover:text-ink",
              )}
            >
              <one.icon
                className={cn(
                  "size-4",
                  one.key === tab.key ? "text-brand" : "text-ink-faint",
                )}
              />
              {one.label}
            </button>
          ))}
        </div>
      </Panel>

      {/* Keyed, so switching reports drops the previous one's panels rather
          than reconciling a sales table into a courier table. */}
      <div key={tab.key}>{tab.body({ period, onSpan })}</div>
    </div>
  )
}
