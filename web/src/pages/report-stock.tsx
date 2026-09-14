/**
 * Ombor — what is in the building, where it is standing, and how right that
 * is.
 *
 * **Almost nothing on this screen has an arrow, and that is the honest
 * drawing.** Stock value, units, full cells, empty cells: the shop knows what
 * is on the shelf now and keeps no record of what was on it a month ago, so
 * the server sends these with a null previous and this screen draws no
 * comparison. An arrow here would be an arrow against a nought somebody
 * invented. Only the two figures that are genuinely *events over the period*
 * — what was written off and what went to the damaged corner — carry one.
 *
 * **Accuracy is absent, not nought, when nobody counted.** A hundred per cent
 * over nought lines is the most misleading number available here and nought
 * per cent is a slander on a warehouse that simply was not counted this
 * month, so the panel says nobody counted and shows no figure.
 */

import { ClipboardCheck } from "lucide-react"

import { Empty, Panel } from "@/components/page"
import { groups, money } from "@/lib/format"
import { useStockReport } from "@/lib/queries"
import type { StockKind, Stocktake } from "@/lib/types"
import {
  Figures,
  Note,
  ReportBody,
  Share,
  percentText,
  type ReportProps,
} from "@/pages/report-chrome"

export function StockReport({ period, onSpan }: ReportProps) {
  const report = useStockReport(period)
  const data = report.data

  return (
    <ReportBody query={report} span={data?.period} onSpan={onSpan}>
      {data ? (
        <>
          <Figures
            figures={data.headlines}
            lead="stock_value"
            hints={{
              stock_value: "Sotuv narxida, hozirgi holat.",
              written_off: "Shu davrda hisobdan chiqarilgan dona.",
              damaged_units: "Shu davrda brakka o'tgan dona.",
              stocktake_accuracy: "Yopilgan sanashlar bo'yicha.",
            }}
          />

          <Note>
            Bu yerdagi qiymat va katak raqamlari — <b className="text-ink">bugungi
            holat</b>. Bir oy oldin javonda nima turganini do'kon hech qayerda
            yozmaydi, shuning uchun ular oldingi davr bilan taqqoslanmaydi va
            o'q chizilmaydi. Faqat «hisobdan chiqarilgan» va «brakka o'tgan» —
            davr ichida bo'lgan voqealar, ular taqqoslanadi.
          </Note>

          <div className="grid items-start gap-(--gap-page) xl:grid-cols-2">
            <Kinds rows={data.by_kind} />
            <Cells
              cells={data.cells}
              full={data.cells_full}
              empty={data.cells_empty}
            />
          </div>

          <StocktakePanel
            take={data.stocktake}
            before={data.previous_stocktake}
          />
        </>
      ) : null}
    </ReportBody>
  )
}

/**
 * Where the stock is standing, and what is standing there.
 *
 * The genuinely valuable split: "the shop holds 81 million so'm of stock" is
 * a number nobody can act on, and "eleven million of it is in the damaged
 * corner" is a morning's work. One hue for every bar — these are places, not
 * a scale.
 */
function Kinds({ rows }: { rows: StockKind[] }) {
  const most = Math.max(...rows.map((one) => one.value), 1)

  return (
    <Panel title="Qayerda turibdi" bare>
      {rows.length === 0 ? (
        <Empty
          bare
          icon={ClipboardCheck}
          title="Ombor bo'sh"
          what="Hech qayerda hech narsa turmagan."
        />
      ) : (
        <ul className="divide-y divide-line">
          {rows.map((row) => (
            <li key={row.kind} className="px-4 py-(--cell-y)">
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-small font-medium">{row.label}</span>
                <span className="tabular text-small font-semibold">
                  {money(row.value)}
                </span>
              </div>
              <div className="mt-1.5">
                <Share percent={(row.value / most) * 100} />
              </div>
              <div className="mt-1 text-micro text-ink-faint">
                {groups(row.units)} dona · {groups(row.variants)} variant
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

/** How much of the room is in use. A ratio against a limit is a meter, not a
 *  pie of two slices. */
function Cells({
  cells,
  full,
  empty,
}: {
  cells: number
  full: number
  empty: number
}) {
  const used = cells - empty
  const percent = cells ? (used / cells) * 100 : 0

  return (
    <Panel title="Kataklar">
      <div className="space-y-4">
        <div>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="figure">{groups(used)}</span>
            <span className="text-small text-ink-soft">
              {groups(cells)} katakdan band
            </span>
          </div>
          <div className="mt-2">
            <Share percent={percent} />
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 border-t border-line pt-3">
          <Cell label="To'lgan" value={groups(full)} />
          <Cell label="Band" value={groups(used)} />
          <Cell label="Bo'sh" value={groups(empty)} />
        </div>
        <p className="text-micro text-ink-faint">
          «To'lgan» — sig'imining 80% va undan ko'pi band bo'lgan kataklar.
          Boshqaruv ekranidagi raqam ham shu.
        </p>
      </div>
    </Panel>
  )
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="caption truncate">{label}</div>
      <div className="mt-0.5 truncate tabular text-body font-semibold">{value}</div>
    </div>
  )
}

/**
 * How far the shelf had drifted from the ledger — the only measure there is
 * of whether the room and the books agree.
 *
 * Absent rather than nought when nobody counted, and the comparison against
 * the period before is drawn **only** when that period was counted too.
 */
function StocktakePanel({ take, before }: { take: Stocktake; before: Stocktake }) {
  if (take.accuracy_percent === null) {
    return (
      <Panel title="Sanash">
        <Empty
          bare
          icon={ClipboardCheck}
          title="Bu davrda sanash bo'lmagan"
          what={
            "Yopilgan sanash bo'lmagani uchun aniqlik ko'rsatilmaydi — 0% ham, 100% ham " +
            "noto'g'ri bo'lardi. Ombor ekranidan sanash ochilgach, shu yerda ko'rinadi."
          }
        />
      </Panel>
    )
  }

  return (
    <Panel
      title="Sanash"
      aside={
        before.accuracy_percent !== null ? (
          <span className="text-micro text-ink-soft">
            oldingi davr: {percentText(before.accuracy_percent)}
          </span>
        ) : (
          <span className="text-micro text-ink-faint">
            oldingi davrda sanash bo'lmagan
          </span>
        )
      }
    >
      <div className="space-y-4">
        <div>
          <span className="caption">Aniqlik</span>
          <div className="figure">{percentText(take.accuracy_percent)}</div>
          <div className="mt-2">
            <Share percent={take.accuracy_percent / 100} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 border-t border-line pt-3 sm:grid-cols-4">
          <Cell label="Sanash" value={groups(take.counts)} />
          <Cell label="Qator" value={groups(take.lines)} />
          <Cell label="Farq chiqqani" value={groups(take.lines_wrong)} />
          <Cell label="Farq (dona)" value={groups(take.miscounted_units)} />
        </div>
        <p className="text-micro text-ink-faint">
          Kutilgan {groups(take.expected_units)} dona, sanalgan{" "}
          {groups(take.counted_units)} dona. Aniqlik — kutilgandan umumiy farq
          ayrilib, kutilganiga bo'lingani.
        </p>
      </div>
    </Panel>
  )
}
