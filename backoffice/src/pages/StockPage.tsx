import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { MovementKind, MovementPage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { PageTitle } from "@/components/Shell"
import { useFilter } from "@/lib/useFilter"
import { moment, num } from "@/lib/format"
import { movementKind, t } from "@/lib/labels"

/**
 * The ledger, newest first — one table and no chart.
 *
 * A shelf figure is the sum of these rows, so this screen is the answer to
 * every "why does it say four". It is a list rather than a graph on purpose:
 * a disputed count is not a trend, it is a row with a reason and a name
 * against it, and what somebody needs is to find that row.
 *
 * The quantity carries its sign because the sign *is* the information: goods
 * came in or went out, and a column of unsigned numbers would need the kind
 * read beside every one of them to mean anything.
 */
const TONE: Record<string, "good" | "danger" | "warn" | "brand" | "neutral"> = {
  opening: "neutral",
  intake: "good",
  sale: "brand",
  cancel_return: "warn",
  customer_return: "warn",
  write_off: "danger",
  count_adjustment: "neutral",
  seller_return: "danger",
}

/** The kinds worth filtering by; the rest are reachable through "Hammasi". */
const KINDS: { key: MovementKind | ""; label: string }[] = [
  { key: "", label: t.all },
  { key: "intake", label: movementKind.intake! },
  { key: "sale", label: movementKind.sale! },
  { key: "customer_return", label: movementKind.customer_return! },
  { key: "write_off", label: movementKind.write_off! },
  { key: "seller_return", label: movementKind.seller_return! },
]

export function StockPage() {
  const [kind, setKind] = useFilter<MovementKind>("kind", "")
  const movements = useQuery({
    queryKey: ["stock", kind],
    queryFn: () =>
      api<MovementPage>("/staff/stock/movements", {
        query: { page_size: 60, ...(kind ? { kind } : {}) },
      }),
  })

  return (
    <>
      <PageTitle
        action={
          <div className="flex flex-wrap gap-1">
            {KINDS.map((row) => (
              <button
                key={row.key}
                type="button"
                onClick={() => setKind(row.key)}
                className={
                  "rounded-[var(--radius-control)] px-2.5 py-1 text-[length:var(--text-small)] " +
                  (kind === row.key
                    ? "bg-brand text-brand-ink"
                    : "text-ink-soft hover:bg-line-soft")
                }
              >
                {row.label}
              </button>
            ))}
          </div>
        }
      >
        {t.stock}
      </PageTitle>

      <Panel>
        <div className="hidden border-b border-line-soft px-5 py-2 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint sm:flex sm:gap-4">
          <span className="w-40">{t.when}</span>
          <span className="flex-1">{t.product}</span>
          <span className="w-24 text-right">{t.quantity}</span>
          <span className="w-40">{t.reason}</span>
          <span className="w-32">{t.who}</span>
        </div>

        <Async query={movements} lines={8}>
          {(page) =>
            page.items.length === 0 ? (
              <Empty title={t.stockEmpty} hint={t.stockEmptyHint} />
            ) : (
              <>
                {page.items.map((move) => (
                  <Row key={move.id} className="sm:flex-nowrap">
                    <span className="w-40 shrink-0 text-[length:var(--text-small)] text-ink-faint">
                      {moment(move.created_at)}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-ink">{move.product_title}</p>
                      <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                        {move.variant_label} · {move.sku}
                      </p>
                    </div>
                    <span
                      className={
                        "tabular w-24 text-right font-medium " +
                        (move.quantity < 0 ? "text-danger" : "text-good")
                      }
                    >
                      {move.quantity > 0 ? `+${num(move.quantity)}` : num(move.quantity)}
                    </span>
                    <span className="w-40 shrink-0">
                      <Badge tone={TONE[move.kind] ?? "neutral"}>
                        {movementKind[move.kind] ?? move.kind}
                      </Badge>
                    </span>
                    <span className="w-32 truncate text-[length:var(--text-small)] text-ink-soft">
                      {move.actor || "—"}
                    </span>
                    {move.reason ? (
                      <span className="w-full truncate text-[length:var(--text-small)] text-ink-soft sm:w-56">
                        {move.reason}
                      </span>
                    ) : null}
                  </Row>
                ))}
              </>
            )
          }
        </Async>
      </Panel>
    </>
  )
}
