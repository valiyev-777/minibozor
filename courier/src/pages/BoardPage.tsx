import { Package, Plus } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Stop } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Async, Empty } from "@/ui/states"
import { useAction } from "@/lib/mutate"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * Every order the warehouse has packed and nobody has taken.
 *
 * This screen is why the app has navigation at all. A courier used to be
 * handed a round by an operator, which meant a packed parcel sat on a shelf
 * until somebody in an office remembered to name somebody for it — and a
 * courier standing in that warehouse could see the box and not the order.
 * Now the bench marks it ready and whoever wants it takes it.
 *
 * **Oldest first, and no sort control.** A board a courier could sort by value
 * is a board where the cheap stops are nobody's first choice, which is
 * exactly the incentive a flat delivery fee exists to avoid.
 *
 * Every row is a card with its own button rather than a tappable row, because
 * the act here is not "look at this" — it is "this one is mine". A row that
 * navigated first and offered the button on the next screen would put a
 * screen between a courier and the parcel in front of them.
 */
export function BoardPage() {
  const board = useQuery({
    queryKey: ["board"],
    queryFn: () => api<Stop[]>("/courier/orders/available"),
    refetchInterval: 30_000,
  })
  const navigate = useNavigate()

  const take = useAction<Stop, Stop>({
    run: (stop) =>
      api<Stop>(`/courier/orders/${stop.id}/take`, {
        method: "POST",
        // One key per order rather than per press: the second press of a
        // button whose first press is still in flight is the ordinary case on
        // a phone, and it must not become a second claim.
        key: `take-${stop.id}`,
      }),
    invalidate: [["board"], ["round"], ["earnings"]],
    success: t.taken,
    // Somebody else got there first. Not an error the courier did anything
    // about, so it reads as news rather than a failure.
    onDone: () => void board.refetch(),
  })

  return (
    <div className="space-y-4 px-[var(--gap-page)] py-[var(--gap-page)]">
      <header className="flex items-baseline justify-between gap-3">
        <h1 className="text-xl font-semibold text-ink">{t.board}</h1>
        {board.data?.length ? (
          <p className="text-[length:var(--text-small)] text-ink-soft">
            {num(board.data.length)} {t.waiting}
          </p>
        ) : null}
      </header>

      <Async
        query={board}
        lines={3}
        empty={
          <Empty
            title={t.boardEmpty}
            hint={t.boardEmptyHint}
            className="rounded-[var(--radius-panel)] border border-line bg-surface"
          />
        }
      >
        {(rows) => (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            {rows.map((stop) => (
              <article
                key={stop.id}
                className="min-w-0 rounded-[var(--radius-panel)] border border-line bg-surface
                           p-4 lg:flex lg:items-center lg:gap-4"
              >
                <div className="flex min-w-0 flex-1 gap-3">
                  <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-deep">
                    <Package className="size-5" />
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="tabular font-semibold text-ink">{stop.code}</span>
                      {stop.cash_due > 0 ? (
                        <Badge tone="warn">
                          {t.cashDue}: {som(stop.cash_due)}
                        </Badge>
                      ) : (
                        <Badge tone="good">{t.paidAlready}</Badge>
                      )}
                    </div>
                    {/* Two lines rather than an ellipsis. This is the one
                        thing on the card the courier is going to read out to
                        somebody, and half an address is no address. */}
                    <p className="line-clamp-2 text-ink">{stop.address_line}</p>
                    <p className="truncate text-[length:var(--text-small)] text-ink-soft">
                      {num(stop.items_count)} {t.items}
                      {stop.delivery_window ? ` · ${stop.delivery_window}` : ""}
                    </p>
                  </div>
                </div>

                <Button
                  className="mt-3 w-full lg:mt-0 lg:w-auto lg:shrink-0"
                  variant="primary"
                  size="lg"
                  disabled={take.isPending}
                  onClick={() =>
                    take.mutate(stop, {
                      onSuccess: () => navigate(`/orders/${stop.id}`),
                    })
                  }
                >
                  <Plus />
                  {take.isPending ? t.taking : t.take}
                </Button>
              </article>
            ))}
          </div>
        )}
      </Async>
    </div>
  )
}
