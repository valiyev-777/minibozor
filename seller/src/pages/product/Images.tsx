import * as React from "react"
import { ArrowLeft, ArrowRight, ImagePlus, Loader2, Star, Trash2 } from "lucide-react"
import { ApiError, uploadImage } from "@/api/client"
import { Hint, Label } from "@/components/ui/field"
import { cn, mediaSrc } from "@/lib/utils"

/** One picked picture, before and after the server has it. */
export type Picked = {
  /** Stable across reorders, so React keeps the right preview with the right row. */
  key: string
  /** The browser's own preview, shown immediately. Revoked when the row goes. */
  preview: string
  name: string
  /** The path the catalogue stores, once uploaded. Null while in flight. */
  mediaUrl: string | null
  error: string | null
}

/**
 * Choosing the photographs, in order, with the first one meaning something.
 *
 * Three things here are not decoration:
 *
 * **The preview is local and immediate.** `URL.createObjectURL` shows the
 * picture the moment it is chosen, before any upload finishes, because a
 * seller selecting six photographs of six shirts needs to see which is which
 * to put them in order — and waiting for six round trips to find out that two
 * are the same shirt is the version people abandon halfway.
 *
 * **The order is the product.** The first picture is the one in every listing,
 * every basket line and every order row. So it is labelled, and moving it is
 * two arrows rather than a drag: a drag needs pointer handling, a touch
 * fallback and a keyboard fallback to be usable at all, and arrows are all
 * three for free.
 *
 * **A failed upload stays visible.** It keeps its place in the list with its
 * reason on it, rather than vanishing and leaving somebody to work out which
 * of the six is missing. The form will not submit while one is unresolved.
 */
export function Images({
  value,
  onChange,
  max = 8,
}: {
  value: Picked[]
  onChange: (next: Picked[]) => void
  max?: number
}) {
  const [busy, setBusy] = React.useState(0)
  const input = React.useRef<HTMLInputElement>(null)

  // The object URLs are revoked when this screen goes away. Without it every
  // preview holds its file in memory for the life of the tab, and a seller who
  // opens the form a dozen times has a dozen sets of photographs resident.
  const live = React.useRef<Set<string>>(new Set())
  React.useEffect(() => {
    const urls = live.current
    return () => {
      for (const url of urls) URL.revokeObjectURL(url)
      urls.clear()
    }
  }, [])

  async function add(files: FileList | null) {
    if (!files?.length) return
    const room = max - value.length
    const chosen = Array.from(files).slice(0, Math.max(room, 0))
    if (!chosen.length) return

    const rows: Picked[] = chosen.map((file, index) => {
      const preview = URL.createObjectURL(file)
      live.current.add(preview)
      return {
        key: `${Date.now()}-${index}-${file.name}`,
        preview,
        name: file.name,
        mediaUrl: null,
        error: null,
      }
    })
    // Placed first, then filled in: the row exists while its upload is in
    // flight, so the order a seller chose is the order they keep.
    let current = [...value, ...rows]
    onChange(current)

    setBusy((n) => n + rows.length)
    await Promise.all(
      rows.map(async (row, index) => {
        try {
          const done = await uploadImage(chosen[index]!)
          current = current.map((r) =>
            r.key === row.key ? { ...r, mediaUrl: done.media_url } : r,
          )
        } catch (error) {
          const message =
            error instanceof ApiError ? error.message : "Yuklanmadi"
          current = current.map((r) =>
            r.key === row.key ? { ...r, error: message } : r,
          )
        } finally {
          setBusy((n) => n - 1)
          onChange(current)
        }
      }),
    )
    if (input.current) input.current.value = ""
  }

  function move(from: number, to: number) {
    if (to < 0 || to >= value.length) return
    const next = [...value]
    const [row] = next.splice(from, 1)
    next.splice(to, 0, row!)
    onChange(next)
  }

  function drop(index: number) {
    const row = value[index]
    if (row) {
      URL.revokeObjectURL(row.preview)
      live.current.delete(row.preview)
    }
    onChange(value.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <Label>Rasmlar</Label>
        <Hint>
          {value.length}/{max} · birinchisi asosiy
        </Hint>
      </div>

      {value.length ? (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {value.map((row, index) => (
            <li
              key={row.key}
              className={cn(
                "group relative overflow-hidden rounded-xl border bg-surface",
                row.error ? "border-danger" : "border-line",
              )}
            >
              <img
                src={row.mediaUrl ? mediaSrc(row.mediaUrl) : row.preview}
                alt={row.name}
                className="aspect-square w-full object-cover"
              />

              {index === 0 ? (
                <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-md bg-brand px-2 py-1 text-[11px] font-semibold text-white">
                  <Star className="size-3" />
                  Asosiy
                </span>
              ) : null}

              {row.mediaUrl === null && !row.error ? (
                <span className="absolute inset-0 grid place-items-center bg-ink/40">
                  <Loader2 className="size-6 animate-spin text-white" />
                </span>
              ) : null}

              {row.error ? (
                <p className="px-2 py-1.5 text-[12px] font-medium text-danger">
                  {row.error}
                </p>
              ) : null}

              <div className="flex items-center justify-between gap-1 border-t border-line px-1.5 py-1.5">
                <div className="flex gap-0.5">
                  <IconButton
                    label="Chapga"
                    disabled={index === 0}
                    onClick={() => move(index, index - 1)}
                  >
                    <ArrowLeft className="size-4" />
                  </IconButton>
                  <IconButton
                    label="O'ngga"
                    disabled={index === value.length - 1}
                    onClick={() => move(index, index + 1)}
                  >
                    <ArrowRight className="size-4" />
                  </IconButton>
                </div>
                <IconButton label="O'chirish" onClick={() => drop(index)} danger>
                  <Trash2 className="size-4" />
                </IconButton>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <label
        className={cn(
          "flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed",
          "border-line px-4 py-6 text-[14px] font-medium text-ink-soft",
          "hover:border-brand hover:text-brand",
          value.length >= max && "pointer-events-none opacity-50",
        )}
      >
        <ImagePlus className="size-5" />
        {value.length ? "Yana rasm qo'shish" : "Rasm tanlash"}
        <input
          ref={input}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={(event) => void add(event.target.files)}
        />
      </label>

      <Hint>
        Telefonda olingan surat bo'ladi. Server rasmni o'zi qayta yozadi va
        kichraytiradi — shuning uchun yuklangandan keyin o'lchami boshqacha
        bo'ladi.
        {busy > 0 ? ` ${busy} rasm yuklanmoqda…` : ""}
      </Hint>
    </div>
  )
}

function IconButton({
  label,
  children,
  onClick,
  disabled,
  danger,
}: {
  label: string
  children: React.ReactNode
  onClick: () => void
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "grid size-7 place-items-center rounded-md text-ink-soft",
        "hover:bg-line-soft hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent",
        danger && "hover:bg-danger/10 hover:text-danger",
      )}
    >
      {children}
    </button>
  )
}
