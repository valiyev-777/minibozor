import * as React from "react"
import { Check, ImagePlus, Trash2 } from "lucide-react"
import { uploadImage } from "@/api/client"
import { Button } from "@/ui/button"
import { Hint, Input, Label } from "@/ui/field"
import { cn } from "@/ui/cn"
import { Thumb } from "@/components/Thumb"
import { t } from "@/lib/labels"

/**
 * A colour, chosen by pointing at it.
 *
 * The field this replaces was two text inputs: a name, and a hex code with
 * `#FFFFFF` in the placeholder. A shopkeeper in Chorsu selling t-shirts does
 * not know that black is `#000000`, has no reason to, and the ones who guessed
 * left the swatch on the customer's page showing whatever `#qora` renders as,
 * which is nothing.
 *
 * So the palette is the input. Sixteen colours clothes and shoes actually come
 * in, named in Uzbek, and clicking one sets the name *and* the code together —
 * they were never two facts. `Boshqa rang` is the escape hatch for the
 * seventeenth: the browser's own colour picker, with the name still typed by
 * hand, because a colour we did not name is a colour we cannot name for them.
 *
 * **The photograph is part of the colour and not optional.** The shopper's
 * page swaps the picture when a swatch is tapped — that is what colours on a
 * card are *for*. A colour with no picture leaves the hero showing the
 * previous one, so somebody taps "black", sees a white shirt, and buys the
 * wrong thing or nothing. The backend refuses a colour without one; this
 * screen says so before the seller gets that far, next to the colour it is
 * about, because a form that fails on submit with a message at the top is a
 * form somebody fills in twice.
 */
export type ColourValue = {
  label: string
  value: string
  image_url: string
}

/**
 * The palette.
 *
 * Sixteen, and each one is a colour goods are actually made in rather than a
 * slice of the spectrum: there is `Bej` and `Bordo` and `Tilla` because
 * clothes come in them, and no cyan because nothing does. The hexes are the
 * pigment, not the screen colour — `Oq` is a warm white and `Qora` is not
 * pure black, because a photographed white shirt next to `#FFFFFF` looks
 * grey and a pure-black circle looks like a hole in the page.
 */
const PALETTE: readonly { label: string; value: string }[] = [
  { label: "Qora", value: "#111113" },
  { label: "Oq", value: "#FAFAF8" },
  { label: "Kulrang", value: "#9AA0A6" },
  { label: "To'q kulrang", value: "#4B5158" },
  { label: "Bej", value: "#E4D3B8" },
  { label: "Jigarrang", value: "#6B4423" },
  { label: "Qizil", value: "#D22B2B" },
  { label: "Bordo", value: "#7B1E28" },
  { label: "Pushti", value: "#E8709F" },
  { label: "To'q sariq", value: "#E2701E" },
  { label: "Sariq", value: "#F2C230" },
  { label: "Yashil", value: "#2E9E5B" },
  { label: "To'q yashil", value: "#1F5E3A" },
  { label: "Ko'k", value: "#2563C9" },
  { label: "To'q ko'k", value: "#1E2F63" },
  { label: "Binafsha", value: "#7A4BC4" },
] as const

export function ColourPicker({
  colour,
  onChange,
  onRemove,
}: {
  colour: ColourValue
  onChange: (next: Partial<ColourValue>) => void
  onRemove?: () => void
}) {
  const [uploading, setUploading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const custom = Boolean(
    colour.value && !PALETTE.some((row) => row.value === colour.value),
  )

  async function pick(files: FileList | null) {
    const file = files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const uploaded = await uploadImage(file)
      onChange({ image_url: uploaded.media_url })
    } catch (raw) {
      setError(raw instanceof Error ? raw.message : t.uploadFailed)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4 rounded-[var(--radius-control)] border border-line p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[length:var(--text-body)] font-medium text-ink">
          {colour.label || t.colorNotChosen}
        </p>
        {onRemove ? (
          <Button
            type="button"
            variant="quiet"
            size="icon"
            aria-label={t.removeColor}
            onClick={onRemove}
          >
            <Trash2 />
          </Button>
        ) : null}
      </div>

      {/* The palette. A wrapping row of circles rather than a select: the
          whole point is seeing them at once, and a dropdown of colour names
          is the text field again with extra steps. */}
      <div>
        <Label>{t.colorLabel}</Label>
        <div className="mt-2 flex flex-wrap gap-2">
          {PALETTE.map((row) => {
            const chosen = colour.value === row.value
            return (
              <button
                key={row.value}
                type="button"
                title={row.label}
                aria-label={row.label}
                aria-pressed={chosen}
                onClick={() => onChange({ label: row.label, value: row.value })}
                className={cn(
                  "relative size-10 rounded-full outline-none transition",
                  "ring-1 ring-inset ring-black/15",
                  "focus-visible:ring-2 focus-visible:ring-brand",
                  chosen && "ring-2 ring-brand ring-offset-2 ring-offset-surface",
                )}
                style={{ backgroundColor: row.value }}
              >
                {chosen ? (
                  <Check
                    className={cn(
                      "absolute inset-0 m-auto size-5",
                      // A tick has to be visible on the colour it is on, and
                      // nothing else about the swatch can say which is which.
                      isLight(row.value) ? "text-ink" : "text-white",
                    )}
                  />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>

      {/* The seventeenth colour. Its own row, and it needs a name typed
          because we cannot name a colour we did not choose. */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={`custom-${colour.label}-${colour.value}`}>
            {t.otherColor}
          </Label>
          <input
            id={`custom-${colour.label}-${colour.value}`}
            type="color"
            value={/^#[0-9a-f]{6}$/i.test(colour.value) ? colour.value : "#888888"}
            onChange={(event) => onChange({ value: event.target.value })}
            className="h-10 w-16 cursor-pointer rounded-[var(--radius-control)]
                       border border-line bg-surface p-1"
          />
        </div>
        {custom ? (
          <div className="min-w-40 flex-1 space-y-1.5">
            <Label htmlFor={`name-${colour.value}`}>{t.colorName}</Label>
            <Input
              id={`name-${colour.value}`}
              value={colour.label}
              onChange={(event) => onChange({ label: event.target.value })}
              placeholder="Xaki"
            />
          </div>
        ) : null}
      </div>

      {/* The photograph, and the sentence that says why it is not optional. */}
      <div>
        <Label>{t.colorPhoto}</Label>
        <div className="mt-2 flex items-start gap-3">
          {colour.image_url ? (
            <div className="relative">
              <Thumb src={colour.image_url} className="size-24" />
              <Button
                type="button"
                variant="quiet"
                size="icon"
                aria-label={t.removePhoto}
                className="absolute -right-2 -top-2 size-7 rounded-full"
                onClick={() => onChange({ image_url: "" })}
              >
                <Trash2 />
              </Button>
            </div>
          ) : (
            <label
              className={cn(
                "flex size-24 cursor-pointer flex-col items-center justify-center gap-1",
                "rounded-[var(--radius-control)] border border-dashed",
                "text-center text-[length:var(--text-micro)]",
                // Dashed and amber while it is missing: this is the one field
                // on the form that will be refused, so it should look unfinished.
                "border-warn/60 bg-warn-soft text-warn-ink hover:bg-warn-soft/70",
              )}
            >
              <ImagePlus className="size-5" />
              {uploading ? "…" : t.addPhoto}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => void pick(event.target.files)}
              />
            </label>
          )}
          <div className="flex-1">
            {error ? (
              <p role="alert" className="text-[length:var(--text-small)] font-medium text-danger">
                {error}
              </p>
            ) : (
              <Hint>{t.colorPhotoHint}</Hint>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Whether a tick on this colour should be dark.
 *
 * Rec. 601 luma rather than a lightness channel, because it weights green the
 * way an eye does: `#F2C230` and `#2563C9` have similar HSL lightness and one
 * of them needs a dark tick.
 */
function isLight(hex: string): boolean {
  const clean = hex.replace("#", "")
  if (clean.length !== 6) return true
  const [r, g, b] = [0, 2, 4].map((at) => parseInt(clean.slice(at, at + 2), 16))
  return (r! * 299 + g! * 587 + b! * 114) / 1000 > 150
}

export { PALETTE }
