import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { ImageOff, PackagePlus } from "lucide-react"
import { api } from "@/api/client"
import type { Listing, ListingStage } from "@/api/types"
import { Empty, Failed, Loading, Panel } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint } from "@/components/ui/field"
import { mediaSrc, money, when } from "@/lib/utils"
import { NewProduct } from "@/pages/product/NewProduct"

export const LISTINGS = ["listings"]

/**
 * What tone each stage gets, and the reasoning is the seller's eye rather than
 * a palette: the two that need an action from somebody are the two that are
 * coloured, and "on sale" is the quiet one because it is the resting state.
 */
const TONE: Record<ListingStage, "neutral" | "brand" | "good" | "warn" | "danger"> = {
  awaiting_warehouse: "warn",
  in_warehouse: "brand",
  on_sale: "good",
  sold_out: "warn",
  rejected: "danger",
  archived: "neutral",
}

/**
 * My products.
 *
 * The screen the cabinet was missing, and the reason it was missing is worth
 * writing down: the catalogue was built on the rule that a card belonged to
 * the platform, so a seller had nothing of their own to list. That was wrong.
 * A seller owns the product they sell — they open it, photograph it, price it
 * and say what colours and sizes they have.
 *
 * What the warehouse confirms is that the goods arrived. So the stages read as
 * a journey and not as a permission queue: waiting for the warehouse, counted
 * in, on sale.
 *
 * A refusal is the one stage that owes an explanation, and it carries it.
 * Before this, `moderation_note` was written on the row by whoever refused it
 * and there was nowhere for the seller to read it — they were being asked to
 * fix something without being told what was wrong.
 */
export function ProductsPage() {
  const [adding, setAdding] = React.useState(false)
  const listings = useQuery({
    queryKey: LISTINGS,
    queryFn: () => api<Listing[]>("/staff/catalog/listings"),
  })

  return (
    <>
      <PageHead
        title="Mahsulotlarim"
        hint="O'zingiz qo'shgan mahsulotlar. Rasm, narx, rang va razmer — hammasi sizniki. Ombor tovar kelganini tasdiqlaydi va shundan keyin mahsulot ilovada paydo bo'ladi."
        actions={
          <Button variant="primary" onClick={() => setAdding(true)}>
            <PackagePlus />
            Yangi mahsulot
          </Button>
        }
      />

      {listings.isPending ? (
        <Panel>
          <Loading lines={4} />
        </Panel>
      ) : listings.isError ? (
        <Panel>
          <Failed error={listings.error} onRetry={() => void listings.refetch()} />
        </Panel>
      ) : !listings.data.length ? (
        <Panel>
          <Empty
            title="Hali mahsulot qo'shmagansiz"
            hint="«Yangi mahsulot» — nomi, rasmlari, narxi, ranglari va razmerlari. Saqlaganingizda omborga sizning partiyangiz bo'lib tushadi."
          />
        </Panel>
      ) : (
        <div className="space-y-4">
          {listings.data.map((row) => (
            <Row key={row.id} row={row} />
          ))}
        </div>
      )}

      {adding ? <NewProduct onClose={() => setAdding(false)} /> : null}
    </>
  )
}

function Row({ row }: { row: Listing }) {
  const cover = row.images[0]
  // Grouped by colour, because that is how a seller thinks about the box.
  const byColour = new Map<string, typeof row.stock>()
  for (const cell of row.stock) {
    const list = byColour.get(cell.color_label) ?? []
    list.push(cell)
    byColour.set(cell.color_label, list)
  }

  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-wrap items-start gap-4 px-5 pt-4 pb-4 sm:flex-nowrap">
        {cover ? (
          <img
            src={mediaSrc(cover)}
            alt=""
            className="size-20 shrink-0 rounded-xl border border-line object-cover"
          />
        ) : (
          <span className="grid size-20 shrink-0 place-items-center rounded-xl border border-line bg-line-soft">
            <ImageOff className="size-5 text-ink-faint" />
          </span>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[16px] font-semibold text-ink">{row.title}</h3>
            <Badge tone={TONE[row.stage]}>{row.stage_label}</Badge>
          </div>
          <p className="mt-0.5 text-[13px] text-ink-soft">
            {row.sku} · {when(row.created_at)}
            {row.supply_code ? ` · ${row.supply_code}` : ""}
          </p>

          {/* A refusal owes a sentence, and this is where it is read. */}
          {row.stage === "rejected" && row.moderation_note ? (
            <p className="mt-2 rounded-lg bg-danger-soft px-3 py-2 text-[13px] text-danger">
              <span className="font-semibold">Sabab:</span> {row.moderation_note}
            </p>
          ) : null}

          {row.stage === "awaiting_warehouse" ? (
            <Hint className="mt-2">
              Ombor tovarni sanab qabul qilganda mahsulot sotuvga chiqadi.
            </Hint>
          ) : null}
        </div>

        <div className="shrink-0 text-right">
          <p className="text-[19px] font-semibold text-ink">{money(row.price)}</p>
          <p className="text-[13px] text-ink-soft">so'm</p>
          <p className="mt-2 text-[13px] text-ink-soft">
            Sotiladigan: <span className="font-semibold text-ink">{row.sellable_total}</span>
          </p>
        </div>
      </div>

      {byColour.size ? (
        <div className="border-t border-line-soft px-5 py-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {[...byColour].map(([colour, cells]) => (
              <div key={colour}>
                <p className="mb-1.5 text-[13px] font-medium text-ink">{colour}</p>
                <div className="flex flex-wrap gap-1.5">
                  {cells.map((cell) => (
                    <span
                      key={cell.variant_id}
                      className="inline-flex items-baseline gap-1 rounded-md border border-line px-2 py-1 text-[13px]"
                      title={`E'lon qilingan: ${cell.declared} · omborda: ${cell.on_hand}`}
                    >
                      <span className="text-ink-soft">{cell.size_label ?? colour}</span>
                      <span className="font-semibold text-ink">{cell.sellable}</span>
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <Hint className="mt-3">
            Raqam — hozir sotiladigan soni. Savatga solingan tovar band
            hisoblanadi, shuning uchun omborda turgan sonidan kam bo'lishi
            mumkin.
          </Hint>
        </div>
      ) : null}
    </Panel>
  )
}
