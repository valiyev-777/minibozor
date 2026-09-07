import * as React from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { ChevronDown, ChevronRight, Lock, ScrollText } from "lucide-react"
import { api } from "@/api/client"
import type { Offer, Shelf } from "@/api/types"
import { Empty, Failed, Loading, Panel, Row } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Hint } from "@/components/ui/field"
import { MOVEMENT_KIND } from "@/lib/labels"
import { joined, said, when } from "@/lib/utils"

/**
 * What is actually in the warehouse, in the three figures that differ.
 *
 * `on_hand` is what is on the shelf. `reserved` is what is sitting in
 * somebody's basket or on an unpaid order — real goods, promised, not yet
 * gone. `sellable` is the difference, and it is the only one of the three
 * that answers "can I sell another one".
 *
 * A single "stock" number would hide the case that matters: twelve on the
 * shelf and eleven in baskets is not twelve for sale. So all three are shown,
 * and the one to act on is the one in the largest type.
 *
 * Nothing here is editable, by design — see `OffersPage` for the argument.
 * What this page offers instead is the ledger: a count that looks wrong is
 * not an opinion, it is a list of movements with a reason against each one.
 */
export function StockPage() {
  const [open, setOpen] = React.useState<number | null>(null)

  const offers = useQuery({
    queryKey: ["offers"],
    queryFn: () => api<Offer[]>("/staff/offers"),
  })
  const rows = offers.data ?? []

  // One shelf request per offer. A seller has a dozen; the alternative is an
  // endpoint that does not exist, and inventing a client-side aggregate from
  // `stock_left` would lose the reserved/sellable split that is the point.
  const shelves = useQueries({
    queries: rows.map((offer) => ({
      queryKey: ["shelf", offer.id],
      queryFn: () => api<Shelf[]>(`/staff/offers/${offer.id}/shelf`),
      staleTime: 15_000,
    })),
  })

  const total = shelves.reduce(
    (sum, q) => sum + (q.data?.[0]?.on_hand ?? 0),
    0,
  )
  const held = shelves.reduce((sum, q) => sum + (q.data?.[0]?.reserved ?? 0), 0)

  return (
    <>
      <PageHead
        title="Qoldiq"
        hint="Omborda nechta turgani. Javondagi son — jurnalning yig'indisi, shuning uchun bu sahifada tahrirlanadigan maydon yo'q."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Panel className="px-5 py-4">
          <p className="text-[13px] text-ink-soft">Javonda, jami</p>
          <p className="figure mt-0.5 text-ink">{total}</p>
        </Panel>
        <Panel className="px-5 py-4">
          <p className="text-[13px] text-ink-soft">Band — savatlarda</p>
          <p className="figure mt-0.5 text-warn">{held}</p>
          <p className="mt-0.5 text-[13px] text-ink-faint">
            Haqiqiy tovar, va'da qilingan
          </p>
        </Panel>
        <Panel className="px-5 py-4">
          <p className="text-[13px] text-ink-soft">Sotishga tayyor</p>
          <p className="figure mt-0.5 text-good">{total - held}</p>
          <p className="mt-0.5 text-[13px] text-ink-faint">
            Yana sotish mumkin bo'lgani
          </p>
        </Panel>
      </div>

      <Panel
        title="Taklif bo'yicha"
        hint="Rang va o'lcham darajasida ko'rish uchun qatorni bosing."
      >
        {offers.isPending ? <Loading /> : null}
        {offers.error ? (
          <Failed error={offers.error} onRetry={() => void offers.refetch()} />
        ) : null}
        {!offers.isPending && !offers.error && rows.length === 0 ? (
          <Empty
            title="Taklif yo'q, demak javonda ham hech narsa yo'q"
            hint="Qoldiq taklifga bog'lanadi: avval kartochkaga narx qo'yiladi, keyin partiya keltiriladi."
          />
        ) : null}

        {rows.map((offer, index) => {
          const shelf = shelves[index]
          const whole = shelf?.data?.[0]
          const leaves = (shelf?.data ?? []).slice(1)
          const expanded = open === offer.id

          return (
            <React.Fragment key={offer.id}>
              <Row onClick={leaves.length ? () => setOpen(expanded ? null : offer.id) : undefined}>
                {leaves.length ? (
                  expanded ? (
                    <ChevronDown className="size-4 shrink-0 text-ink-faint" />
                  ) : (
                    <ChevronRight className="size-4 shrink-0 text-ink-faint" />
                  )
                ) : (
                  <span className="size-4 shrink-0" />
                )}

                <div className="min-w-[12rem] flex-1">
                  <p className="text-[16px] font-medium text-ink">
                    {offer.product_title}
                  </p>
                  {offer.active ? null : (
                    <Badge tone="neutral" className="mt-1">
                      Sotuvda emas
                    </Badge>
                  )}
                </div>

                {shelf?.isPending ? (
                  <span className="h-4 w-40 animate-pulse rounded bg-line" />
                ) : (
                  <Counts
                    onHand={whole?.on_hand ?? 0}
                    reserved={whole?.reserved ?? 0}
                    sellable={whole?.sellable ?? 0}
                  />
                )}
              </Row>

              {expanded
                ? leaves.map((leaf) => (
                    <div
                      key={leaf.variant_id ?? "whole"}
                      className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-soft bg-canvas/60 py-3 pr-5 pl-14"
                    >
                      <p className="min-w-[10rem] flex-1 text-[14px] text-ink-soft">
                        {said(leaf.variant_label) || "Butun mahsulot"}
                      </p>
                      <Counts
                        onHand={leaf.on_hand}
                        reserved={leaf.reserved}
                        sellable={leaf.sellable}
                        small
                      />
                    </div>
                  ))
                : null}
            </React.Fragment>
          )
        })}

        <p className="flex items-start gap-2 border-t border-line-soft px-5 py-3 text-[13px] text-ink-soft">
          <Lock className="mt-0.5 size-4 shrink-0 text-ink-faint" />
          <span>
            Sonni ombor kirim va chiqim bilan o'zgartiradi. Ko'paytirish uchun
            «Partiyalar» sahifasida yangi partiya e'lon qiling.
          </span>
        </p>
      </Panel>

      <Movements />
    </>
  )
}

function Counts({
  onHand,
  reserved,
  sellable,
  small,
}: {
  onHand: number
  reserved: number
  sellable: number
  small?: boolean
}) {
  const big = small ? "text-[15px]" : "text-[18px]"
  return (
    <div className="flex items-center gap-5">
      <div className="w-14 text-right">
        <p className="text-[12px] text-ink-faint">Javon</p>
        <p className={`tabular ${big} font-medium text-ink`}>{onHand}</p>
      </div>
      <div className="w-14 text-right">
        <p className="text-[12px] text-ink-faint">Band</p>
        <p className={`tabular ${big} ${reserved ? "text-warn" : "text-ink-faint"}`}>
          {reserved}
        </p>
      </div>
      {/* The one to act on, so the one that carries weight. */}
      <div className="w-16 text-right">
        <p className="text-[12px] text-ink-faint">Tayyor</p>
        <p
          className={`tabular ${big} font-semibold ${
            sellable > 0 ? "text-good" : "text-danger"
          }`}
        >
          {sellable}
        </p>
      </div>
    </div>
  )
}

/**
 * The ledger, most recent first.
 *
 * This is what makes the read-only count acceptable rather than merely
 * imposed: a seller who thinks the figure is wrong can see every movement
 * that produced it, with its reason, and go to the warehouse with a row
 * rather than a suspicion.
 */
function Movements() {
  type Movement = {
    id: number
    kind: string
    quantity: number
    reason: string
    product_title: string
    variant_label: string
    actor_name: string
    created_at: string
  }
  type Page = { items: Movement[]; total: number }

  const query = useQuery({
    queryKey: ["movements"],
    queryFn: () => api<Page>("/staff/stock/movements", { query: { page_size: 25 } }),
  })

  const rows = query.data?.items ?? []

  return (
    <Panel
      className="mt-5"
      title="Harakatlar"
      hint="Javondagi son shu qatorlarning yig'indisi. Noto'g'ri ko'rinsa — bu ro'yxat bilan omborga murojaat qiling."
    >
      {query.isPending ? <Loading lines={2} /> : null}
      {query.error ? (
        <Failed error={query.error} onRetry={() => void query.refetch()} />
      ) : null}
      {!query.isPending && !query.error && rows.length === 0 ? (
        <Empty
          title="Hali harakat yo'q"
          hint="Birinchi partiya qabul qilinganda shu yerda kirim paydo bo'ladi."
        />
      ) : null}

      {rows.map((row) => (
        <Row key={row.id}>
          <p className="tabular w-32 shrink-0 text-[13px] text-ink-faint">
            {when(row.created_at)}
          </p>
          <Badge tone={row.quantity > 0 ? "good" : "neutral"}>
            {MOVEMENT_KIND[row.kind] ?? row.kind}
          </Badge>
          <div className="min-w-[10rem] flex-1">
            <p className="text-[14px] text-ink">{row.product_title}</p>
            <p className="text-[13px] text-ink-faint">
              {joined(row.variant_label, row.reason) || "—"}
            </p>
          </div>
          <p
            className={`tabular w-16 text-right text-[16px] font-semibold ${
              row.quantity > 0 ? "text-good" : "text-danger"
            }`}
          >
            {row.quantity > 0 ? `+${row.quantity}` : row.quantity}
          </p>
        </Row>
      ))}

      {query.data && query.data.total > rows.length ? (
        <div className="border-t border-line-soft px-5 py-3">
          <Hint>
            <ScrollText className="mr-1 inline size-3.5 align-[-2px]" />
            Oxirgi {rows.length} harakat, jami {query.data.total} ta.
          </Hint>
        </div>
      ) : null}
    </Panel>
  )
}
