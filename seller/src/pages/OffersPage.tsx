import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Boxes, Crown, Lock, Pencil } from "lucide-react"
import { api } from "@/api/client"
import type { Offer } from "@/api/types"
import { Empty, Failed, Loading, Panel, Row } from "@/components/Card"
import { PageHead } from "@/components/Shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogPanel } from "@/components/ui/dialog"
import { FieldError, Hint, Input, Label } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { money } from "@/lib/utils"

export const OFFERS = ["offers"]

/**
 * What I sell and for how much — and the one thing on this screen that is not
 * mine to change.
 *
 * The price is the seller's: one card can carry several sellers' offers and
 * the cheapest one with stock wins the shop. **The count is not.** It is the
 * sum of the warehouse's movement ledger, and a seller who could type into it
 * would be promising goods nobody has received.
 *
 * So the count is shown and cannot be edited, and the screen says why in
 * words rather than leaving a greyed-out box for somebody to keep clicking.
 * A field a person cannot use and is not told about is a field they will
 * report as broken.
 */
export function OffersPage() {
  const [editing, setEditing] = React.useState<Offer | null>(null)

  const query = useQuery({
    queryKey: OFFERS,
    queryFn: () => api<Offer[]>("/staff/offers"),
  })

  const rows = query.data ?? []
  const winning = rows.filter((row) => row.is_winner).length
  const paused = rows.filter((row) => !row.active).length

  return (
    <>
      <PageHead
        title="Takliflarim"
        hint="Narx sizning, qoldiq omborning. Bir kartochkani bir nechta sotuvchi sotadi — eng arzon va qoldig'i bor taklif do'konda ko'rinadi."
      />

      <Panel
        title={`${rows.length} ta taklif`}
        hint={
          rows.length
            ? `${winning} tasi do'konda yetakchi${paused ? ` · ${paused} tasi to'xtatilgan` : ""}`
            : undefined
        }
      >
        {query.isPending ? <Loading /> : null}
        {query.error ? (
          <Failed error={query.error} onRetry={() => void query.refetch()} />
        ) : null}
        {!query.isPending && !query.error && rows.length === 0 ? (
          <Empty
            title="Hali taklifingiz yo'q"
            hint="Taklif — mavjud kartochkaga o'z narxingizni qo'yish. Katalogda kerakli mahsulot bo'lmasa, uni taklif qilish mumkin — administrator ko'rib chiqadi."
          />
        ) : null}

        {rows.map((offer) => (
          <Row key={offer.id}>
            <div className="min-w-[14rem] flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[16px] font-medium text-ink">{offer.product_title}</p>
                {offer.is_winner ? (
                  <Badge tone="good">
                    <Crown className="size-3.5" />
                    Do'konda
                  </Badge>
                ) : null}
                {offer.active ? null : <Badge tone="neutral">To'xtatilgan</Badge>}
              </div>
              {offer.variants.length ? (
                <p className="mt-0.5 text-[13px] text-ink-faint">
                  {offer.variants.length} ta variant
                </p>
              ) : null}
            </div>

            <div className="w-28 text-right">
              <p className="tabular text-[18px] font-semibold text-ink">
                {money(offer.price)}
              </p>
              {offer.old_price ? (
                <p className="tabular text-[13px] text-ink-faint line-through">
                  {money(offer.old_price)}
                </p>
              ) : null}
            </div>

            {/* Read-only, and labelled as somebody else's. The lock is not
                decoration: it is the answer to "why can't I type here". */}
            <div className="w-32 text-right">
              <p className="text-[13px] text-ink-soft">
                <Lock className="mr-1 inline size-3 align-[-1px]" />
                Javonda
              </p>
              <p
                className={
                  offer.stock_left > 0
                    ? "tabular text-[18px] font-semibold text-ink"
                    : "tabular text-[18px] font-semibold text-danger"
                }
              >
                {offer.stock_left}
              </p>
            </div>

            <Button size="sm" onClick={() => setEditing(offer)}>
              <Pencil />
              Narxni o'zgartirish
            </Button>
          </Row>
        ))}

        {rows.length ? (
          <p className="flex items-start gap-2 border-t border-line-soft px-5 py-3 text-[13px] text-ink-soft">
            <Boxes className="mt-0.5 size-4 shrink-0 text-ink-faint" />
            <span>
              <span className="font-medium text-ink">Qoldiqni tahrirlash yo'q — bu ataylab.</span>{" "}
              Javondagi son ombor jurnalining yig'indisi: har bir kirim va chiqim
              nomi va sababi bilan yozilgan. Ko'paytirish uchun{" "}
              <span className="font-medium text-ink">partiya e'lon qiling</span> —
              ombor qabul qilganda son o'zi o'sadi. Sanoq noto'g'ri ko'rinsa
              «Qoldiq» sahifasida harakatlarni ko'rib, omborga murojaat qiling.
            </span>
          </p>
        ) : null}
      </Panel>

      {editing ? (
        <EditPrice offer={editing} onClose={() => setEditing(null)} />
      ) : null}
    </>
  )
}

function EditPrice({ offer, onClose }: { offer: Offer; onClose: () => void }) {
  const [price, setPrice] = React.useState(String(offer.price))
  const [oldPrice, setOldPrice] = React.useState(String(offer.old_price ?? ""))
  const [active, setActive] = React.useState(offer.active)

  const save = useAction<void, Offer>({
    run: () =>
      api<Offer>(`/staff/offers/${offer.id}`, {
        method: "PATCH",
        json: {
          price: Number(price) || 0,
          // Nought means "no struck-through price", which the API reads as a
          // different statement from leaving the field out.
          old_price: oldPrice.trim() ? Number(oldPrice) || 0 : 0,
          active,
        },
      }),
    invalidate: [OFFERS, ["dashboard"]],
    success: "Saqlandi — do'kondagi narx yangilandi",
    onDone: onClose,
  })

  const value = Number(price) || 0
  const struck = oldPrice.trim() ? Number(oldPrice) || 0 : 0
  const badDiscount = struck > 0 && struck <= value
  const discount = struck > value ? Math.round(((struck - value) / struck) * 100) : 0

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        title="Narxni o'zgartirish"
        description={offer.product_title}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Bekor qilish</Button>
            </DialogClose>
            <Button
              variant="primary"
              disabled={value <= 0 || badDiscount || save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? "Saqlanmoqda…" : "Saqlash"}
            </Button>
          </>
        }
      >
        <div className="space-y-4 pb-3">
          <div className="space-y-1.5">
            <Label htmlFor="price">Narx (so'm)</Label>
            <Input
              id="price"
              type="number"
              min={1}
              step={1000}
              autoFocus
              className="tabular text-[18px]"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
            />
            <Hint>
              Hozir: {money(offer.price)}. Har bir o'zgarish nomingiz bilan
              yozib qo'yiladi.
            </Hint>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="old-price">Chizilgan narx (ixtiyoriy)</Label>
            <Input
              id="old-price"
              type="number"
              min={0}
              step={1000}
              className="tabular"
              value={oldPrice}
              placeholder="yo'q"
              onChange={(event) => setOldPrice(event.target.value)}
            />
            {badDiscount ? (
              <FieldError>
                Chizilgan narx joriy narxdan katta bo'lishi kerak — aks holda
                chegirma emas.
              </FieldError>
            ) : discount ? (
              <Hint>
                Mijoz <span className="font-medium text-good">−{discount}%</span> deb
                ko'radi.
              </Hint>
            ) : (
              <Hint>Bo'sh qoldirilsa chegirma ko'rsatilmaydi.</Hint>
            )}
          </div>

          <label className="flex items-start gap-3 rounded-lg border border-line px-3 py-3">
            <input
              type="checkbox"
              className="mt-1 size-4"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />
            <span>
              <span className="block text-[15px] font-medium text-ink">
                Sotuvda
              </span>
              <span className="block text-[13px] text-ink-soft">
                O'chirilsa taklif narx yarishida qatnashmaydi va do'konda
                ko'rinmaydi. Tovar javonda qoladi — saqlash haqi hisoblanishda
                davom etadi.
              </span>
            </span>
          </label>

          {/* Said here as well as on the list, because this is the dialog
              somebody opens looking for the stock field. */}
          <p className="rounded-lg bg-line-soft/70 px-3 py-2.5 text-[13px] text-ink-soft">
            <Lock className="mr-1 inline size-3.5 align-[-2px]" />
            Bu yerda qoldiq yo'q. Javondagi{" "}
            <span className="tabular font-medium text-ink">{offer.stock_left}</span> —
            ombor jurnalining yig'indisi, uni faqat kirim va chiqim
            o'zgartiradi.
          </p>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
