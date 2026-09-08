import { Link } from "react-router-dom"
import { Plus } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Listing, ListingStage } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Async, Empty } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { PageTitle } from "@/components/Shell"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * Everything this seller opened, and where each of it has got to.
 *
 * One row per product and five words it can say, which is the whole state
 * machine as far as a seller is concerned: waiting on the warehouse, counted
 * in, on sale, sold out, refused. The word itself comes from the server
 * (`stage_label`) — the *colour* is decided here, because a colour is a
 * property of the screen and there is no point sending one over the wire.
 */
const TONE: Record<ListingStage, "neutral" | "brand" | "good" | "warn" | "danger"> = {
  awaiting_warehouse: "warn",
  in_warehouse: "brand",
  on_sale: "good",
  sold_out: "neutral",
  rejected: "danger",
  archived: "neutral",
}

export function ProductsPage() {
  const listings = useQuery({
    queryKey: ["listings"],
    queryFn: () => api<Listing[]>("/staff/catalog/listings"),
  })

  return (
    <>
      <PageTitle
        action={
          <Button asChild variant="primary">
            <Link to="/products/new">
              <Plus />
              {t.newProduct}
            </Link>
          </Button>
        }
      >
        {t.products}
      </PageTitle>

      <Panel>
        <Async
          query={listings}
          lines={4}
          empty={
            <Empty
              title={t.productsEmpty}
              hint={t.productsEmptyHint}
              action={
                <Button asChild variant="primary">
                  <Link to="/products/new">
                    <Plus />
                    {t.newProduct}
                  </Link>
                </Button>
              }
            />
          }
        >
          {(rows) => (
            <>
              {rows.map((row) => (
                <Row key={row.id} className="hover:bg-line-soft/50">
                  {/* The photograph is the fastest way a shopkeeper
                      recognises their own product; the SKU is how our
                      warehouse refers to it on the telephone. */}
                  <Thumb src={row.images[0]} className="size-11" />

                  <Link
                    to={`/products/${row.id}`}
                    className="min-w-0 flex-1 space-y-0.5 outline-none focus-visible:underline"
                  >
                    <p className="truncate text-[length:var(--text-body)] font-medium text-ink">
                      {row.title}
                    </p>
                    <p className="truncate text-[length:var(--text-micro)] text-ink-faint">
                      {row.sku}
                    </p>
                  </Link>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="tabular text-[length:var(--text-body)] text-ink">
                        {som(row.price)}
                      </p>
                      {/* One figure, and which one follows the stage: a
                          card still waiting has nothing on a shelf to
                          report, so the honest number is what was handed
                          in. */}
                      <p className="tabular text-[length:var(--text-micro)] text-ink-soft">
                        {row.stage === "awaiting_warehouse"
                          ? `${t.declaredShort}: ${num(
                              row.stock.reduce((sum, cell) => sum + cell.declared, 0),
                            )}`
                          : `${t.onHand}: ${num(row.on_hand_total)}`}
                      </p>
                    </div>
                    <Badge tone={TONE[row.stage]}>{row.stage_label}</Badge>
                  </div>
                </Row>
              ))}
            </>
          )}
        </Async>
      </Panel>
    </>
  )
}
