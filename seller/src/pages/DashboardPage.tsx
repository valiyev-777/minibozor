import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { ArrowRight, Crown, Truck, TriangleAlert } from "lucide-react"
import { api } from "@/api/client"
import type { Offer, Supply } from "@/api/types"
import { Failed, Figure, Loading, Panel, Row } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useSeller } from "@/auth/session"
import { money, when } from "@/lib/utils"

/**
 * The screen that answers "is anything wrong" in one look.
 *
 * A seller opens this a couple of times a week, not all day. So it is four
 * figures and two short lists, and every item on it is something to act on:
 * a batch the warehouse has not counted yet, an offer about to run out. A
 * dashboard of numbers nobody can do anything about is a dashboard people
 * stop opening.
 *
 * What it does **not** show is a sales total for the period. That figure lives
 * in a statement, which is generated per settlement period by an admin, and
 * inventing an approximation of it here from the offers would put a number on
 * screen that disagrees with the one somebody is paid against. Better a
 * missing figure than two that differ — see the README for the endpoint that
 * would fix it.
 */
const LOW_STOCK = 5

export function DashboardPage() {
  const seller = useSeller()

  const offers = useQuery({
    queryKey: ["offers"],
    queryFn: () => api<Offer[]>("/staff/offers"),
  })
  const supplies = useQuery({
    queryKey: ["supplies"],
    queryFn: () => api<Supply[]>("/staff/supplies"),
  })

  const rows = offers.data ?? []
  const waiting = (supplies.data ?? []).filter((row) => row.status === "declared")
  const low = rows
    .filter((row) => row.active && row.stock_left <= LOW_STOCK)
    .sort((a, b) => a.stock_left - b.stock_left)
  const winning = rows.filter((row) => row.is_winner)
  const onShelf = rows.reduce((sum, row) => sum + row.stock_left, 0)

  return (
    <>
      <PageHead
        title={seller.full_name ? `Salom, ${seller.full_name}` : "Boshqaruv paneli"}
        hint="Bugun nima e'tibor talab qiladi."
      />

      {offers.error ? (
        <Panel className="mb-5">
          <Failed error={offers.error} onRetry={() => void offers.refetch()} />
        </Panel>
      ) : null}

      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Panel className="px-5 py-4">
          {offers.isPending ? (
            <Loading lines={1} />
          ) : (
            <Figure label="Narxlarim" value={rows.length} />
          )}
        </Panel>
        <Panel className="px-5 py-4">
          {offers.isPending ? (
            <Loading lines={1} />
          ) : (
            <Figure
              label="Do'konda yetakchi"
              value={winning.length}
              tone="good"
              hint="Eng arzon va qoldig'i bor"
            />
          )}
        </Panel>
        <Panel className="px-5 py-4">
          {offers.isPending ? (
            <Loading lines={1} />
          ) : (
            <Figure label="Javonda, jami" value={onShelf} unit="dona" />
          )}
        </Panel>
        <Panel className="px-5 py-4">
          {supplies.isPending ? (
            <Loading lines={1} />
          ) : (
            <Figure
              label="Kutayotgan partiya"
              value={waiting.length}
              tone={waiting.length ? "warn" : "ink"}
            />
          )}
        </Panel>
      </div>

      {/* Two lists, both of them work to be done. */}
      {low.length ? (
        <Panel
          className="mb-5"
          title="Kam qoldi"
          hint={`Sotuvdagi ${low.length} ta narxda ${LOW_STOCK} donadan kam qolgan.`}
          actions={
            <Button size="sm" asChild>
              <Link to="/supplies">
                Partiya e'lon qilish
                <ArrowRight />
              </Link>
            </Button>
          }
        >
          {low.slice(0, 6).map((offer) => (
            <Row key={offer.id}>
              <div className="min-w-[12rem] flex-1">
                <p className="text-[15px] font-medium text-ink">{offer.product_title}</p>
                <p className="tabular text-[13px] text-ink-faint">
                  {money(offer.price)} so'm
                </p>
              </div>
              {offer.is_winner ? (
                <Badge tone="good">
                  <Crown className="size-3.5" />
                  Do'konda
                </Badge>
              ) : null}
              <div className="w-24 text-right">
                <p className="text-[12px] text-ink-faint">Javonda</p>
                <p
                  className={`tabular text-[20px] font-semibold ${
                    offer.stock_left === 0 ? "text-danger" : "text-warn"
                  }`}
                >
                  {offer.stock_left}
                </p>
              </div>
            </Row>
          ))}
          {low.length > 6 ? (
            <p className="border-t border-line-soft px-5 py-3 text-[13px] text-ink-soft">
              Yana {low.length - 6} ta — «Qoldiq» sahifasida hammasi.
            </p>
          ) : null}
        </Panel>
      ) : null}

      {waiting.length ? (
        <Panel
          title="Kutayotgan partiyalar"
          hint="Ombor sanamagunicha javondagi son o'zgarmaydi."
          actions={
            <Button size="sm" asChild>
              <Link to="/supplies">
                Hammasi
                <ArrowRight />
              </Link>
            </Button>
          }
        >
          {waiting.map((supply) => (
            <Row key={supply.id}>
              <Truck className="size-4 shrink-0 text-warn" />
              <div className="min-w-[10rem] flex-1">
                <p className="tabular text-[15px] font-medium text-ink">{supply.code}</p>
                <p className="text-[13px] text-ink-faint">
                  {when(supply.declared_at)} · {supply.lines.length} qator
                </p>
              </div>
              <div className="w-24 text-right">
                <p className="text-[12px] text-ink-faint">E'lon qilingan</p>
                <p className="tabular text-[18px] font-medium text-ink">
                  {supply.lines.reduce((sum, line) => sum + line.declared_quantity, 0)}
                </p>
              </div>
            </Row>
          ))}
        </Panel>
      ) : null}

      {!offers.isPending && rows.length === 0 ? (
        <Panel className="px-5 py-8 text-center">
          <p className="text-[16px] font-medium text-ink">Hali sotuvda hech narsa yo'q</p>
          <p className="mx-auto mt-1 max-w-md text-[14px] text-ink-soft">
            «Mahsulotlarim» — o'z mahsulotingizni qo'shasiz: rasmlari, narxi,
            ranglari va razmerlari. Saqlaganingizda omborga sizning partiyangiz
            bo'lib tushadi; ombor sanab qabul qilgach ilovada paydo bo'ladi.
          </p>
          <div className="mt-4 flex justify-center">
            <Button variant="primary" asChild>
              <Link to="/products">
                Mahsulot qo'shish
                <ArrowRight />
              </Link>
            </Button>
          </div>
        </Panel>
      ) : null}

      {/* Said plainly rather than shown as an empty card: the sales figure
          belongs to a statement and this screen cannot compute it. */}
      <p className="mt-5 flex items-start gap-2 text-[13px] text-ink-soft">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-ink-faint" />
        <span>
          Bu davrdagi savdo va to'lanadigan summa hisobotda bo'ladi — u
          administrator davrni yig'ganda tuziladi. «Hisobotlar» sahifasi
          keyingi bosqichda qo'shiladi; hozircha bu raqamni taxminan
          hisoblamaymiz, chunki u siz to'lov oladigan raqamdan farq qilib
          qolardi.
        </span>
      </p>
    </>
  )
}
