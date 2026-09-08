import * as React from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowLeft, ImagePlus, Trash2 } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api, uploadImage } from "@/api/client"
import type { ProductDetail, ProductImage, ProductSpec, ProductVariant } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Field, Hint, Input, Label, Textarea } from "@/ui/field"
import { Async, messageOf } from "@/ui/states"
import { Panel, Row } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { PageTitle } from "@/components/Shell"
import { useAction } from "@/lib/mutate"
import { num, som } from "@/lib/format"
import { productStatus, t } from "@/lib/labels"

/**
 * Fixing a card somebody else wrote.
 *
 * **Editing is not approving.** Nothing on this screen changes a product's
 * status: a card reaches the shop when the warehouse counts its batch in, and
 * an admin's job here is the half of moderation that survived — the title
 * spelled wrong, the description a shopkeeper pasted from somewhere, the
 * photograph nobody can see anything in. The banner says so, because in every
 * other marketplace this screen is where somebody presses Approve.
 *
 * The price is absent on purpose. It belongs to the seller's offer and is
 * theirs to set; an admin who could change it would be repricing somebody
 * else's goods.
 */
export function ProductEditPage() {
  const { id } = useParams()
  const product = useQuery({
    queryKey: ["product", id],
    queryFn: () => api<ProductDetail>(`/staff/catalog/products/${id}`),
    enabled: Boolean(id),
  })

  return (
    <>
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link to="/catalog">
            <ArrowLeft />
            {t.catalog}
          </Link>
        </Button>
      </div>
      <Async query={product} lines={6}>
        {(card) => <Editor card={card} />}
      </Async>
    </>
  )
}

function Editor({ card }: { card: ProductDetail }) {
  const keys = [["product", String(card.id)], ["products", "moderating"]]
  const [title, setTitle] = React.useState(card.title)
  const [subtitle, setSubtitle] = React.useState(card.subtitle)
  const [description, setDescription] = React.useState(card.description)
  const [badge, setBadge] = React.useState(card.badge ?? "")
  const [warranty, setWarranty] = React.useState(card.warranty ?? "")

  const save = useAction<void, ProductDetail>({
    run: () =>
      api<ProductDetail>(`/staff/catalog/products/${card.id}`, {
        method: "PATCH",
        json: {
          title: title.trim(),
          subtitle: subtitle.trim(),
          description: description.trim(),
          badge: badge.trim() || null,
          warranty: warranty.trim() || null,
        },
      }),
    invalidate: keys,
    success: t.saved,
  })

  return (
    <div className="space-y-[var(--gap-page)]">
      <PageTitle
        action={
          <Badge tone={card.status === "published" ? "good" : "warn"}>
            {productStatus[card.status] ?? card.status}
          </Badge>
        }
      >
        {card.title}
      </PageTitle>

      <p className="rounded-[var(--radius-control)] bg-brand-soft px-4 py-3 text-[length:var(--text-small)] text-brand-deep">
        {t.editHint}
      </p>

      {card.moderation_note ? (
        <p
          role="alert"
          className="rounded-[var(--radius-control)] bg-danger-soft px-4 py-3 text-[length:var(--text-small)] text-danger"
        >
          {card.moderation_note}
        </p>
      ) : null}

      <Panel
        title={t.title}
        action={
          <Button
            variant="primary"
            size="sm"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            {t.save}
          </Button>
        }
      >
        <div className="grid gap-4 border-t border-line-soft px-5 py-4 sm:grid-cols-2">
          <Field id="p-title" label={t.title}>
            {(props) => (
              <Input {...props} value={title} onChange={(e) => setTitle(e.target.value)} />
            )}
          </Field>
          <Field id="p-subtitle" label={t.subtitle}>
            {(props) => (
              <Input
                {...props}
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
              />
            )}
          </Field>
          <Field id="p-description" label={t.description} className="sm:col-span-2">
            {(props) => (
              <Textarea
                {...props}
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            )}
          </Field>
          <Field id="p-badge" label={t.badge}>
            {(props) => (
              <Input {...props} value={badge} onChange={(e) => setBadge(e.target.value)} />
            )}
          </Field>
          <Field id="p-warranty" label={t.warranty}>
            {(props) => (
              <Input
                {...props}
                value={warranty}
                onChange={(e) => setWarranty(e.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="flex flex-wrap gap-x-8 gap-y-1 border-t border-line-soft px-5 py-3 text-[length:var(--text-small)] text-ink-soft">
          <span>{card.sku}</span>
          <span>
            {t.categories}: <span className="text-ink">{card.category_slug}</span>
          </span>
          <span>
            {t.brands}: <span className="text-ink">{card.brand_slug ?? "—"}</span>
          </span>
          {/* The price is the seller's offer, shown and not editable. */}
          <span>
            Narx: <span className="tabular text-ink">{som(card.price)}</span>
          </span>
          <span>
            {t.balance}: <span className="tabular text-ink">{num(card.stock_left)}</span>
          </span>
        </div>
      </Panel>

      <Images productId={card.id} keys={keys} />
      <Variants productId={card.id} />
      <Specs productId={card.id} />
    </div>
  )
}

/**
 * The gallery, with the ids the reorder endpoint needs.
 *
 * `GET .../images` is the one read that answers with ids — the write paths
 * answer with bare URLs, which redraws a gallery and cannot edit one.
 */
function Images({ productId, keys }: { productId: number; keys: string[][] }) {
  const images = useQuery({
    queryKey: ["images", productId],
    queryFn: () => api<ProductImage[]>(`/staff/catalog/products/${productId}/images`),
  })
  const [error, setError] = React.useState<string | null>(null)
  const [busy, setBusy] = React.useState(false)

  const attach = useAction<string, unknown>({
    run: (url) =>
      api(`/staff/catalog/products/${productId}/images`, {
        method: "POST",
        json: { url },
      }),
    invalidate: [["images", productId], ...keys],
    success: t.added,
  })

  const drop = useAction<number, unknown>({
    run: (imageId) =>
      api(`/staff/catalog/products/${productId}/images/${imageId}`, {
        method: "DELETE",
      }),
    invalidate: [["images", productId], ...keys],
    success: t.removed,
  })

  const reorder = useAction<number[], unknown>({
    run: (ids) =>
      api(`/staff/catalog/products/${productId}/images/order`, {
        method: "PUT",
        json: { ids },
      }),
    invalidate: [["images", productId]],
    success: t.saved,
  })

  const pick = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        const uploaded = await uploadImage(file)
        attach.mutate(uploaded.media_url)
      }
    } catch (problem) {
      setError(messageOf(problem))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="Rasmlar">
      <Async query={images} lines={2}>
        {(rows) => (
          <div className="space-y-3 border-t border-line-soft px-5 py-4">
            <div className="flex flex-wrap gap-2">
              {rows.map((image, index) => (
                <div key={image.id} className="relative">
                  <Thumb src={image.url} className="size-20" />
                  {index === 0 ? (
                    <Badge tone="brand" className="absolute left-1 top-1">
                      Asosiy
                    </Badge>
                  ) : null}
                  <div className="absolute -bottom-2 left-0 right-0 flex justify-center gap-1">
                    {/* Moving one is a whole reorder, because a partial order
                        would leave the rest holding numbers that mean
                        something else — so the button sends the full list
                        with two entries swapped. */}
                    {index > 0 ? (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label="Chapga"
                        className="h-6 px-1.5"
                        onClick={() => {
                          const ids = rows.map((row) => row.id)
                          const swapped = [...ids]
                          const previous = swapped[index - 1]!
                          swapped[index - 1] = swapped[index]!
                          swapped[index] = previous
                          reorder.mutate(swapped)
                        }}
                      >
                        ←
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="quiet"
                      aria-label={t.remove}
                      className="h-6 px-1.5"
                      onClick={() => drop.mutate(image.id)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              ))}
              <label
                className="flex size-20 cursor-pointer flex-col items-center justify-center gap-1
                           rounded-[var(--radius-control)] border border-dashed border-line
                           text-[length:var(--text-micro)] text-ink-soft hover:bg-line-soft"
              >
                <ImagePlus className="size-4" />
                {busy ? "…" : t.add}
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(event) => void pick(event.target.files)}
                />
              </label>
            </div>
            {error ? (
              <p role="alert" className="text-[length:var(--text-small)] font-medium text-danger">
                {error}
              </p>
            ) : (
              <Hint>Birinchi rasm — kartochkaning asosiy rasmi.</Hint>
            )}
          </div>
        )}
      </Async>
    </Panel>
  )
}

/**
 * The colours and sizes, read-only where they carry a history.
 *
 * `can_delete` and `blocked_reason` come from the server: a variant something
 * has been sold against cannot be deleted, because the order line that named
 * it would lose what it referred to. The reason is shown rather than the
 * button being greyed out with no explanation.
 */
function Variants({ productId }: { productId: number }) {
  const variants = useQuery({
    queryKey: ["variants", productId],
    queryFn: () => api<ProductVariant[]>(`/staff/catalog/products/${productId}/variants`),
  })

  const drop = useAction<number, unknown>({
    run: (variantId) =>
      api(`/staff/catalog/products/${productId}/variants/${variantId}`, {
        method: "DELETE",
      }),
    invalidate: [["variants", productId]],
    success: t.removed,
  })

  return (
    <Panel title="Ranglar va o'lchamlar">
      <Async query={variants} lines={3}>
        {(rows) => (
          <>
            {rows.map((variant) => (
              <Row key={variant.id} className="sm:flex-nowrap">
                <span className="w-20 shrink-0 text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint">
                  {variant.kind}
                </span>
                <span className="min-w-0 flex-1 truncate text-ink">
                  {variant.parent_id ? <span className="text-ink-faint">· </span> : null}
                  {variant.label}
                </span>
                <span className="tabular w-20 text-right text-ink-soft">
                  {variant.stock_left === null ? "—" : num(variant.stock_left)}
                </span>
                {variant.can_delete ? (
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`${variant.label} ${t.remove}`}
                    disabled={drop.isPending}
                    onClick={() => drop.mutate(variant.id)}
                  >
                    <Trash2 />
                  </Button>
                ) : (
                  <span className="w-56 truncate text-right text-[length:var(--text-small)] text-ink-faint">
                    {variant.blocked_reason}
                  </span>
                )}
              </Row>
            ))}
          </>
        )}
      </Async>
    </Panel>
  )
}

/**
 * The spec table, replaced whole rather than edited row by row.
 *
 * That is what the endpoint does — `PUT .../specs` takes the entire table —
 * and it is the right shape: a spec table is read as a block, and reordering
 * two rows of it through per-row edits would be four requests and a moment
 * where the table is wrong.
 */
function Specs({ productId }: { productId: number }) {
  const specs = useQuery({
    queryKey: ["specs", productId],
    queryFn: () => api<ProductSpec[]>(`/staff/catalog/products/${productId}/specs`),
  })
  const [draft, setDraft] = React.useState<{ key: string; value: string }[] | null>(null)

  const rows = draft ?? (specs.data ?? []).map((row) => ({ key: row.key, value: row.value }))

  const save = useAction<void, unknown>({
    run: () =>
      api(`/staff/catalog/products/${productId}/specs`, {
        method: "PUT",
        json: { specs: rows.filter((row) => row.key.trim() && row.value.trim()) },
      }),
    invalidate: [["specs", productId]],
    success: t.saved,
    onDone: () => setDraft(null),
  })

  return (
    <Panel
      title="Xususiyatlar"
      action={
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setDraft([...rows, { key: "", value: "" }])}>
            {t.add}
          </Button>
          <Button
            size="sm"
            variant="primary"
            disabled={draft === null || save.isPending}
            onClick={() => save.mutate()}
          >
            {t.save}
          </Button>
        </div>
      }
    >
      <Async query={specs} lines={2}>
        {() => (
          <div className="space-y-2 border-t border-line-soft px-5 py-4">
            {rows.length === 0 ? (
              <Hint>Xususiyat yo'q.</Hint>
            ) : (
              rows.map((row, index) => (
                <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                  <div className="space-y-1.5">
                    <Label htmlFor={`spec-key-${index}`} className="sr-only">
                      Kalit
                    </Label>
                    <Input
                      id={`spec-key-${index}`}
                      value={row.key}
                      onChange={(event) =>
                        setDraft(
                          rows.map((entry, i) =>
                            i === index ? { ...entry, key: event.target.value } : entry,
                          ),
                        )
                      }
                      placeholder="Material"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`spec-value-${index}`} className="sr-only">
                      Qiymat
                    </Label>
                    <Input
                      id={`spec-value-${index}`}
                      value={row.value}
                      onChange={(event) =>
                        setDraft(
                          rows.map((entry, i) =>
                            i === index ? { ...entry, value: event.target.value } : entry,
                          ),
                        )
                      }
                      placeholder="Paxta"
                    />
                  </div>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={t.remove}
                    onClick={() => setDraft(rows.filter((_, i) => i !== index))}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))
            )}
          </div>
        )}
      </Async>
    </Panel>
  )
}
