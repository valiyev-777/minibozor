import * as React from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Banknote, Check, Pencil, TriangleAlert } from "lucide-react"
import { api } from "@/api/client"
import type {
  SellerStatement,
  SellerStatementDetail,
  StatementLine,
  StatementLineKind,
} from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FieldError, Hint, Input, Label, Select, Textarea } from "@/components/ui/field"
import { LINE_KIND, SETTLEMENT_STATUS, SETTLEMENT_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { day, money, signedMoney, when } from "@/lib/utils"

/**
 * One seller's account, with everything that adds up to it.
 *
 * This is the screen the whole finance model exists for. A seller told
 * "9 100 000" has a number to argue with; a seller shown the order lines, the
 * returns and the days of storage behind it has an account to read. So the
 * lines are the body of the page and the total is a summary of them, not the
 * other way round.
 *
 * Three rules, all because these figures are money somebody is paid.
 *
 * **The invariant is shown, not hidden.** The backend holds that a statement's
 * payable equals the sum of its lines. This page adds the lines up itself and
 * says whether the two agree. If they ever disagree the page says so loudly
 * rather than printing the total — a figure that does not match its own
 * composition is the one thing nobody should be paid against.
 *
 * **Nothing is rounded.** The API answers in whole so'm and every figure here
 * is passed through untouched.
 *
 * **The two irreversible buttons are not where a hand lands.** Paying and
 * correcting sit in the header, apart from the rows, and each confirmation
 * repeats the sum it is about to commit to.
 */

const KEY = ["staff", "payouts"]

/** Which side of the ledger a kind falls on, for the eye rather than the sum. */
const CREDIT: Set<StatementLineKind> = new Set(["sale", "refund_commission"])

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

export function StatementPage() {
  const params = useParams()
  const navigate = useNavigate()
  const statementId = Number(params["id"])
  const [kind, setKind] = React.useState<"" | StatementLineKind>("")
  const [adjusting, setAdjusting] = React.useState(false)
  const [paying, setPaying] = React.useState(false)

  const key = [...KEY, "statement", statementId]
  const query = useQuery({
    queryKey: key,
    queryFn: () =>
      api<SellerStatementDetail>(`/staff/payouts/statements/${statementId}`),
  })

  const card = query.data
  const lines = card?.lines ?? []
  // Added up here rather than taken on trust. The backend's invariant is that
  // this equals `payable`; a page that only printed `payable` could not tell
  // anybody when it stopped being true.
  const sum = lines.reduce((total, line) => total + line.amount, 0)
  const agrees = card ? sum === card.payable : true

  const shown = kind ? lines.filter((line) => line.kind === kind) : lines

  const columns: Column<StatementLine>[] = [
    {
      key: "when",
      header: "Qachon",
      sortValue: (row) => row.occurred_at,
      cell: (row) => <span className="tabular text-ink-soft">{when(row.occurred_at)}</span>,
    },
    {
      key: "kind",
      header: "Turi",
      sortValue: (row) => row.kind,
      cell: (row) => (
        <Badge tone={CREDIT.has(row.kind) ? "good" : row.kind === "adjustment" ? "warn" : "neutral"}>
          {LINE_KIND[row.kind]}
        </Badge>
      ),
    },
    {
      key: "title",
      header: "Nima",
      sortValue: (row) => row.title,
      cell: (row) => (
        <div className="max-w-80">
          <span className="block truncate text-ink">{row.title || "—"}</span>
          <span className="block truncate text-[12px] text-ink-faint">{row.note}</span>
        </div>
      ),
    },
    {
      key: "source",
      header: "Manbasi",
      // The point of the column: every figure can be walked back to the event
      // that caused it, by an id somebody can look up.
      cell: (row) => <Source line={row} />,
    },
    {
      key: "quantity",
      header: "Dona",
      headClassName: "text-right",
      className: "text-right tabular text-ink-faint",
      sortValue: (row) => row.quantity,
      cell: (row) => row.quantity || "—",
    },
    {
      key: "amount",
      header: "Summa",
      headClassName: "text-right",
      className: "text-right tabular",
      sortValue: (row) => row.amount,
      cell: (row) => (
        <span
          className={
            row.amount < 0 ? "font-medium text-danger" : "font-medium text-good"
          }
        >
          {signedMoney(row.amount)}
        </span>
      ),
    },
  ]

  if (query.isPending || !card) {
    return (
      <Page title="Hisobot">
        <p className="text-[13px] text-ink-faint">Yuklanmoqda…</p>
      </Page>
    )
  }

  return (
    <Page
      title={card.seller_name}
      hint={`${card.period_label} · ${day(card.starts_on)} — ${day(card.ends_on)}`}
      actions={
        <div className="flex items-center gap-1.5">
          <Badge tone={SETTLEMENT_TONE[card.status]}>
            {SETTLEMENT_STATUS[card.status]}
          </Badge>
          <Button onClick={() => navigate("/payouts")}>
            <ArrowLeft />
            Moliya
          </Button>
          {/* Both money-moving buttons live up here, away from the rows a
              cursor travels over. */}
          {card.status === "open" ? (
            <Button className="ml-2" onClick={() => setAdjusting(true)}>
              <Pencil />
              Tuzatish
            </Button>
          ) : null}
          {card.status === "closed" ? (
            <Button variant="primary" className="ml-2" onClick={() => setPaying(true)}>
              <Banknote />
              To'langan deb belgilash
            </Button>
          ) : null}
        </div>
      }
    >
      <div className="space-y-3">
        <Totals card={card} sum={sum} agrees={agrees} />

        {card.status === "open" ? (
          <p className="rounded border border-line bg-line-soft/60 px-3 py-2 text-[12px] text-ink-soft">
            Davr hali ochiq — qatorlar har «Yig'ish»da qaytadan hisoblanadi va
            bu raqam o'zgarishi mumkin. To'lash uchun avval davrni yopish
            kerak.
          </p>
        ) : null}

        {card.status === "paid" ? (
          <dl className="flex flex-wrap gap-x-8 gap-y-1 rounded border border-good/30 bg-good-soft px-3 py-2 text-[12px]">
            <div>
              <dt className="text-ink-soft">To'langan</dt>
              <dd className="tabular font-medium text-ink">{when(card.paid_at)}</dd>
            </div>
            <div>
              <dt className="text-ink-soft">Usuli</dt>
              <dd className="font-medium text-ink">{card.payment_method || "—"}</dd>
            </div>
            <div>
              <dt className="text-ink-soft">Havola</dt>
              <dd className="tabular font-medium text-ink">
                {card.payment_reference || "—"}
              </dd>
            </div>
            {card.note ? (
              <div>
                <dt className="text-ink-soft">Izoh</dt>
                <dd className="text-ink">{card.note}</dd>
              </div>
            ) : null}
          </dl>
        ) : null}

        <DataTable
          rows={shown}
          columns={columns}
          rowKey={(row) => row.id}
          emptyTitle="Qator yo'q"
          emptyHint={
            kind
              ? "Bu turdagi qator bu hisobotda yo'q."
              : "Bu davrda bu sotuvchida hech narsa bo'lmagan."
          }
          clientPageSize={60}
          toolbar={
            <>
              <div className="flex items-center gap-1.5">
                <Label htmlFor="l-kind">Turi</Label>
                <Select
                  id="l-kind"
                  className="w-48"
                  value={kind}
                  onChange={(event) =>
                    setKind(event.target.value as "" | StatementLineKind)
                  }
                >
                  {KINDS.map((value) => (
                    <option key={value} value={value}>
                      {value ? LINE_KIND[value] : "Hammasi"}
                    </option>
                  ))}
                </Select>
              </div>
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
            </>
          }
        />
      </div>

      {adjusting ? (
        <Adjust card={card} invalidate={key} onClose={() => setAdjusting(false)} />
      ) : null}
      {paying ? (
        <Pay card={card} invalidate={key} onClose={() => setPaying(false)} />
      ) : null}
    </Page>
  )
}

function Source({ line }: { line: StatementLine }) {
  const source = line.order_item_id
    ? { label: "Buyurtma satri", id: line.order_item_id }
    : line.return_request_id
      ? { label: "Qaytarish", id: line.return_request_id }
      : line.offer_id
        ? { label: "Taklif", id: line.offer_id }
        : null

  if (!source) {
    return <span className="text-[12px] text-ink-faint">Qo'lda kiritilgan</span>
  }
  return (
    <span className="text-[12px] text-ink-soft">
      {source.label} <span className="tabular font-medium text-ink">#{source.id}</span>
    </span>
  )
}

/**
 * The headings, and the check that they mean anything.
 *
 * `payable` is the signed arithmetic; the rest are positive figures read as
 * deductions. The sum of the lines is printed beside the total on purpose: it
 * is the backend's own invariant, and an interface that hides it is asking to
 * be trusted instead of being checkable.
 */
function Totals({
  card,
  sum,
  agrees,
}: {
  card: SellerStatementDetail
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
    <section className="overflow-hidden rounded-lg border border-line bg-surface">
      <dl className="divide-y divide-line-soft">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-4 px-3 py-1.5"
          >
            <dt className="text-[13px] text-ink-soft">{row.label}</dt>
            <dd
              className={`tabular text-[13px] ${
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

        <div className="flex items-baseline justify-between gap-4 border-t border-line bg-line-soft/50 px-3 py-2">
          <dt className="text-[13px] font-semibold text-ink">To'lanadi</dt>
          <dd
            className={`tabular text-[17px] font-semibold ${
              card.payable < 0 ? "text-danger" : "text-ink"
            }`}
          >
            {money(card.payable)} <span className="text-[13px] font-normal">so'm</span>
          </dd>
        </div>
      </dl>

      {agrees ? (
        <p className="flex items-center gap-1.5 border-t border-line px-3 py-1.5 text-[12px] text-ink-faint">
          <Check className="size-3.5 shrink-0 text-good" />
          {card.line_count} qatorning yig'indisi{" "}
          <span className="tabular font-medium text-ink">{money(sum)}</span> — jamiga
          teng. Hisobot — raqam emas, jurnal: har bir qator o'z manbasini
          ko'rsatadi.
        </p>
      ) : (
        // Never reached while the backend holds its invariant, and that is
        // exactly why it is here: if it ever breaks, the number nobody should
        // pay against must not be printed as though it were fine.
        <p className="flex items-start gap-1.5 border-t border-danger/30 bg-danger-soft px-3 py-2 text-[12px]">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
          <span>
            <span className="font-semibold text-danger">
              Jami qatorlar yig'indisiga teng emas.
            </span>{" "}
            Jami{" "}
            <span className="tabular font-medium">{money(card.payable)}</span>,
            qatorlar yig'indisi{" "}
            <span className="tabular font-medium">{money(sum)}</span> — farq{" "}
            <span className="tabular font-medium">{money(card.payable - sum)}</span>.
            Bu hisobot bo'yicha to'lov qilmang.
          </span>
        </p>
      )}
    </section>
  )
}

function Adjust({
  card,
  invalidate,
  onClose,
}: {
  card: SellerStatement
  invalidate: (string | number)[]
  onClose: () => void
}) {
  const [amount, setAmount] = React.useState("")
  const [note, setNote] = React.useState("")

  const adjust = useAction<void, SellerStatementDetail>({
    run: () =>
      api<SellerStatementDetail>(`/staff/payouts/statements/${card.id}/adjust`, {
        method: "POST",
        json: { amount: Number(amount) || 0, note: note.trim() },
      }),
    invalidate: [invalidate, KEY],
    success: "Tuzatish qo'shildi",
    onDone: onClose,
  })

  const value = Number(amount) || 0
  const after = card.payable + value

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="Tuzatish qo'shish"
      description={`${card.seller_name} · ${card.period_label}`}
      confirmLabel="Qo'shish"
      // The reason is required by the API, so the button is disabled without
      // it rather than letting somebody discover a 422.
      disabled={!note.trim() || !value || adjust.isPending}
      pending={adjust.isPending}
      onConfirm={() => adjust.mutate()}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          <Label htmlFor="a-amount">Summa (so'm)</Label>
          <Input
            id="a-amount"
            type="number"
            autoFocus
            className="tabular"
            value={amount}
            placeholder="-50000"
            onChange={(event) => setAmount(event.target.value)}
          />
          <Hint>
            Ishorasi bilan: manfiy — chegirma, musbat — sotuvchi foydasiga.
          </Hint>
        </div>

        <div className="space-y-1">
          <Label htmlFor="a-note">Sabab</Label>
          <Textarea
            id="a-note"
            value={note}
            placeholder="Kelishuv bo'yicha yetkazish xarajati qaytarildi · TKT-1188"
            onChange={(event) => setNote(event.target.value)}
          />
          {note.trim() ? null : (
            <FieldError>
              Sababsiz tuzatish — hisobotdagi yagona himoyasiz qator. Server
              ham bo'sh sababni qabul qilmaydi.
            </FieldError>
          )}
        </div>

        {value ? (
          <dl className="rounded border border-line bg-line-soft/60 px-2.5 py-2">
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-[12px] text-ink-soft">Hozir</dt>
              <dd className="tabular text-[13px] text-ink">{money(card.payable)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-[12px] text-ink-soft">Tuzatish</dt>
              <dd
                className={`tabular text-[13px] ${
                  value < 0 ? "text-danger" : "text-good"
                }`}
              >
                {signedMoney(value)}
              </dd>
            </div>
            <div className="mt-1 flex items-baseline justify-between gap-3 border-t border-line pt-1">
              <dt className="text-[12px] font-medium text-ink">Bo'ladi</dt>
              <dd
                className={`tabular text-[15px] font-semibold ${
                  after < 0 ? "text-danger" : "text-ink"
                }`}
              >
                {money(after)} so'm
              </dd>
            </div>
          </dl>
        ) : null}

        <Hint>
          Faqat ochiq hisobotga. Yopilganiga tuzatish kiritishga server 409
          beradi — keyingi davrda, ko'rinadigan joyda qilinadi.
        </Hint>
      </div>
    </ConfirmDialog>
  )
}

const METHODS = ["bank o'tkazmasi", "naqd", "Payme", "Click", "Uzum Bank"]

function Pay({
  card,
  invalidate,
  onClose,
}: {
  card: SellerStatement
  invalidate: (string | number)[]
  onClose: () => void
}) {
  const [method, setMethod] = React.useState(METHODS[0] ?? "bank o'tkazmasi")
  const [reference, setReference] = React.useState("")
  const [note, setNote] = React.useState("")

  const pay = useAction<void, SellerStatement>({
    run: () =>
      api<SellerStatement>(`/staff/payouts/statements/${card.id}/pay`, {
        method: "POST",
        json: { method, reference: reference.trim(), note: note.trim() },
      }),
    invalidate: [invalidate, KEY],
    success: (row) => `${row.seller_name} — to'landi`,
    onDone: onClose,
  })

  return (
    <ConfirmDialog
      open
      onOpenChange={(next) => !next && onClose()}
      title="To'langan deb belgilash"
      description={`${card.seller_name} · ${card.period_label}`}
      confirmLabel="To'landi"
      disabled={!method.trim() || pay.isPending}
      pending={pay.isPending}
      onConfirm={() => pay.mutate()}
    >
      <div className="space-y-3">
        {/* The sum, repeated. A confirmation that does not name the figure it
            is confirming is a confirmation of nothing. */}
        <div className="rounded border border-line bg-line-soft/60 px-2.5 py-2">
          <p className="text-[12px] text-ink-soft">Sotuvchiga o'tkaziladigan summa</p>
          <p
            className={`tabular text-[22px] font-semibold ${
              card.payable < 0 ? "text-danger" : "text-ink"
            }`}
          >
            {money(card.payable)}{" "}
            <span className="text-[13px] font-normal text-ink-soft">so'm</span>
          </p>
          {card.payable < 0 ? (
            <p className="mt-0.5 text-[12px] font-medium text-danger">
              Manfiy — bu davrda sotuvchi bizga qarzdor. O'tkazma emas,
              hisobning yopilishi.
            </p>
          ) : null}
        </div>

        <div className="space-y-1">
          <Label htmlFor="pay-method">Usuli</Label>
          <Select
            id="pay-method"
            value={method}
            onChange={(event) => setMethod(event.target.value)}
          >
            {METHODS.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="pay-ref">Havola</Label>
          <Input
            id="pay-ref"
            className="tabular"
            value={reference}
            placeholder="TR-99001"
            onChange={(event) => setReference(event.target.value)}
          />
          <Hint>
            O'tkazma raqami — sotuvchi «pul kelmadi» deganda tekshiriladigan
            yagona narsa. Majburiy emas (naqd ham bo'ladi), lekin so'raladi.
          </Hint>
        </div>

        <div className="space-y-1">
          <Label htmlFor="pay-note">Izoh</Label>
          <Input
            id="pay-note"
            value={note}
            placeholder="Oylik to'lov"
            onChange={(event) => setNote(event.target.value)}
          />
        </div>

        <p className="text-[12px] text-ink-soft">
          Bir marta. Ikkinchi marta belgilashga server 409 beradi — bitta
          hisobga ikki o'tkazma, pul yo'qolgani esa faqat to'lanmagan
          sotuvchi qo'ng'iroq qilganda ma'lum bo'ladi.
        </p>
      </div>
    </ConfirmDialog>
  )
}
