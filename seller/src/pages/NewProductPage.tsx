import * as React from "react"
import { useNavigate } from "react-router-dom"
import { ImagePlus, Plus, Trash2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api, uploadImage } from "@/api/client"
import type { Category, Listing, ListingCreateIn } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Field, Hint, Input, Label, Select, Textarea } from "@/ui/field"
import { messageOf } from "@/ui/states"
import { Panel } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { ColourPicker } from "@/components/ColourPicker"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { num } from "@/lib/format"
import { t } from "@/lib/labels"

/**
 * One form, one request, and at the end of it the warehouse is expecting a box.
 *
 * This is the seller's whole submission: the card, its photographs, its price,
 * the colours, the sizes under each colour, and how many of each is coming. It
 * posts to `POST /staff/catalog/listings`, which writes all of that in one
 * transaction — see the backend module's own note on why it is one endpoint
 * and not six.
 *
 * **The grid is a tree, not a table.** A size belongs to a colour: black L and
 * white L are two different things to count, and the shelf is counted on the
 * leaves. So sizes are nested inside their colour here exactly as they are in
 * the payload, and a colour with no sizes is itself the countable cell.
 *
 * **Quantities are a promise.** Nothing typed here reaches a stock figure: the
 * numbers become `declared_quantity` on a supply line and the shelf does not
 * move until somebody at the warehouse counts the box. The hint under the
 * button says so, because a seller who thinks they have just put stock on sale
 * will wonder why the product is not in the app.
 */

type SizeDraft = { key: number; label: string; quantity: string }
type ColorDraft = {
  key: number
  label: string
  value: string
  imageUrl: string | null
  sizes: SizeDraft[]
  /** How many of this colour, when the colour is the leaf. */
  quantity: string
}

let nextKey = 1
const key = () => nextKey++

const emptySize = (): SizeDraft => ({ key: key(), label: "", quantity: "" })
const emptyColor = (): ColorDraft => ({
  key: key(),
  quantity: "",
  label: "",
  value: "",
  imageUrl: null,
  sizes: [emptySize()],
})

export function NewProductPage() {
  const navigate = useNavigate()

  // The editorial list, in the words the rows hold — not the customer's
  // translated tree. A seller files a product under the same name an admin
  // sees, so the two never disagree about which category was meant.
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/staff/catalog/categories"),
    staleTime: 10 * 60_000,
  })

  const [title, setTitle] = React.useState("")
  const [subtitle, setSubtitle] = React.useState("")
  const [description, setDescription] = React.useState("")
  const [category, setCategory] = React.useState("")
  const [price, setPrice] = React.useState("")
  const [oldPrice, setOldPrice] = React.useState("")
  const [weight, setWeight] = React.useState("")
  const [images, setImages] = React.useState<string[]>([])
  const [colors, setColors] = React.useState<ColorDraft[]>([emptyColor()])
  const [uploadError, setUploadError] = React.useState<string | null>(null)
  const [uploading, setUploading] = React.useState(false)

  // The category list is long and a seller picks from it once per product, so
  // the first one is not a sensible default — but an empty select that looks
  // filled in is worse, so it opens on a prompt and the field is required.
  const submit = useAction<ListingCreateIn, Listing>({
    run: (body) =>
      api<Listing>("/staff/catalog/listings", { method: "POST", json: body }),
    invalidate: [["listings"], ["supplies"]],
    success: (made) => `${made.title} topshirildi — ${made.supply_code ?? ""}`.trim(),
    onDone: (made) => navigate(`/products/${made.id}`),
  })

  // The one field the backend will refuse, checked here so the seller is told
  // before they press rather than after. Named colours only: an empty draft
  // row is not a colour anybody has started yet.
  const namedColours = colors.filter((colour) => colour.label.trim())
  const withoutPhoto = namedColours.filter((colour) => !colour.imageUrl)

  const totalDeclared = colors.reduce((sum, colour) => {
    const bySize = colour.sizes.reduce(
      (inner, size) => inner + (Number(size.quantity) || 0),
      0,
    )
    // A colour with sizes is counted on them; one without is counted on
    // itself, and that figure used to be dropped on the floor.
    return sum + (bySize || Number(colour.quantity) || 0)
  }, 0)

  const pickImages = async (files: FileList | null) => {
    if (!files?.length) return
    setUploading(true)
    setUploadError(null)
    try {
      // One at a time, in the order chosen: the first picture becomes the
      // cover, and `Promise.all` would settle them in whatever order the
      // network happened to finish.
      const added: string[] = []
      for (const file of Array.from(files)) {
        const uploaded = await uploadImage(file)
        added.push(uploaded.media_url)
      }
      setImages((current) => [...current, ...added])
    } catch (problem) {
      setUploadError(messageOf(problem))
    } finally {
      setUploading(false)
    }
  }

  const send = (event: React.FormEvent) => {
    event.preventDefault()
    submit.mutate({
      title: title.trim(),
      subtitle: subtitle.trim(),
      description: description.trim(),
      category_slug: category,
      price: Number(price) || 0,
      old_price: oldPrice ? Number(oldPrice) : null,
      weight_grams: Number(weight) || 0,
      images,
      colors: colors
        .filter((colour) => colour.label.trim())
        .map((colour) => ({
          label: colour.label.trim(),
          value: colour.value.trim(),
          image_url: colour.imageUrl,
          // Only meaningful when the colour has no sizes: with sizes, they
          // are the leaves and counting the colour too would count twice.
          quantity: Number(colour.quantity) || 0,
          sizes: colour.sizes
            .filter((size) => size.label.trim())
            .map((size) => ({
              label: size.label.trim(),
              value: size.label.trim(),
              quantity: Number(size.quantity) || 0,
            })),
        })),
    })
  }

  const patchColor = (index: number, patch: Partial<ColorDraft>) =>
    setColors((current) =>
      current.map((colour, i) => (i === index ? { ...colour, ...patch } : colour)),
    )

  const patchSize = (colourIndex: number, sizeIndex: number, patch: Partial<SizeDraft>) =>
    setColors((current) =>
      current.map((colour, i) =>
        i === colourIndex
          ? {
              ...colour,
              sizes: colour.sizes.map((size, j) =>
                j === sizeIndex ? { ...size, ...patch } : size,
              ),
            }
          : colour,
      ),
    )

  return (
    <form onSubmit={send} className="space-y-[var(--gap-page)]">
      <PageTitle>{t.newProduct}</PageTitle>

      <Panel title={t.title}>
        <div className="space-y-4 border-t border-line-soft px-5 py-5">
          <Field id="title" label={t.title}>
            {(props) => (
              <Input
                {...props}
                required
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Paxta futbolka, oq"
              />
            )}
          </Field>
          <Field id="subtitle" label={t.subtitle}>
            {(props) => (
              <Input
                {...props}
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                placeholder="Yumshoq trikotaj"
              />
            )}
          </Field>
          {/* A select with nothing in it looks filled in and is not. If the
              list failed to load, the field says so — the sentence the server
              gave us — because a seller staring at an empty dropdown has no
              way to tell a permission problem from a slow network. */}
          <Field
            id="category"
            label={t.category}
            error={categories.isError ? messageOf(categories.error) : undefined}
            hint={categories.isPending ? "Yuklanmoqda…" : undefined}
          >
            {(props) => (
              <Select
                {...props}
                required
                disabled={categories.isPending || categories.isError}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">—</option>
                {(categories.data ?? []).map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field id="description" label={t.description}>
            {(props) => (
              <Textarea
                {...props}
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Kunlik kiyish uchun."
              />
            )}
          </Field>
        </div>
      </Panel>

      <Panel title={t.images}>
        <div className="space-y-3 border-t border-line-soft px-5 py-5">
          <div className="flex flex-wrap gap-2">
            {images.map((url, index) => (
              <div key={url} className="relative">
                <Thumb src={url} className="size-20" />
                {index === 0 ? (
                  <Badge tone="brand" className="absolute left-1 top-1">
                    Asosiy
                  </Badge>
                ) : null}
                <Button
                  type="button"
                  variant="quiet"
                  size="icon"
                  aria-label="Rasmni olib tashlash"
                  className="absolute -right-2 -top-2 size-7 rounded-full"
                  onClick={() => setImages(images.filter((_, i) => i !== index))}
                >
                  <Trash2 />
                </Button>
              </div>
            ))}
            <label
              className="flex size-20 cursor-pointer flex-col items-center justify-center gap-1
                         rounded-[var(--radius-control)] border border-dashed border-line
                         text-[length:var(--text-micro)] text-ink-soft hover:bg-line-soft"
            >
              <ImagePlus className="size-4" />
              {uploading ? "…" : t.addImage}
              <input
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(e) => void pickImages(e.target.files)}
              />
            </label>
          </div>
          {uploadError ? (
            <p role="alert" className="text-[length:var(--text-small)] font-medium text-danger">
              {uploadError}
            </p>
          ) : (
            <Hint>Birinchi rasm — kartochkaning asosiy rasmi. Kamida bitta kerak.</Hint>
          )}
        </div>
      </Panel>

      <Panel title={t.price}>
        <div className="grid gap-4 border-t border-line-soft px-5 py-5 sm:grid-cols-3">
          <Field id="price" label={t.price}>
            {(props) => (
              <Input
                {...props}
                required
                inputMode="numeric"
                value={price}
                onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))}
                placeholder="149000"
              />
            )}
          </Field>
          <Field id="old-price" label={t.oldPrice} hint="Chizilgan narx — majburiy emas">
            {(props) => (
              <Input
                {...props}
                inputMode="numeric"
                value={oldPrice}
                onChange={(e) => setOldPrice(e.target.value.replace(/\D/g, ""))}
              />
            )}
          </Field>
          <Field id="weight" label={t.weight} hint="Xizmat narxi vaznga qarab">
            {(props) => (
              <Input
                {...props}
                inputMode="numeric"
                value={weight}
                onChange={(e) => setWeight(e.target.value.replace(/\D/g, ""))}
                placeholder="300"
              />
            )}
          </Field>
        </div>
      </Panel>

      <Panel
        title={t.colors}
        action={
          <Button
            type="button"
            size="sm"
            onClick={() => setColors([...colors, emptyColor()])}
          >
            <Plus />
            {t.addColor}
          </Button>
        }
      >
        <div className="space-y-4 border-t border-line-soft px-5 py-5">
          {colors.map((colour, colourIndex) => (
            <div
              key={colour.key}
              className="space-y-3 rounded-[var(--radius-control)] border border-line p-4"
            >
              <ColourPicker
                colour={{
                  label: colour.label,
                  value: colour.value,
                  image_url: colour.imageUrl ?? "",
                }}
                onChange={(patch) =>
                  patchColor(colourIndex, {
                    ...(patch.label !== undefined ? { label: patch.label } : {}),
                    ...(patch.value !== undefined ? { value: patch.value } : {}),
                    ...(patch.image_url !== undefined
                      ? { imageUrl: patch.image_url || null }
                      : {}),
                  })
                }
                onRemove={
                  colors.length > 1
                    ? () => setColors(colors.filter((_, i) => i !== colourIndex))
                    : undefined
                }
              />

              {/* A colour with no size rows filled in is counted on itself,
                  so it needs its own figure. Shown rather than hidden behind
                  a mode switch: a seller of bags never fills a size in, and
                  the box is simply where their count goes. */}
              {colour.sizes.every((size) => !size.label.trim()) ? (
                <div className="max-w-xs space-y-1.5">
                  <Label htmlFor={`colour-qty-${colour.key}`}>{t.quantity}</Label>
                  <Input
                    id={`colour-qty-${colour.key}`}
                    inputMode="numeric"
                    value={colour.quantity}
                    placeholder="0"
                    onChange={(e) =>
                      patchColor(colourIndex, {
                        quantity: e.target.value.replace(/\D/g, ""),
                      })
                    }
                  />
                  <Hint>{t.sizelessHint}</Hint>
                </div>
              ) : null}

              <div className="space-y-2">
                <p className="text-[length:var(--text-small)] font-medium text-ink">
                  {t.sizes}
                </p>
                {colour.sizes.map((size, sizeIndex) => (
                  <div
                    key={size.key}
                    className="grid grid-cols-[1fr_1fr_auto] items-end gap-2"
                  >
                    <div className="space-y-1.5">
                      <Label htmlFor={`size-${size.key}`} className="sr-only">
                        {t.sizeLabel}
                      </Label>
                      <Input
                        id={`size-${size.key}`}
                        value={size.label}
                        onChange={(e) =>
                          patchSize(colourIndex, sizeIndex, { label: e.target.value })
                        }
                        placeholder={t.sizeLabel}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor={`qty-${size.key}`} className="sr-only">
                        {t.quantity}
                      </Label>
                      <Input
                        id={`qty-${size.key}`}
                        inputMode="numeric"
                        value={size.quantity}
                        onChange={(e) =>
                          patchSize(colourIndex, sizeIndex, {
                            quantity: e.target.value.replace(/\D/g, ""),
                          })
                        }
                        placeholder={t.quantity}
                      />
                    </div>
                    {colour.sizes.length > 1 ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="O'lchamni olib tashlash"
                        onClick={() =>
                          patchColor(colourIndex, {
                            sizes: colour.sizes.filter((_, j) => j !== sizeIndex),
                          })
                        }
                      >
                        <Trash2 />
                      </Button>
                    ) : (
                      <span />
                    )}
                  </div>
                ))}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    patchColor(colourIndex, { sizes: [...colour.sizes, emptySize()] })
                  }
                >
                  <Plus />
                  {t.addSize}
                </Button>
              </div>
            </div>
          ))}
          {/* The rule the backend enforces, said before it is enforced: every
              colour has sizes or none does, because the shelf is counted on
              the leaves and the two levels cannot be mixed. */}
          <Hint>
            O'lcham har rangda bo'lsin yoki hech qaysisida — qoldiq eng pastki
            bo'g'inda sanaladi.
          </Hint>
        </div>
      </Panel>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-panel)] border border-line bg-surface px-5 py-4">
        <div>
          <p className="tabular text-[length:var(--text-body)] font-medium text-ink">
            {t.willSend}: {num(totalDeclared)} {t.pieces}
          </p>
          {/* The refusal, said here rather than after the round trip, and
              naming the colours so a seller with eight of them knows which
              two to go back to. */}
          {withoutPhoto.length ? (
            <p
              role="alert"
              className="max-w-md text-[length:var(--text-small)] font-medium text-danger"
            >
              {t.colorNeedsPhoto}: {withoutPhoto.map((c) => c.label.trim()).join(", ")}
            </p>
          ) : (
            <p className="max-w-md text-[length:var(--text-small)] text-ink-soft">
              {t.submitHint}
            </p>
          )}
        </div>
        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={submit.isPending || uploading || withoutPhoto.length > 0}
        >
          {submit.isPending ? t.submitting : t.submit}
        </Button>
      </div>
    </form>
  )
}
