import * as React from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, Coins, Layers, Stamp } from "lucide-react"
import { api } from "@/api/client"
import type { AdminBrand, AdminCategory, AdminProductDetail } from "@/api/types"
import { Page } from "@/components/Layout"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Hint, Input, Label, Select } from "@/components/ui/field"
import { PRODUCT_STATUS, PRODUCT_TONE } from "@/lib/labels"
import { useAction } from "@/lib/mutate"
import { money } from "@/lib/utils"
import { Images } from "@/pages/product/Images"
import { Specs } from "@/pages/product/Specs"
import {
  EMPTY_TEXTS,
  LanguageTabs,
  type Lang,
  type TextField,
  type Texts,
  TextFields,
  translationsPayload,
} from "@/pages/product/TranslatedText"
import { Variants } from "@/pages/product/Variants"

/**
 * Writing a card, and the three things writing a card is not.
 *
 * A new card is created from the text alone and the editor is then sent to
 * this same screen for the rest, because a photograph, a colour and a spec
 * row all hang off an id — there is nothing to attach them to until the card
 * exists. Pretending otherwise would mean holding a whole card in the browser
 * and replaying it on save, and a half-failed replay is a card in a state
 * nobody chose.
 *
 * The seller's side of this is deliberately not shared with it. A seller
 * proposes cards through `POST /staff/catalog/proposals` and is not staff —
 * they never reach this panel, and their form will live in a seller's own
 * account. Abstracting one component to serve both now would be guessing at
 * needs nobody has stated.
 */

const KEY = ["staff", "catalog"]

export function ProductEditPage() {
  const params = useParams()
  const productId = params["id"] === "new" ? null : Number(params["id"])
  return productId === null ? <NewProduct /> : <EditProduct productId={productId} />
}

// --------------------------------------------------------------- pickers

function useCatalogue() {
  const categories = useQuery({
    queryKey: [...KEY, "admin-categories"],
    queryFn: () => api<AdminCategory[]>("/staff/catalog/categories"),
  })
  const brands = useQuery({
    queryKey: [...KEY, "admin-brands"],
    queryFn: () => api<AdminBrand[]>("/staff/catalog/brands"),
  })
  return { categories, brands }
}

function Placement({
  categorySlug,
  brandSlug,
  onCategory,
  onBrand,
}: {
  categorySlug: string
  brandSlug: string
  onCategory: (slug: string) => void
  onBrand: (slug: string) => void
}) {
  const { categories, brands } = useCatalogue()
  const rows = categories.data ?? []
  const bySlug = new Map(rows.map((row) => [row.slug, row]))

  /** "Kiyim va poyabzal → Krossovkalar", so a leaf is not ambiguous. */
  function path(row: AdminCategory): string {
    const parent = row.parent_slug ? bySlug.get(row.parent_slug) : undefined
    return parent ? `${parent.name} → ${row.name}` : row.name
  }

  return (
    <div className="flex gap-2">
      <div className="flex-1 space-y-1">
        <Label htmlFor="p-category">
          Turkum<span className="ml-1 text-danger">*</span>
        </Label>
        <Select
          id="p-category"
          value={categorySlug}
          onChange={(event) => onCategory(event.target.value)}
        >
          <option value="">— tanlang —</option>
          {[...rows]
            .sort((a, b) => path(a).localeCompare(path(b)))
            .map((row) => (
              <option key={row.slug} value={row.slug}>
                {path(row)}
              </option>
            ))}
        </Select>
        <Hint>
          Bu ro'yxat qatordagi o'zbekchani ko'rsatadi — mijoz endpointi tilga
          qarab tarjima qaytaradi, muharrirga esa asl matn kerak.
        </Hint>
      </div>
      <div className="flex-1 space-y-1">
        <Label htmlFor="p-brand">Brend</Label>
        <Select
          id="p-brand"
          value={brandSlug}
          onChange={(event) => onBrand(event.target.value)}
        >
          <option value="">— brendsiz —</option>
          {(brands.data ?? []).map((row) => (
            <option key={row.slug} value={row.slug}>
              {row.name}
            </option>
          ))}
        </Select>
      </div>
    </div>
  )
}

// ------------------------------------------------------------- what is not here

/**
 * The three fields an editor will look for and not find.
 *
 * Each has an owner, and the owner is not this form: a price belongs to an
 * offer, a count to the movement ledger, a status to a decision somebody made
 * with a reason attached. Leaving the space blank would send somebody hunting
 * through five tabs for a field that was never going to be here; saying where
 * each one lives costs a paragraph and saves the hunt.
 */
function Elsewhere({ product }: { product: AdminProductDetail | null }) {
  const items = [
    {
      icon: Coins,
      title: "Narx",
      where: "Sotuvchi belgilaydi",
      why:
        "Bir kartochkani bir nechta sotuvchi sotadi va har biri o'z narxini " +
        "qo'yadi. Kartochkadagi raqam — eng arzon narxning nusxasi.",
      now: product
        ? product.offer_count
          ? `${money(product.price)} · ${product.offer_count} sotuvchi`
          : "Narx qo'yilmagan — ko'rsatilayotgani boshlang'ich raqam"
        : null,
    },
    {
      icon: Layers,
      title: "Qoldiq",
      where: "Harakatlar jurnalida — ombor kirim qiladi",
      why:
        "Javondagi son yozilmaydi, u harakatlar yig'indisi. Shuning uchun " +
        "noto'g'ri ko'ringan sanoq — bahs emas, nomi va sababi bor ro'yxat.",
      now: product ? `Javonda ${product.stock_left}` : null,
    },
    {
      icon: Stamp,
      title: "Holat",
      where: "Moderatsiya ekranida — sababi bilan",
      why:
        "E'lon qilish yoki rad etish — qaror, va rad etishning sababi " +
        "sotuvchiga o'qiladi. Shuning uchun uning o'z eshigi bor.",
      now: product ? PRODUCT_STATUS[product.status] : null,
    },
  ]

  return (
    <section className="rounded-lg border border-line bg-line-soft/40 px-3 py-2.5">
      <h2 className="text-[13px] font-medium text-ink">Bu formada nima yo'q</h2>
      <Hint>Uchtasining ham egasi bor, va u shu forma emas.</Hint>
      <dl className="mt-2 grid gap-2 sm:grid-cols-3">
        {items.map((item) => (
          <div key={item.title} className="rounded border border-line bg-surface px-2.5 py-2">
            <dt className="flex items-center gap-1.5 text-[13px] font-medium text-ink">
              <item.icon className="size-3.5 shrink-0 text-ink-faint" />
              {item.title}
            </dt>
            <dd className="mt-0.5 text-[12px] text-brand">{item.where}</dd>
            <dd className="mt-1 text-[12px] text-ink-soft">{item.why}</dd>
            {item.now ? (
              <dd className="tabular mt-1 text-[12px] text-ink-faint">Hozir: {item.now}</dd>
            ) : null}
          </div>
        ))}
      </dl>
    </section>
  )
}

// ------------------------------------------------------------------ creating

function NewProduct() {
  const navigate = useNavigate()
  const [texts, setTexts] = React.useState<Record<Lang, Texts>>({
    uz: { ...EMPTY_TEXTS },
    ru: { ...EMPTY_TEXTS },
    en: { ...EMPTY_TEXTS },
  })
  const [lang, setLang] = React.useState<Lang>("uz")
  const [sku, setSku] = React.useState("")
  const [categorySlug, setCategorySlug] = React.useState("")
  const [brandSlug, setBrandSlug] = React.useState("")
  const [price, setPrice] = React.useState("100000")

  function edit(language: Lang, field: TextField, value: string) {
    setTexts((all) => ({ ...all, [language]: { ...all[language], [field]: value } }))
  }

  const create = useAction<void, AdminProductDetail>({
    run: () =>
      api<AdminProductDetail>("/staff/catalog/products", {
        method: "POST",
        json: {
          sku: sku.trim(),
          title: texts.uz.title.trim(),
          subtitle: texts.uz.subtitle.trim(),
          description: texts.uz.description.trim(),
          badge: texts.uz.badge.trim() || null,
          warranty: texts.uz.warranty.trim() || null,
          category_slug: categorySlug,
          brand_slug: brandSlug || null,
          price: Number(price) || 1,
          translations: translationsPayload(texts),
        },
      }),
    invalidate: [KEY],
    success: "Kartochka yaratildi — endi rasm va variantlarni qo'shing",
    // Straight on to the full editor: a photograph and a colour hang off an
    // id, so there was nothing to attach them to until now.
    onDone: (card) => navigate(`/catalog/products/${card.id}`, { replace: true }),
  })

  const ready = sku.trim() && texts.uz.title.trim() && categorySlug

  return (
    <Page
      title="Yangi kartochka"
      hint="Qoralama sifatida yaratiladi. E'lon qilish — alohida qaror, moderatsiya ekranida."
      actions={
        <div className="flex items-center gap-1.5">
          <Button onClick={() => navigate("/catalog")}>
            <ArrowLeft />
            Katalog
          </Button>
          <Button
            variant="primary"
            disabled={!ready || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "Yuborilmoqda…" : "Yaratish"}
          </Button>
        </div>
      }
    >
      <div className="max-w-4xl space-y-3">
        <section className="rounded-lg border border-line bg-surface px-3 py-3">
          <div className="mb-3 flex gap-2">
            <div className="w-56 space-y-1">
              <Label htmlFor="p-sku">
                SKU<span className="ml-1 text-danger">*</span>
              </Label>
              <Input
                id="p-sku"
                autoFocus
                className="tabular"
                value={sku}
                placeholder="MB-1001"
                onChange={(event) => setSku(event.target.value)}
              />
              <Hint>Yagona bo'lishi kerak.</Hint>
            </div>
            <div className="w-48 space-y-1">
              <Label htmlFor="p-price">Boshlang'ich raqam</Label>
              <Input
                id="p-price"
                type="number"
                min={1}
                step={1000}
                className="tabular"
                value={price}
                onChange={(event) => setPrice(event.target.value)}
              />
              {/* Not the price. The API needs a number so a card with no
                  offers shows something rather than a nought, and the first
                  offer overwrites it. */}
              <Hint>
                Narx emas — sotuvchi narx qo'yguncha ko'rsatiladigan raqam.
                Birinchi narx uni almashtiradi.
              </Hint>
            </div>
          </div>

          <Placement
            categorySlug={categorySlug}
            brandSlug={brandSlug}
            onCategory={setCategorySlug}
            onBrand={setBrandSlug}
          />
        </section>

        <section className="rounded-lg border border-line bg-surface px-3 py-3">
          <div className="mb-3">
            <LanguageTabs lang={lang} onChange={setLang} texts={texts} />
          </div>
          <TextFields lang={lang} texts={texts} onChange={edit} idPrefix="new" />
        </section>

        <Elsewhere product={null} />

        <p className="text-[12px] text-ink-faint">
          Rasm, rang va o'lchamlar, xususiyatlar — kartochka yaratilgandan
          keyin. Ularning hammasi kartochkaning id'siga bog'lanadi, shuning
          uchun oldin kartochka bo'lishi kerak.
        </p>
      </div>
    </Page>
  )
}

// ------------------------------------------------------------------- editing

function EditProduct({ productId }: { productId: number }) {
  const navigate = useNavigate()
  const [lang, setLang] = React.useState<Lang>("uz")
  const [texts, setTexts] = React.useState<Record<Lang, Texts> | null>(null)
  const [categorySlug, setCategorySlug] = React.useState("")
  const [brandSlug, setBrandSlug] = React.useState("")
  const [flags, setFlags] = React.useState({
    is_original: true,
    free_delivery: true,
    next_day_delivery: true,
  })

  const key = [...KEY, "product", productId]
  const query = useQuery({
    queryKey: key,
    queryFn: () => api<AdminProductDetail>(`/staff/catalog/products/${productId}`),
  })

  // The card fills the form once. A refetch afterwards must not overwrite
  // half-typed prose with what the server still has.
  const card = query.data
  React.useEffect(() => {
    if (!card || texts !== null) return
    const ru = card.translations["ru"] ?? {}
    const en = card.translations["en"] ?? {}
    const pick = (source: Record<string, string>): Texts => ({
      title: source["title"] ?? "",
      subtitle: source["subtitle"] ?? "",
      description: source["description"] ?? "",
      badge: source["badge"] ?? "",
      warranty: source["warranty"] ?? "",
    })
    setTexts({
      uz: {
        title: card.title,
        subtitle: card.subtitle,
        description: card.description,
        badge: card.badge ?? "",
        warranty: card.warranty ?? "",
      },
      ru: pick(ru),
      en: pick(en),
    })
    setCategorySlug(card.category_slug)
    setBrandSlug(card.brand_slug ?? "")
    setFlags({
      is_original: card.is_original,
      free_delivery: card.free_delivery,
      next_day_delivery: card.next_day_delivery,
    })
  }, [card, texts])

  function edit(language: Lang, field: TextField, value: string) {
    setTexts((all) =>
      all ? { ...all, [language]: { ...all[language], [field]: value } } : all,
    )
  }

  const save = useAction<void, AdminProductDetail>({
    run: () =>
      api<AdminProductDetail>(`/staff/catalog/products/${productId}`, {
        method: "PATCH",
        json: {
          title: texts?.uz.title.trim(),
          subtitle: texts?.uz.subtitle.trim(),
          description: texts?.uz.description.trim(),
          badge: texts?.uz.badge.trim() ?? "",
          warranty: texts?.uz.warranty.trim() ?? "",
          category_slug: categorySlug,
          brand_slug: brandSlug || null,
          ...flags,
          translations: texts ? translationsPayload(texts) : {},
        },
      }),
    invalidate: [key, KEY],
    success: "Saqlandi",
  })

  if (query.isPending || !texts || !card) {
    return (
      <Page title="Kartochka">
        <p className="text-[13px] text-ink-faint">Yuklanmoqda…</p>
      </Page>
    )
  }

  return (
    <Page
      title={card.title}
      hint={`${card.sku} · ${card.proposed_by ? card.proposed_by.name : "Mini Bozor"}`}
      actions={
        <div className="flex items-center gap-1.5">
          <Badge tone={PRODUCT_TONE[card.status]}>{PRODUCT_STATUS[card.status]}</Badge>
          <Button onClick={() => navigate("/catalog")}>
            <ArrowLeft />
            Katalog
          </Button>
          <Button
            variant="primary"
            disabled={!texts.uz.title.trim() || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "Yuborilmoqda…" : "Matnni saqlash"}
          </Button>
        </div>
      }
    >
      <div className="max-w-4xl space-y-3">
        {card.moderation_note ? (
          <p className="rounded border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-ink">
            <span className="font-medium text-danger">Rad etilgan:</span>{" "}
            {card.moderation_note}
          </p>
        ) : null}

        <section className="rounded-lg border border-line bg-surface px-3 py-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <LanguageTabs lang={lang} onChange={setLang} texts={texts} />
            <Hint>
              O'zbekchasi kartochkada, qolgani tarjima jadvalida — ikkalasi ham
              bitta «Saqlash» bilan ketadi.
            </Hint>
          </div>
          <TextFields lang={lang} texts={texts} onChange={edit} idPrefix="edit" />
        </section>

        <section className="rounded-lg border border-line bg-surface px-3 py-3">
          <Placement
            categorySlug={categorySlug}
            brandSlug={brandSlug}
            onCategory={setCategorySlug}
            onBrand={setBrandSlug}
          />
          <div className="mt-3 flex flex-wrap gap-4">
            {(
              [
                ["is_original", "Original kafolati"],
                ["free_delivery", "Bepul yetkazish"],
                ["next_day_delivery", "Ertaga yetkaziladi"],
              ] as const
            ).map(([name, label]) => (
              <label key={name} className="flex items-center gap-2 text-[13px] text-ink">
                <input
                  type="checkbox"
                  checked={flags[name]}
                  onChange={(event) =>
                    setFlags((all) => ({ ...all, [name]: event.target.checked }))
                  }
                />
                {label}
              </label>
            ))}
          </div>
        </section>

        <Images productId={productId} />
        <Variants productId={productId} />
        <Specs productId={productId} />
        <Elsewhere product={card} />
      </div>
    </Page>
  )
}
