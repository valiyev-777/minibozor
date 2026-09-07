import { Palette, Plus, Trash2 } from "lucide-react"
import type { Picked } from "@/pages/product/Images"
import { Hint, Input, Label } from "@/components/ui/field"
import { Button } from "@/components/ui/button"
import { cn, mediaSrc } from "@/lib/utils"

export type SizeRow = { key: string; label: string; quantity: string }
export type ColorRow = {
  key: string
  label: string
  value: string
  /** Which of the uploaded pictures shows this colour. */
  imageUrl: string | null
  sizes: SizeRow[]
}

/** Five sizes, because a t-shirt has five and typing them out is not the job. */
const COMMON_SIZES = ["S", "M", "L", "XL", "XXL"]

export function newColor(): ColorRow {
  return {
    key: `c${Date.now()}${Math.random().toString(36).slice(2, 6)}`,
    label: "",
    value: "",
    imageUrl: null,
    sizes: COMMON_SIZES.map((label, index) => ({
      key: `s${Date.now()}${index}`,
      label,
      quantity: "",
    })),
  }
}

/**
 * The grid: a colour, the sizes it comes in, and how many of each is coming.
 *
 * **A size belongs to a colour, not to the product.** One row per colour per
 * size is what makes "the black M has run out" sayable — if the sizes sat
 * beside the colours instead of under them, the shelf would be counted twice
 * over and the page would go on offering a black M out of the blue ones.
 *
 * **The quantity is a declaration, not a stock figure.** It becomes the
 * declared amount on a batch the warehouse is going to count. Nothing a seller
 * types here reaches a stock column: the shelf moves when somebody opens the
 * box. So the label says "kelayotgan soni" and not "qoldiq".
 *
 * Either every colour has sizes or none does, and the backend refuses the
 * mixture — so this offers sizes on every colour and lets a seller clear them
 * all, rather than letting them build something that will be rejected on save.
 */
export function Variants({
  value,
  onChange,
  images,
}: {
  value: ColorRow[]
  onChange: (next: ColorRow[]) => void
  images: Picked[]
}) {
  const ready = images.filter((i) => i.mediaUrl)

  function patch(key: string, change: Partial<ColorRow>) {
    onChange(value.map((c) => (c.key === key ? { ...c, ...change } : c)))
  }

  function patchSize(colorKey: string, sizeKey: string, change: Partial<SizeRow>) {
    onChange(
      value.map((c) =>
        c.key === colorKey
          ? {
              ...c,
              sizes: c.sizes.map((s) => (s.key === sizeKey ? { ...s, ...change } : s)),
            }
          : c,
      ),
    )
  }

  const total = value.reduce(
    (sum, c) => sum + c.sizes.reduce((n, s) => n + (Number(s.quantity) || 0), 0),
    0,
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Label>Ranglar va razmerlar</Label>
        <Hint>
          Jami kelayotgan: <span className="font-semibold text-ink">{total}</span> dona
        </Hint>
      </div>

      <div className="space-y-4">
        {value.map((colour, index) => (
          <div key={colour.key} className="rounded-xl border border-line bg-surface p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_10rem]">
                <div className="space-y-1.5">
                  <Label htmlFor={`c-${colour.key}`}>Rang nomi</Label>
                  <Input
                    id={`c-${colour.key}`}
                    value={colour.label}
                    placeholder="Oq"
                    onChange={(e) => patch(colour.key, { label: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor={`v-${colour.key}`}>Rang kodi</Label>
                  <div className="flex items-center gap-2">
                    <span
                      className="size-9 shrink-0 rounded-lg border border-line"
                      style={{ background: colour.value || "transparent" }}
                    />
                    <Input
                      id={`v-${colour.key}`}
                      value={colour.value}
                      placeholder="#FFFFFF"
                      onChange={(e) => patch(colour.key, { value: e.target.value })}
                    />
                  </div>
                </div>
              </div>
              {value.length > 1 ? (
                <button
                  type="button"
                  aria-label="Rangni o'chirish"
                  onClick={() => onChange(value.filter((c) => c.key !== colour.key))}
                  className="mt-6 grid size-8 place-items-center rounded-md text-ink-soft hover:bg-danger/10 hover:text-danger"
                >
                  <Trash2 className="size-4" />
                </button>
              ) : null}
            </div>

            {/* Which photograph shows this colour. A colour is chosen by
                looking at the thing, not at a hex circle. */}
            {ready.length ? (
              <div className="mb-3 space-y-1.5">
                <Label>Bu rangdagi rasm</Label>
                <div className="flex flex-wrap gap-2">
                  {ready.map((picture) => (
                    <button
                      key={picture.key}
                      type="button"
                      onClick={() =>
                        patch(colour.key, {
                          imageUrl:
                            colour.imageUrl === picture.mediaUrl ? null : picture.mediaUrl,
                        })
                      }
                      className={cn(
                        "overflow-hidden rounded-lg border-2",
                        colour.imageUrl === picture.mediaUrl
                          ? "border-brand"
                          : "border-transparent hover:border-line",
                      )}
                    >
                      <img
                        src={mediaSrc(picture.mediaUrl!)}
                        alt=""
                        className="size-14 object-cover"
                      />
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-1.5">
              <Label>Razmerlar va kelayotgan soni</Label>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {colour.sizes.map((size) => (
                  <div key={size.key} className="flex items-center gap-2">
                    <Input
                      value={size.label}
                      placeholder="Razmer"
                      aria-label="Razmer"
                      className="w-24"
                      onChange={(e) =>
                        patchSize(colour.key, size.key, { label: e.target.value })
                      }
                    />
                    <Input
                      value={size.quantity}
                      inputMode="numeric"
                      placeholder="0"
                      aria-label="Kelayotgan soni"
                      onChange={(e) =>
                        patchSize(colour.key, size.key, {
                          quantity: e.target.value.replace(/[^0-9]/g, ""),
                        })
                      }
                    />
                    <button
                      type="button"
                      aria-label="Razmerni o'chirish"
                      onClick={() =>
                        patch(colour.key, {
                          sizes: colour.sizes.filter((s) => s.key !== size.key),
                        })
                      }
                      className="grid size-8 shrink-0 place-items-center rounded-md text-ink-soft hover:bg-danger/10 hover:text-danger"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                ))}
              </div>
              <Button
                type="button"
                variant="quiet"
                size="sm"
                onClick={() =>
                  patch(colour.key, {
                    sizes: [
                      ...colour.sizes,
                      {
                        key: `s${Date.now()}${colour.sizes.length}`,
                        label: "",
                        quantity: "",
                      },
                    ],
                  })
                }
              >
                <Plus className="size-4" />
                Razmer qo'shish
              </Button>
            </div>

            {index === 0 ? (
              <Hint className="mt-3">
                Soni — omborga <em>kelayotgan</em> dona. Qoldiq ombor sanab
                qabul qilgandan keyin paydo bo'ladi.
              </Hint>
            ) : null}
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="quiet"
        onClick={() => onChange([...value, newColor()])}
      >
        <Palette className="size-4" />
        Rang qo'shish
      </Button>
    </div>
  )
}
