import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Check, Info, TriangleAlert } from "lucide-react"
import { api } from "@/api/client"
import type { StatementDetail, StatementLine, StatementLineKind } from "@/api/types"
import { Loading, Panel } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Label, Select } from "@/components/ui/field"
import { LINE_CREDIT, LINE_KIND, SETTLEMENT_STATUS, SETTLEMENT_TONE } from "@/lib/labels"
import { day, money, signedMoney, when } from "@/lib/utils"

const KINDS: ("" | StatementLineKind)[] = [
  "",
  "sale",
  "commission",
  "fulfilment",
  "refund",
  "refund_commission",
  "storage",
  "adjustment",
]

/**
 * One period's account, with everything that adds up to it.
 *
 * The one screen in this cabinet that is a table, and deliberately so. Every
 * other screen here is cards, because a seller is recognising things; this
 * one is read by comparing figures down a column, and cards would make that
 * impossible. So the amounts are `tabular` and right-aligned exactly as they
 * are in the backoffice.
 *
 * The rigour is the same too, for the same reason: this is money.
 *
 * - **Nothing is rounded.** The API answers in whole so'm and every figure
 *   passes through untouched.
 * - **Every line names its source.** An order line, a return, an offer that
 *   sat in the warehouse. "You get 91 550" is a number to argue with; this is
 *   an account to read, and the seller can read it without asking anybody.
 * - **The invariant is shown, not hidden.** The backend holds that `payable`
 *   equals the sum of the lines. This page adds them up itself and says
 *   whether they agree — a page that only printed the total could not tell
 *   anybody when that stopped being true.
 */
export function StatementPage() {
  const params = useParams()
  const id = Number(params["id"])
  const [kind, setKind] = React.useState<"" | StatementLineKind>("")

  const query = useQuery({
    queryKey: ["statements", id],
    queryFn: () => api<StatementDetail>(`/staff/payouts/statements/${id}`),
  })

  const card = query.data
  const lines = card?.lines ?? []
  // Added up here rather than taken on trust.
  const sum = lines.reduce((total, line) => total + line.amount, 0)
  const agrees = card ? sum === card.payable : true
  const shown = kind ? lines.filter((line) => line.kind === kind) : lines

  if (query.isPending || !card) {
    return (
      <>
        <PageHead title="Hisobot" />
        <Panel>
          <Loading lines={4} />
        </Panel>
      </>
    )
  }

  return (
    <>
      <PageHead
        title={card.period_label}
        hint={`${day(card.starts_on)} — ${day(card.ends_on)}`}
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={SETTLEMENT_TONE[card.status]}>
              {SETTLEMENT_STATUS[card.status]}
            </Badge>
            <Button asChild>
              <Link to="/statements">
                <ArrowLeft />
                Hisobotlar
              </Link>
            </Button>
          </div>
        }
      />

      <div className="space-y-5">
        <Totals card={card} sum={sum} agrees={agrees} />

        {card.status === "open" ? (
          <p className="flex items-start gap-2 rounded-xl bg-warn-soft px-4 py-3 text-[14px] text-ink">
            <Info className="mt-0.5 size-4 shrink-0 text-warn" />
            <span>
              Bu davr hali ochiq — raqamlar qayta hisoblanishi mumkin.
              Tasdiqlangandan keyin ular o'zgarmaydi.
            </span>
          </p>
        ) : null}

        {card.status === "paid" ? (
          <dl className="flex flex-wrap gap-x-8 gap-y-2 rounded-xl border border-good/30 bg-good-soft px-4 py-3 text-[14px]">
            <div>
              <dt className="text-[13px] text-ink-soft">To'langan</dt>
              <dd className="tabular font-medium text-ink">{when(card.paid_at)}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-soft">Usuli</dt>
              <dd className="font-medium text-ink">{card.payment_method || "—"}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-soft">Havola</dt>
              <dd className="tabular font-medium text-ink">
                {card.payment_reference || "—"}
              </dd>
            </div>
          </dl>
        ) : null}

        <Panel
          title="Qatorlar"
          hint="Har bir raqam qaysi hodisadan kelib chiqqani ko'rsatilgan."
          actions={
            <div className="flex items-center gap-2">
              <Label htmlFor="kind" className="whitespace-nowrap">
                Turi
              </Label>
              <Select
                id="kind"
                className="w-48"
                value={kind}
                onChange={(event) => setKind(event.target.value as "" | StatementLineKind)}
              >
                {KINDS.map((value) => (
                  <option key={value} value={value}>
                    {value ? LINE_KIND[value] : "Hammasi"}
                  </option>
                ))}
              </Select>
            </div>
          }
        >
          {/* A table, in a cabinet made of cards. Compared down a column, so
              it has to be a column. */}
          <div className="overflow-x-auto border-t border-line-soft">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-line-soft bg-line-soft/50">
                  <th className="px-5 py-2 text-[13px] font-medium text-ink-soft">
                    Qachon
                  </th>
                  <th className="px-3 py-2 text-[13px] font-medium text-ink-soft">Turi</th>
                  <th className="px-3 py-2 text-[13px] font-medium text-ink-soft">Nima</th>
                  <th className="px-3 py-2 text-[13px] font-medium text-ink-soft">
                    Manbasi
                  </th>
                  <th className="px-5 py-2 text-right text-[13px] font-medium text-ink-soft">
                    Summa
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((line) => (
                  <tr key={line.id} className="border-b border-line-soft last:border-0">
                    <td className="tabular px-5 py-3 align-top text-[13px] whitespace-nowrap text-ink-faint">
                      {when(line.occurred_at)}
                    </td>
                    <td className="px-3 py-3 align-top whitespace-nowrap">
                      <Badge
                        tone={
                          line.kind === "adjustment"
                            ? "warn"
                            : LINE_CREDIT[line.kind]
                              ? "good"
                              : "neutral"
                        }
                      >
                        {LINE_KIND[line.kind]}
                      </Badge>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <p className="text-[14px] text-ink">{line.title || "—"}</p>
                      {line.note ? (
                        <p className="text-[13px] text-ink-faint">{line.note}</p>
                      ) : null}
                    </td>
                    <td className="px-3 py-3 align-top whitespace-nowrap">
                      <Source line={line} />
                    </td>
                    <td
                      className={`tabular px-5 py-3 text-right align-top text-[15px] font-medium whitespace-nowrap ${
                        line.amount < 0 ? "text-danger" : "text-good"
                      }`}
                    >
                      {signedMoney(line.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {shown.length === 0 ? (
            <p className="px-5 py-8 text-center text-[14px] text-ink-faint">
              Bu turdagi qator yo'q.
            </p>
          ) : null}

          <p className="border-t border-line-soft px-5 py-3">
            <Hint>
              {shown.length}
              {kind ? ` / ${lines.length}` : ""} qator
              {kind ? (
                <>
                  {" · "}
                  <span className="tabular font-medium text-ink">
                    {signedMoney(shown.reduce((t, l) => t + l.amount, 0))}
                  </span>
                </>
              ) : null}
            </Hint>
          </p>
        </Panel>
      </div>
    </>
  )
}

function Source({ line }: { line: StatementLine }) {
  const source = line.order_item_id
    ? { label: "Buyurtma", id: line.order_item_id }
    : line.return_request_id
      ? { label: "Qaytarish", id: line.return_request_id }
      : line.offer_id
        ? { label: "Taklif", id: line.offer_id }
        : null

  if (!source) {
    return <span className="text-[13px] text-ink-faint">Qo'lda kiritilgan</span>
  }
  return (
    <span className="text-[13px] text-ink-soft">
      {source.label} <span className="tabular font-medium text-ink">#{source.id}</span>
    </span>
  )
}

/**
 * The headings and the figure they have to add up to.
 *
 * Worded from the seller's side: "ushlab qolindi" rather than the platform's
 * "commission we kept". Same rows, described by whose pocket they leave.
 */
function Totals({
  card,
  sum,
  agrees,
}: {
  card: StatementDetail
  sum: number
  agrees: boolean
}) {
  const rows = [
    { label: "Sotilgan", value: card.gross_sales, credit: true },
    { label: "Komissiya", value: -card.commission, credit: false },
    { label: "Yig'ish-yetkazish", value: -card.fulfilment, credit: false },
    { label: "Qaytarishlar", value: -card.refunds, credit: false },
    { label: "Saqlash", value: -card.storage, credit: false },
  ]
  if (card.adjustments) {
    rows.push({
      label: "Tuzatishlar",
      value: card.adjustments,
      credit: card.adjustments > 0,
    })
  }

  return (
    <Panel className="overflow-hidden">
      <dl className="divide-y divide-line-soft">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-4 px-5 py-2.5"
          >
            <dt className="text-[15px] text-ink-soft">{row.label}</dt>
            <dd
              className={`tabular text-[15px] ${
                row.value === 0
                  ? "text-ink-faint"
                  : row.credit
                    ? "text-good"
                    : "text-danger"
              }`}
            >
              {signedMoney(row.value)}
            </dd>
          </div>
        ))}

        <div className="flex items-baseline justify-between gap-4 border-t border-line bg-brand-soft/60 px-5 py-4">
          <dt className="text-[16px] font-semibold text-ink">Qo'lga tegadi</dt>
          <dd
            className={`figure ${card.payable < 0 ? "text-danger" : "text-brand-ink"}`}
          >
            {money(card.payable)}{" "}
            <span className="text-[14px] font-normal text-ink-soft">so'm</span>
          </dd>
        </div>
      </dl>

      {card.payable < 0 ? (
        <p className="border-t border-danger/20 bg-danger-soft px-5 py-3 text-[13px] text-ink">
          Manfiy: bu davrda ushlab qolinganlar sotilganidan ko'p bo'lgan —
          summa keyingi hisobotdan yechiladi.
        </p>
      ) : null}

      {agrees ? (
        <p className="flex items-start gap-2 border-t border-line-soft px-5 py-3 text-[13px] text-ink-soft">
          <Check className="mt-0.5 size-4 shrink-0 text-good" />
          <span>
            {card.line_count} qatorning yig'indisi{" "}
            <span className="tabular font-medium text-ink">{money(sum)}</span> — jamiga
            teng. Bu raqam ro'yxatdan kelib chiqadi, alohida hisoblanmaydi.
          </span>
        </p>
      ) : (
        // Never reached while the backend holds its invariant — which is why
        // it is here. A figure that disagrees with its own composition is the
        // one number nobody should accept.
        <p className="flex items-start gap-2 border-t border-danger/30 bg-danger-soft px-5 py-3 text-[13px]">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
          <span>
            <span className="font-semibold text-danger">
              Jami qatorlar yig'indisiga teng emas.
            </span>{" "}
            Jami <span className="tabular font-medium">{money(card.payable)}</span>,
            qatorlar <span className="tabular font-medium">{money(sum)}</span> — farq{" "}
            <span className="tabular font-medium">{money(card.payable - sum)}</span>. Bu
            hisobotni qabul qilmang, administratorga murojaat qiling.
          </span>
        </p>
      )}
    </Panel>
  )
}
