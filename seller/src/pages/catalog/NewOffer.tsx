import * as React from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ApiError, api } from "@/api/client"
import { AlertCircle, Check, CheckCheck, Info, Users } from "lucide-react"
import type { CatalogCard, CatalogCardDetail, Offer } from "@/api/types"
import { Loading } from "@/components/Card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogPanel } from "@/components/ui/dialog"
import { FieldError, Hint, Input, Label } from "@/components/ui/field"
import { CATALOG } from "@/pages/CatalogPage"
import { useAction } from "@/lib/mutate"
import { money, said } from "@/lib/utils"

/**
 * Putting a price on a card — the cabinet's most important new screen.
 *
 * Two rules of the model shape all of it, and both are stated here rather
 * than left to be discovered.
 *
 * **An offer must cover the whole card.** The leaves — the sizes of a product
 * that has sizes, its colours otherwise — all have to be named, because an
 * offer covering half a card leaves the rest of it without figures. The API
 * refuses a partial list with a 422 that names what is missing. This screen
 * shows the same thing *in advance*: every leaf is listed, the button stays
 * disabled until they are all ticked, and the ones still needed are named.
 * A form that lets somebody submit and then explains has wasted their time.
 *
 * **A new offer starts at nothing.** Stock comes from the warehouse's ledger,
 * so a fresh offer holds zero and does not win the card until goods are
 * booked in. That is not a failure to explain away afterwards; it is said on
 * the way in and again on the way out.
 */
export function NewOffer({
  card,
  onClose,
}: {
  card: CatalogCard
  onClose: () => void
}) {
  const navigate = useNavigate()
  const [price, setPrice] = React.useState("")
  const [oldPrice, setOldPrice] = React.useState("")
  const [chosen, setChosen] = React.useState<Set<number>>(new Set())
  const [saved, setSaved] = React.useState<Offer | null>(null)
  const [clash, setClash] = React.useState<string | null>(null)

  const detail = useQuery({
    queryKey: [...CATALOG, "card", card.id],
    queryFn: () => api<CatalogCardDetail>(`/staff/catalog/browse/${card.id}`),
  })

  const full = detail.data
  const leaves = React.useMemo(
    () => (full?.variants ?? []).filter((v) => v.is_leaf),
    [full],
  )

  // Every leaf ticked by default. Naming all of them is the only accepted
  // shape, so starting there is starting at the answer; unticking one is how
  // somebody discovers the rule, which is the right way round.
  React.useEffect(() => {
    if (full) setChosen(new Set(full.leaf_ids))
  }, [full])

  const missing = leaves.filter((v) => !chosen.has(v.id))
  const value = Number(price) || 0
  const struck = oldPrice.trim() ? Number(oldPrice) || 0 : 0
  const badDiscount = struck > 0 && struck <= value
  const ready = value > 0 && !badDiscount && missing.length === 0

  const create = useAction<void, Offer>({
    run: () =>
      api<Offer>("/staff/offers", {
        method: "POST",
        json: {
          product_id: card.id,
          price: value,
          old_price: struck || null,
          variant_ids: full?.leaf_ids ?? [],
        },
      }),
    invalidate: [CATALOG, ["offers"], ["shop"]],
    success: "Narx qo'yildi",
    onDone: (offer) => setSaved(offer),
  })

  // The one refusal worth catching rather than only toasting: a seller who
  // already sells this wants to be sent to the price they set, not told off.
  async function submit() {
    setClash(null)
    try {
      const offer = await create.mutateAsync()
      void offer
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setClash(error.message)
    }
  }

  if (saved) {
    return <Placed card={card} offer={saved} onClose={onClose} />
  }

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        className="w-[min(94vw,38rem)]"
        title="Narx qo'yish"
        description={card.title}
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Bekor qilish</Button>
            </DialogClose>
            <Button
              variant="primary"
              disabled={!ready || create.isPending}
              onClick={() => void submit()}
            >
              {create.isPending ? "Saqlanmoqda…" : "Narxni qo'yish"}
            </Button>
          </>
        }
      >
        {detail.isPending ? <Loading lines={4} /> : null}

        {full ? (
          <div className="space-y-5 pb-3">
            {clash ? (
              <div className="rounded-lg border border-warn/30 bg-warn-soft px-4 py-3">
                <p className="flex items-start gap-2 text-[14px] text-ink">
                  <AlertCircle className="mt-0.5 size-4 shrink-0 text-warn" />
                  <span>
                    <span className="font-semibold">{clash}</span> Narxni
                    o'zgartirmoqchi bo'lsangiz, mavjud narxni tahrirlang —
                    ikkinchi marta qo'yish kerak emas.
                  </span>
                </p>
                <Button
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    onClose()
                    navigate("/offers")
                  }}
                >
                  Narxlarimga o'tish
                </Button>
              </div>
            ) : null}

            {/* What the card already goes for. Public anyway, and the number
                somebody actually prices against. */}
            <div className="flex flex-wrap items-end justify-between gap-4 rounded-lg bg-line-soft/70 px-4 py-3">
              <div>
                <p className="text-[13px] text-ink-soft">Do'kondagi narx</p>
                <p className="tabular text-[20px] font-semibold text-ink">
                  {money(full.price)} <span className="text-[14px] font-normal">so'm</span>
                </p>
              </div>
              <div className="text-right">
                <p className="flex items-center justify-end gap-1 text-[13px] text-ink-soft">
                  <Users className="size-3.5" />
                  {full.offers.length} sotuvchi
                </p>
                {full.offers.length ? (
                  <p className="tabular text-[13px] text-ink-faint">
                    {money(Math.min(...full.offers.map((o) => o.price)))} —{" "}
                    {money(Math.max(...full.offers.map((o) => o.price)))}
                  </p>
                ) : (
                  <p className="text-[13px] text-ink-faint">hali hech kim yo'q</p>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-4">
              <div className="min-w-[10rem] flex-1 space-y-1.5">
                <Label htmlFor="price">Narxim (so'm)</Label>
                <Input
                  id="price"
                  type="number"
                  min={1}
                  step={1000}
                  autoFocus
                  className="tabular text-[18px]"
                  value={price}
                  placeholder={String(full.price)}
                  onChange={(event) => setPrice(event.target.value)}
                />
                {value > 0 && full.offers.length ? (
                  value < Math.min(...full.offers.map((o) => o.price)) ? (
                    <Hint className="text-good">
                      Eng arzon narx bo'ladi — qoldiq kelganda kartochkani
                      oladi.
                    </Hint>
                  ) : (
                    <Hint>
                      Hozirgi eng arzoni{" "}
                      {money(Math.min(...full.offers.map((o) => o.price)))} —
                      kartochkani olish uchun undan past bo'lishi kerak.
                    </Hint>
                  )
                ) : null}
              </div>
              <div className="min-w-[10rem] flex-1 space-y-1.5">
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
                    Chizilgan narx joriy narxdan katta bo'lishi kerak.
                  </FieldError>
                ) : struck > value ? (
                  <Hint className="text-good">
                    Mijoz −{Math.round(((struck - value) / struck) * 100)}% deb
                    ko'radi.
                  </Hint>
                ) : null}
              </div>
            </div>

            {leaves.length ? (
              <Leaves
                detail={full}
                chosen={chosen}
                missing={missing.map((v) => said(v.label) || `#${v.id}`)}
                onToggle={(id) =>
                  setChosen((set) => {
                    const next = new Set(set)
                    if (next.has(id)) next.delete(id)
                    else next.add(id)
                    return next
                  })
                }
                onAll={() => setChosen(new Set(full.leaf_ids))}
              />
            ) : (
              <p className="rounded-lg bg-line-soft/70 px-4 py-3 text-[14px] text-ink-soft">
                Bu tovarning ranglari va o'lchamlari yo'q — bitta narsa
                sifatida sotiladi va bitta joyda sanaladi.
              </p>
            )}

            {/* Said before, not after. */}
            <p className="flex items-start gap-2 rounded-lg bg-line-soft/70 px-4 py-3 text-[13px] text-ink-soft">
              <Info className="mt-0.5 size-4 shrink-0 text-ink-faint" />
              <span>
                Saqlagandan keyin qoldig'ingiz <span className="font-medium text-ink">nol</span>{" "}
                bo'ladi va narxingiz hali do'konda ko'rinmaydi. Ombor tovarni
                qabul qilganda ko'rinadi — narx qo'yish bilan tovar
                yetkazish alohida qadamlar.
              </span>
            </p>
          </div>
        ) : null}
      </DialogPanel>
    </Dialog>
  )
}

/**
 * Every leaf, and the ones still to tick.
 *
 * Grouped under its colour where there are colours, because "L of the black
 * one" is how the goods are actually counted and a flat list of sizes would
 * lose which colour they belong to.
 */
function Leaves({
  detail,
  chosen,
  missing,
  onToggle,
  onAll,
}: {
  detail: CatalogCardDetail
  chosen: Set<number>
  missing: string[]
  onToggle: (id: number) => void
  onAll: () => void
}) {
  const colours = detail.variants.filter((v) => v.kind === "color")
  const leaves = detail.variants.filter((v) => v.is_leaf)
  const loose = leaves.filter((v) => v.parent_id === null)

  const tick = (id: number, label: string) => (
    <label
      key={id}
      className="flex cursor-pointer items-center gap-2 rounded-lg border border-line px-3 py-1.5 text-[14px] hover:bg-line-soft"
    >
      <input
        type="checkbox"
        className="size-4"
        checked={chosen.has(id)}
        onChange={() => onToggle(id)}
      />
      {said(label) || `#${id}`}
    </label>
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label>
          Variantlar
          <span className="ml-1.5 font-normal text-ink-soft">
            — hammasi belgilanishi shart
          </span>
        </Label>
        {missing.length ? (
          <Button size="sm" onClick={onAll}>
            <CheckCheck />
            Hammasini belgilash
          </Button>
        ) : (
          <Badge tone="good">
            <Check className="size-3.5" />
            {leaves.length} tadan {leaves.length} tasi
          </Badge>
        )}
      </div>

      {colours.length ? (
        <div className="space-y-2">
          {colours.map((colour) => {
            const sizes = leaves.filter((v) => v.parent_id === colour.id)
            return (
              <div key={colour.id} className="rounded-lg border border-line p-3">
                <div className="mb-2 flex items-center gap-2">
                  {colour.value ? (
                    <span
                      className="size-4 shrink-0 rounded-full border border-line"
                      style={{ background: colour.value }}
                      aria-hidden
                    />
                  ) : null}
                  <span className="text-[14px] font-medium text-ink">
                    {said(colour.label) || `#${colour.id}`}
                  </span>
                  {colour.is_leaf ? null : (
                    <span className="text-[13px] text-ink-faint">
                      — sanoq o'lchamlarda
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {colour.is_leaf
                    ? tick(colour.id, colour.label)
                    : sizes.map((size) => tick(size.id, size.label))}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          {loose.map((v) => tick(v.id, v.label))}
        </div>
      )}

      {/* The 422's own sentence, said before the request instead of after. */}
      {missing.length ? (
        <p className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn-soft px-4 py-3 text-[14px] text-ink">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-warn" />
          <span>
            <span className="font-semibold">
              {missing.length} variant belgilanmagan:
            </span>{" "}
            {missing.slice(0, 10).join(", ")}
            {missing.length > 10 ? "…" : ""}. Narx kartochkaning hammasini
            qamrashi kerak — yarmini qamragan narx qolgan qismini
            sanoqsiz qoldiradi.
          </span>
        </p>
      ) : null}
    </div>
  )
}

/**
 * What happened, and what has not happened yet.
 *
 * The offer exists and holds nothing. Closing the dialog on a success toast
 * would leave somebody expecting to see their price in the shop and finding
 * it absent — so the next step is spelt out with the door to it.
 */
function Placed({
  card,
  offer,
  onClose,
}: {
  card: CatalogCard
  offer: Offer
  onClose: () => void
}) {
  const navigate = useNavigate()
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        title="Narx qo'yildi"
        description={card.title}
        footer={
          <>
            <Button variant="ghost" onClick={onClose}>
              Katalogda davom etish
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                onClose()
                navigate("/supplies")
              }}
            >
              Partiya e'lon qilish
            </Button>
          </>
        }
      >
        <div className="space-y-4 pb-3">
          <div className="flex items-end justify-between gap-4 rounded-lg bg-brand-soft px-4 py-3">
            <div>
              <p className="text-[13px] text-brand-ink">Narxingiz</p>
              <p className="tabular text-[22px] font-semibold text-brand-ink">
                {money(offer.price)} <span className="text-[14px] font-normal">so'm</span>
              </p>
            </div>
            <div className="text-right">
              <p className="text-[13px] text-brand-ink">Javonda</p>
              <p className="tabular text-[22px] font-semibold text-danger">
                {offer.stock_left}
              </p>
            </div>
          </div>

          <p className="text-[15px] text-ink">
            Qoldiq <span className="font-semibold">nol</span>, shuning uchun bu
            narxingiz hozircha do'kon kartochkasini{" "}
            <span className="font-semibold">olmaydi</span>.
          </p>
          <p className="text-[14px] text-ink-soft">
            Bu xato emas — model shunday ishlaydi. Javondagi son ombor
            jurnalining yig'indisi: siz yozadigan raqam emas, kirim va chiqim
            natijasi. Tovar yuborish uchun partiya e'lon qiling; ombor
            sanaganda son o'sadi va narxingiz yarishda qatnashadi.
          </p>
          <p className="text-[14px] text-ink-soft">
            Narxni keyin ham o'zgartirasiz — «Narxlarim» sahifasida.
          </p>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
