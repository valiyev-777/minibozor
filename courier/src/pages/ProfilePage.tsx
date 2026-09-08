import { Package, TriangleAlert, Truck, Wallet } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api } from "@/api/client"
import type { Earnings } from "@/api/types"
import { Async } from "@/ui/states"
import { useCourier } from "@/auth/session"
import { num, som } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * What I have delivered and what it came to.
 *
 * This is the screen a courier opens when they are *not* at a door, and it is
 * the reason the app is worth keeping on a home screen: nobody works a round
 * they cannot count. Three windows rather than one running total — today is
 * what they are doing now, the month is what their rent is measured against,
 * and the lifetime figure is the one that makes a long day feel like it added
 * up to something.
 *
 * **The cash sits apart, and that is the whole layout decision.** Money taken
 * at doors belongs to the office; pay is what the deliveries earned. Put them
 * in one column of figures and a courier reads a total that is not theirs —
 * which is how somebody ends up short at the end of a week. So earnings are
 * one block, the cash is another, and the second one says out loud whose it
 * is.
 *
 * The failed attempts are here and deliberately quiet: a courier who takes
 * the hard addresses should not read this as a mark against them. It is a
 * figure they can point at when an operator asks.
 */
export function ProfilePage() {
  const courier = useCourier()
  const earnings = useQuery({
    queryKey: ["earnings"],
    queryFn: () => api<Earnings>("/courier/earnings"),
  })

  return (
    <div className="space-y-[var(--gap-page)] px-[var(--gap-page)] py-[var(--gap-page)]">
      <header className="flex items-center gap-3">
        <span className="inline-flex size-12 shrink-0 items-center justify-center rounded-full bg-brand-soft text-brand-deep">
          <Truck className="size-6" />
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold text-ink">
            {courier.full_name || t.profile}
          </h1>
          <p className="truncate text-[length:var(--text-small)] text-ink-soft">
            {courier.phone}
          </p>
        </div>
      </header>

      <Async query={earnings} lines={4}>
        {(row) => (
          <div className="space-y-[var(--gap-page)]">
            {/* The pay. The lifetime figure is the big one — the two windows
                beside it are the ones that change during a shift. */}
            <section className="rounded-[var(--radius-panel)] border border-line bg-surface">
              <div className="border-b border-line-soft p-5">
                <p className="text-[length:var(--text-small)] text-ink-soft">
                  {t.earnedTotal}
                </p>
                <p className="tabular text-3xl font-semibold text-ink sm:text-4xl">
                  {som(row.earned_total)}
                </p>
                <p className="mt-1 text-[length:var(--text-micro)] text-ink-faint">
                  {t.perDelivery}: {som(row.fee_per_delivery)} · {t.earningsHint}
                </p>
              </div>
              <dl className="grid grid-cols-2 divide-x divide-line-soft">
                <Figure label={t.earnedToday} value={som(row.earned_today)} />
                <Figure label={t.earnedMonth} value={som(row.earned_month)} />
              </dl>
            </section>

            {/* The count, which is the same story told in parcels. */}
            <section className="rounded-[var(--radius-panel)] border border-line bg-surface">
              <div className="border-b border-line-soft p-5">
                <p className="flex items-center gap-2 text-[length:var(--text-small)] text-ink-soft">
                  <Package className="size-4 shrink-0 text-ink-faint" />
                  {t.deliveredTotal}
                </p>
                <p className="tabular text-3xl font-semibold text-ink sm:text-4xl">
                  {num(row.delivered_total)}
                </p>
              </div>
              <dl className="grid grid-cols-2 divide-x divide-line-soft">
                <Figure label={t.deliveredToday} value={num(row.delivered_today)} />
                <Figure label={t.deliveredMonth} value={num(row.delivered_month)} />
              </dl>
            </section>

            {/* Not earnings, and it says so. Only when there is any: a nought
                here is a sentence about money nobody is carrying. */}
            {row.cash_on_hand > 0 ? (
              <section className="rounded-[var(--radius-panel)] border border-warn/40 bg-warn-soft p-5">
                <p className="flex items-center gap-2 text-[length:var(--text-small)] font-medium text-warn-ink">
                  <Wallet className="size-5 shrink-0" />
                  {t.cashOnHand}
                </p>
                <p className="tabular text-3xl font-semibold text-warn-ink sm:text-4xl">
                  {som(row.cash_on_hand)}
                </p>
                <p className="mt-1 text-[length:var(--text-micro)] text-warn-ink/80">
                  {t.cashOnHandHint}
                </p>
              </section>
            ) : null}

            {row.failed_attempts > 0 ? (
              <p className="flex items-center gap-2 px-1 text-[length:var(--text-small)] text-ink-soft">
                <TriangleAlert className="size-4 shrink-0 text-ink-faint" />
                {t.failedAttempts}: <span className="tabular">{num(row.failed_attempts)}</span>
              </p>
            ) : null}
          </div>
        )}
      </Async>
    </div>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-5">
      <dt className="text-[length:var(--text-small)] text-ink-soft">{label}</dt>
      <dd className="tabular text-lg font-semibold text-ink">{value}</dd>
    </div>
  )
}
