import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { PackageCheck, Truck } from "lucide-react"
import { api } from "@/api/client"
import type { Category, Listing, ListingCreateIn } from "@/api/types"
import { Dialog, DialogPanel } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select, Textarea } from "@/components/ui/field"
import { useAction } from "@/lib/mutate"
import { money } from "@/lib/utils"
import { Images, type Picked } from "@/pages/product/Images"
import { newColor, Variants, type ColorRow } from "@/pages/product/Variants"
import { LISTINGS } from "@/pages/ProductsPage"

/**
 * Adding a product: one form, and at the end of it the warehouse is expecting
 * a box.
 *
 * The seller's own product, from end to end — the name, the photographs, the
 * price they set, the colours and sizes they have, and how many of each is on
 * its way in. One request, because the alternative is six (create the card,
 * post each image, post each colour, post each size, open the offer, declare
 * the batch) and each of those is a chance to be the last one that worked.
 *
 * **The quantities are a declaration.** They become declared amounts on a
 * batch, and the shelf does not move until the warehouse counts the box. The
 * form says so in the words a seller uses, because "qoldiq" here would be a
 * promise the software does not keep.
 *
 * What it deliberately does not have: a SKU field. A seller does not think in
 * stock codes and should not have to invent a unique one — the backend makes
 * it from the shop and the product id.
 */
export function NewProduct({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = React.useState("")
  const [subtitle, setSubtitle] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [category, setCategory] = React.useState("")
  const [price, setPrice] = React.useState("")
  const [weight, setWeight] = React.useState("")
  const [images, setImages] = React.useState<Picked[]>([])
  const [colors, setColors] = React.useState<ColorRow[]>(() => [newColor()])
  const [saved, setSaved] = React.useState<Listing | null>(null)

  const categories = useQuery({
    queryKey: ["categories", "flat"],
    queryFn: () => api<Category[]>("/categories"),
  })

  const uploading = images.some((i) => i.mediaUrl === null && !i.error)
  const broken = images.some((i) => i.error)
  const ready =
    title.trim().length >= 2 &&
    Boolean(category) &&
    Number(price) > 0 &&
    images.some((i) => i.mediaUrl) &&
    !uploading &&
    !broken

  const declared = colors.reduce(
    (sum, c) => sum + c.sizes.reduce((n, s) => n + (Number(s.quantity) || 0), 0),
    0,
  )

  const create = useAction<void, Listing>({
    run: () =>
      api<Listing>("/staff/catalog/listings", {
        method: "POST",
        json: body(),
      }),
    invalidate: [LISTINGS, ["supplies"], ["offers"]],
    onDone: (listing) => setSaved(listing),
  })

  function body(): ListingCreateIn {
    return {
      title: title.trim(),
      subtitle: subtitle.trim(),
      description: description.trim(),
      category_slug: category,
      price: Number(price),
      weight_grams: Number(weight) || 0,
      // Only the pictures that made it. A failed one blocks the button, so
      // this filter is belt and braces rather than the rule.
      images: images.map((i) => i.mediaUrl).filter((u): u is string => Boolean(u)),
      colors: colors
        .filter((c) => c.label.trim())
        .map((c) => ({
          label: c.label.trim(),
          value: c.value.trim(),
          image_url: c.imageUrl,
          sizes: c.sizes
            .filter((s) => s.label.trim())
            .map((s) => ({
              label: s.label.trim(),
              value: "",
              quantity: Number(s.quantity) || 0,
            })),
        })),
    }
  }

  if (saved) return <Sent listing={saved} onClose={onClose} />

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        className="w-[min(96vw,54rem)]"
        title="Yangi mahsulot"
        description="Saqlaganingizda omborga sizning partiyangiz bo'lib tushadi. Ombor sanab qabul qilgach, mahsulot ilovada paydo bo'ladi."
        footer={
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Hint>
              {declared > 0
                ? `Omborga ${declared} dona kelayotgani e'lon qilinadi`
                : "Soni kiritilmagan — partiya ochilmaydi"}
            </Hint>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onClose}>
                Bekor qilish
              </Button>
              <Button
                variant="primary"
                disabled={!ready || create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Saqlanmoqda…" : "Saqlash va omborga yuborish"}
              </Button>
            </div>
          </div>
        }
      >
        <div className="space-y-6 pb-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="np-title">Mahsulot nomi</Label>
              <Input
                id="np-title"
                value={title}
                placeholder="Oversize futbolka, 100% paxta"
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>

            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="np-sub">Qisqa izoh</Label>
              <Input
                id="np-sub"
                value={subtitle}
                placeholder="Yumshoq, kalin trikotaj"
                onChange={(e) => setSubtitle(e.target.value)}
              />
            </div>

            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="np-desc">Tavsif</Label>
              <Textarea
                id="np-desc"
                value={description}
                placeholder="Mato, parvarishi, o'lcham jadvali — xaridor nimani bilishi kerak."
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="np-cat">Turkum</Label>
              <Select
                id="np-cat"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">Tanlang…</option>
                {(categories.data ?? []).map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name}
                  </option>
                ))}
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="np-price">Narxim (so'm)</Label>
              <Input
                id="np-price"
                value={price}
                inputMode="numeric"
                placeholder="149000"
                onChange={(e) => setPrice(e.target.value.replace(/[^0-9]/g, ""))}
              />
              {Number(price) > 0 ? (
                <Hint>{money(Number(price))} so'm</Hint>
              ) : (
                <Hint>Narxni o'zingiz belgilaysiz.</Hint>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="np-weight">Bir dona og'irligi (gramm)</Label>
              <Input
                id="np-weight"
                value={weight}
                inputMode="numeric"
                placeholder="300"
                onChange={(e) => setWeight(e.target.value.replace(/[^0-9]/g, ""))}
              />
              {/* Not cosmetic: the weight band decides the handling fee and
                  the storage rate. Left empty it is charged as one kilogram,
                  so saying 300 g is cheaper than saying nothing. */}
              <Hint>
                Yig'ish haqi va saqlash stavkasi og'irlik guruhiga qarab
                olinadi. Bo'sh qoldirsangiz 1 kg deb hisoblanadi.
              </Hint>
            </div>
          </div>

          <Images value={images} onChange={setImages} />

          <Variants value={colors} onChange={setColors} images={images} />
        </div>
      </DialogPanel>
    </Dialog>
  )
}

/**
 * What happens next, said plainly.
 *
 * The batch code is the thing to keep: it is the code the warehouse looks for,
 * and it is ours rather than the seller's own label — a seller's reference may
 * repeat, may be missing, and two sellers may use the same one on the same day.
 */
function Sent({ listing, onClose }: { listing: Listing; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogPanel
        title="Saqlandi"
        description={listing.title}
        footer={
          <Button variant="primary" onClick={onClose}>
            Yopish
          </Button>
        }
      >
        <div className="space-y-4 pb-3">
          <div className="flex items-center justify-between gap-3 rounded-lg bg-brand-soft px-4 py-3">
            <span className="text-[14px] text-brand-ink">Partiya kodi</span>
            <span className="font-mono text-[15px] font-semibold text-brand-ink">
              {listing.supply_code ?? "—"}
            </span>
          </div>

          <ol className="space-y-3">
            <Step icon={<Truck className="size-4" />} now>
              Tovarni omborga yuborasiz. Qutida shu kod bo'lsin — ombor shuni
              qidiradi.
            </Step>
            <Step icon={<PackageCheck className="size-4" />}>
              Ombor sanab qabul qiladi. Shundan keyin mahsulot ilovada paydo
              bo'ladi va sotiladi.
            </Step>
          </ol>

          <Hint>
            Holatini «Mahsulotlarim»da kuzatasiz: hozir «
            {listing.stage_label}».
          </Hint>
        </div>
      </DialogPanel>
    </Dialog>
  )
}

function Step({
  icon,
  now,
  children,
}: {
  icon: React.ReactNode
  now?: boolean
  children: React.ReactNode
}) {
  return (
    <li className="flex gap-3">
      <span
        className={
          now
            ? "mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-brand text-white"
            : "mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-line-soft text-ink-soft"
        }
      >
        {icon}
      </span>
      <p className="text-[14px] text-ink-soft">{children}</p>
    </li>
  )
}
