import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Info, Send } from "lucide-react"
import { api } from "@/api/client"
import type { Brand, Category, Proposal } from "@/api/types"
import { Loading } from "@/components/Card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogPanel } from "@/components/ui/dialog"
import { Hint, Input, Label, Textarea } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { CATALOG } from "@/pages/CatalogPage"

/**
 * Suggesting a card the catalogue does not have.
 *
 * **The catalogue belongs to the platform**, and this form is the shape of
 * that. A seller does not open their own copy of a product — one card
 * carrying several sellers' offers is the whole point of the model, and a
 * copy per seller would duplicate the catalogue and leave the warehouse
 * holding the same goods in two places under two names. So what a seller can
 * do is *propose*, and it lands in moderation.
 *
 * Which means the seller does not choose the price a shopper pays here. The
 * `price` field the API requires is the figure a card shows before any offer
 * exists — it is asked for, and labelled as what it is, because leaving it
 * unexplained would have somebody believe they had just set their price.
 */
export function Propose({ onClose }: { onClose: () => void }) {
  const [sku, setSku] = React.useState("")
  const [title, setTitle] = React.useState("")
  const [subtitle, setSubtitle] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [categorySlug, setCategorySlug] = React.useState("")
  const [brandSlug, setBrandSlug] = React.useState("")
  const [price, setPrice] = React.useState("")
  const [sent, setSent] = React.useState<Proposal | null>(null)

  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/categories"),
    staleTime: 5 * 60_000,
  })
  const brands = useQuery({
    queryKey: ["brands"],
    queryFn: () => api<Brand[]>("/brands"),
    staleTime: 5 * 60_000,
  })

  const propose = useAction<void, Proposal>({
    run: () =>
      api<Proposal>("/staff/catalog/proposals", {
        method: "POST",
        json: {
          sku: sku.trim(),
          title: title.trim(),
          subtitle: subtitle.trim(),
          description: description.trim(),
          category_slug: categorySlug,
          brand_slug: brandSlug || null,
          price: Number(price) || 1,
        },
      }),
    invalidate: [CATALOG],
    success: "Taklifingiz moderatsiyaga yuborildi",
    onDone: (row) => setSent(row),
  })

  const ready = sku.trim() && title.trim() && categorySlug && Number(price) > 0

  if (sent) return <Sent proposal={sent} onClose={onClose} />

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        className="w-[min(94vw,38rem)]"
        title="Yo'q tovarni taklif qilish"
        description="Katalogda topilmadi — administrator ko'rib chiqadi"
        footer={
          <>
            <DialogClose asChild>
              <Button variant="ghost">Bekor qilish</Button>
            </DialogClose>
            <Button
              variant="primary"
              disabled={!ready || propose.isPending}
              onClick={() => propose.mutate()}
            >
              <Send />
              {propose.isPending ? "Yuborilmoqda…" : "Moderatsiyaga yuborish"}
            </Button>
          </>
        }
      >
        {categories.isPending ? <Loading lines={3} /> : null}

        <div className="space-y-4 pb-3">
          <p className="flex items-start gap-2 rounded-lg bg-line-soft/70 px-4 py-3 text-[13px] text-ink-soft">
            <Info className="mt-0.5 size-4 shrink-0 text-ink-faint" />
            <span>
              Katalog platformaniki: siz kartochka yaratmaysiz, taklif
              qilasiz. Administrator tasdiqlasa kartochka do'konga chiqadi va
              siz unga o'z narxingizni qo'yasiz — boshqa sotuvchilar ham
              qo'yishi mumkin, bu model shunday.
            </span>
          </p>

          <div className="flex flex-wrap gap-4">
            <div className="min-w-[10rem] flex-1 space-y-1.5">
              <Label htmlFor="p-sku">SKU</Label>
              <Input
                id="p-sku"
                autoFocus
                className="tabular"
                value={sku}
                placeholder="CHORSU-1001"
                onChange={(event) => setSku(event.target.value)}
              />
              <Hint>Yagona bo'lishi kerak — takrorlansa rad etiladi.</Hint>
            </div>
            <div className="w-40 space-y-1.5">
              <Label htmlFor="p-price">Taxminiy narx</Label>
              <Input
                id="p-price"
                type="number"
                min={1}
                step={1000}
                className="tabular"
                value={price}
                placeholder="120000"
                onChange={(event) => setPrice(event.target.value)}
              />
              {/* Not their price. Said so, because a number in a price field
                  reads as a price unless it is contradicted. */}
              <Hint>
                Sizning narxingiz emas — kartochkada taklif kelguncha
                ko'rsatiladigan raqam. Tasdiqlangandan keyin narxni alohida
                qo'yasiz.
              </Hint>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="p-title">Nomi</Label>
            <Input
              id="p-title"
              value={title}
              placeholder="Qo'lbola sopol choynak"
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="p-subtitle">Qisqa izoh</Label>
            <Input
              id="p-subtitle"
              value={subtitle}
              placeholder="Sopol, qo'lda bo'yalgan"
              onChange={(event) => setSubtitle(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="p-description">Tavsif</Label>
            <Textarea
              id="p-description"
              value={description}
              placeholder="Nima ekani, nimadan yasalgani, o'lchamlari…"
              onChange={(event) => setDescription(event.target.value)}
            />
            <Hint>
              To'ldirilgani ko'rib chiqishni tezlashtiradi — administratorga
              nima ekani tushunarli bo'lishi kerak.
            </Hint>
          </div>

          <div className="flex flex-wrap gap-4">
            <div className="min-w-[10rem] flex-1 space-y-1.5">
              <Label htmlFor="p-category">Turkum</Label>
              <select
                id="p-category"
                className="w-full rounded-lg border border-line bg-surface px-3 py-2 pr-8 text-[15px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                value={categorySlug}
                onChange={(event) => setCategorySlug(event.target.value)}
              >
                <option value="">— tanlang —</option>
                {(categories.data ?? []).map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="min-w-[10rem] flex-1 space-y-1.5">
              <Label htmlFor="p-brand">Brend</Label>
              <select
                id="p-brand"
                className="w-full rounded-lg border border-line bg-surface px-3 py-2 pr-8 text-[15px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20"
                value={brandSlug}
                onChange={(event) => setBrandSlug(event.target.value)}
              >
                <option value="">— brendsiz —</option>
                {(brands.data ?? []).map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <p className="text-[13px] text-ink-soft">
            Rasm, ranglar va o'lchamlarni administrator tasdiqlagandan keyin
            qo'shadi. Ular kartochkaning bir qismi, taklifning emas.
          </p>
        </div>
      </DialogPanel>
    </Dialog>
  )
}

/**
 * What happens next, and the one thing this cabinet cannot yet tell them.
 *
 * A proposal goes into moderation and an admin publishes or refuses it with a
 * reason. An approved card turns up in the catalogue, where the seller can
 * find it and price it. A refused one is invisible from here — the endpoint
 * that would list a seller's own proposals and their `moderation_note` does
 * not exist, and inventing local state for it would drift from the server.
 * So the honest thing is to say so.
 */
function Sent({ proposal, onClose }: { proposal: Proposal; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        title="Moderatsiyaga yuborildi"
        description={proposal.title}
        footer={
          <Button variant="primary" onClick={onClose}>
            Yopish
          </Button>
        }
      >
        <div className="space-y-4 pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-brand-soft px-4 py-3">
            <span className="tabular text-[15px] font-medium text-brand-ink">
              {proposal.sku}
            </span>
            <Badge tone="warn">Moderatsiyada</Badge>
          </div>

          {proposal.moderation_note ? (
            <p className="rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-[14px] text-ink">
              <span className="font-semibold text-danger">Izoh:</span>{" "}
              {proposal.moderation_note}
            </p>
          ) : null}

          <p className="text-[15px] text-ink">
            Administrator ko'rib chiqadi. Tasdiqlansa kartochka do'konga
            chiqadi — shundan keyin uni <span className="font-medium">Katalog</span>{" "}
            sahifasida topib, o'z narxingizni qo'yasiz.
          </p>

          {/* Stated rather than faked. */}
          <p className="rounded-lg bg-line-soft/70 px-4 py-3 text-[13px] text-ink-soft">
            Hozircha bu kabinetda yuborilgan takliflar ro'yxati yo'q: rad
            etilgan taklifning sababini o'qish uchun kerakli endpoint hali
            qurilmagan. Tasdiqlangani katalogda o'zi paydo bo'ladi; rad
            etilgani haqida administrator xabar beradi.
          </p>
        </div>
      </DialogPanel>
    </Dialog>
  )
}
