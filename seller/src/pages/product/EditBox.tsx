import * as React from "react"
import { ImagePlus, Pencil, Trash2, X } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { api, uploadImage } from "@/api/client"
import type { Category, Listing, ListingEditIn } from "@/api/types"
import { Badge } from "@/ui/badge"
import { Button } from "@/ui/button"
import { Field, Hint, Input, Select, Textarea } from "@/ui/field"
import { messageOf } from "@/ui/states"
import { Panel } from "@/components/Panel"
import { Thumb } from "@/components/Thumb"
import { useAction } from "@/lib/mutate"
import { t } from "@/lib/labels"

/**
 * The card's own words and pictures, corrected by the person who wrote them.
 *
 * None of this was editable. A seller who mistyped a name, filed a shirt under
 * shoes, or photographed the wrong side of it had exactly one field they could
 * change — the price — and everything else belonged to an admin's screen they
 * cannot open. A shop where fixing a typo means telephoning head office is a
 * shop whose cards stay wrong, and the refused ones are the worst of it: the
 * refusal says what to fix and there was nothing to fix it with.
 *
 * **Closed until asked.** The product screen is read far more often than it is
 * edited — a seller opens it to see whether the warehouse has counted the box
 * — so this is a button, and the form is what the button opens. Open by
 * default, it would put six inputs between them and the stock figure they came
 * for.
 *
 * The colours are not here. A colour is a row on a shelf with a count against
 * it, so adding or removing one is a delivery or a collection, not a change of
 * wording — which is why they sit in the stock panel below with the two
 * buttons that move goods.
 */
export function EditBox({ listing }: { listing: Listing }) {
  const [open, setOpen] = React.useState(false)

  return (
    <Panel
      title={t.cardDetails}
      action={
        <Button
          type="button"
          size="sm"
          variant={open ? "quiet" : "outline"}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Pencil />}
          {open ? t.cancel : t.edit}
        </Button>
      }
    >
      {open ? (
        <Form listing={listing} onDone={() => setOpen(false)} />
      ) : (
        <dl className="grid gap-4 border-t border-line-soft px-5 py-5 sm:grid-cols-2">
          <Line label={t.title}>{listing.title}</Line>
          <Line label={t.subtitle}>{listing.subtitle || "—"}</Line>
          <Line label={t.category}>{listing.category_slug}</Line>
          <Line label={t.images}>
            <span className="flex flex-wrap gap-2">
              {listing.images.length ? (
                listing.images.map((url) => (
                  <Thumb key={url} src={url} className="size-12" />
                ))
              ) : (
                "—"
              )}
            </span>
          </Line>
        </dl>
      )}
    </Panel>
  )
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[length:var(--text-micro)] uppercase tracking-wide text-ink-faint">
        {label}
      </dt>
      <dd className="text-[length:var(--text-body)] text-ink">{children}</dd>
    </div>
  )
}

/**
 * The form.
 *
 * Seeded from the listing and sent as a patch of *changed* fields only, so
 * saving the title alone sends the title alone — which is what the audit row
 * then says, rather than "everything, again".
 */
function Form({ listing, onDone }: { listing: Listing; onDone: () => void }) {
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Category[]>("/staff/catalog/categories"),
    staleTime: 10 * 60_000,
  })

  const [title, setTitle] = React.useState(listing.title)
  const [subtitle, setSubtitle] = React.useState(listing.subtitle)
  const [description, setDescription] = React.useState("")
  const [category, setCategory] = React.useState(listing.category_slug)
  const [images, setImages] = React.useState<string[]>(listing.images)
  const [uploading, setUploading] = React.useState(false)
  const [uploadError, setUploadError] = React.useState<string | null>(null)

  // The description is not on the listing shape, so it is read off the card
  // the shop shows rather than left blank — a textarea that opens empty and
  // saves is a textarea that deletes what was written.
  const detail = useQuery({
    queryKey: ["listing-text", listing.id],
    queryFn: () => api<{ description: string }>(`/products/${listing.id}`),
    // A card the warehouse has not counted in yet is a 404 for shoppers, and
    // that is correct; there is simply nothing to prefill from.
    retry: false,
  })
  React.useEffect(() => {
    if (detail.data?.description) setDescription(detail.data.description)
  }, [detail.data])

  const save = useAction<ListingEditIn, Listing>({
    run: (body) =>
      api<Listing>(`/staff/catalog/listings/${listing.id}`, {
        method: "PATCH",
        json: body,
      }),
    invalidate: [
      ["listings"],
      ["listing", String(listing.id)],
      ["listing-text", listing.id],
    ],
    success: t.cardSaved,
    onDone,
  })

  async function pick(files: FileList | null) {
    if (!files?.length) return
    setUploading(true)
    setUploadError(null)
    try {
      // One at a time, in the order chosen: the first picture is the cover,
      // and `Promise.all` settles them in whatever order the network finishes.
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

  const sameImages =
    images.length === listing.images.length &&
    images.every((url, at) => url === listing.images[at])

  const patch: ListingEditIn = {
    ...(title.trim() !== listing.title ? { title: title.trim() } : {}),
    ...(subtitle.trim() !== listing.subtitle ? { subtitle: subtitle.trim() } : {}),
    ...(description.trim() !== (detail.data?.description ?? "").trim()
      ? { description: description.trim() }
      : {}),
    ...(category !== listing.category_slug ? { category_slug: category } : {}),
    ...(sameImages ? {} : { images }),
  }
  const changed = Object.keys(patch).length > 0

  return (
    <form
      className="space-y-4 border-t border-line-soft px-5 py-5"
      onSubmit={(event) => {
        event.preventDefault()
        save.mutate(patch)
      }}
    >
      <Field id="edit-title" label={t.title}>
        {(props) => (
          <Input
            {...props}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        )}
      </Field>
      <Field id="edit-subtitle" label={t.subtitle}>
        {(props) => (
          <Input
            {...props}
            value={subtitle}
            onChange={(event) => setSubtitle(event.target.value)}
          />
        )}
      </Field>
      <Field id="edit-category" label={t.category}>
        {(props) => (
          <Select
            {...props}
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            {(categories.data ?? [])
              .filter((row) => !row.child_count)
              .map((row) => (
                <option key={row.slug} value={row.slug}>
                  {row.parent_slug ? `${row.parent_slug} › ${row.name}` : row.name}
                </option>
              ))}
          </Select>
        )}
      </Field>
      <Field id="edit-description" label={t.description}>
        {(props) => (
          <Textarea
            {...props}
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        )}
      </Field>

      <div className="space-y-2">
        <p className="text-[length:var(--text-small)] font-medium text-ink">{t.images}</p>
        <div className="flex flex-wrap gap-2">
          {images.map((url, at) => (
            <div key={url} className="relative">
              <Thumb src={url} className="size-20" />
              {at === 0 ? (
                <Badge tone="brand" className="absolute left-1 top-1">
                  {t.primaryImage}
                </Badge>
              ) : null}
              <Button
                type="button"
                variant="quiet"
                size="icon"
                aria-label={t.removePhoto}
                className="absolute -right-2 -top-2 size-7 rounded-full"
                onClick={() => setImages(images.filter((_, i) => i !== at))}
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
            {uploading ? "…" : t.addPhoto}
            <input
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(event) => void pick(event.target.files)}
            />
          </label>
        </div>
        {uploadError ? (
          <p role="alert" className="text-[length:var(--text-small)] font-medium text-danger">
            {uploadError}
          </p>
        ) : (
          <Hint>{t.imagesHint}</Hint>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          variant="primary"
          disabled={!changed || !images.length || uploading || save.isPending}
        >
          {t.save}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          {t.cancel}
        </Button>
      </div>
    </form>
  )
}
