/**
 * §5.2 ·6 — colour and size, asked directly.
 *
 * The brief drew this as a chip-picker: "+ Xususiyat tanlash" opening a list,
 * a chip per chosen attribute. Built that way, the owner called it "juda
 * yomon", and he was right about why: there are exactly two attributes that do
 * anything, and hiding two questions behind a third button is a step that
 * exists only to be clicked through. So both questions are simply on the
 * screen, each with its answer showing on the control itself.
 *
 * - **Rang** opens the palette modal. Stored as which colours the variant grid
 *   carries — there is no `product_attributes` table and there should not be
 *   one, because a colour that is not on a variant is a colour nothing can be
 *   sold in.
 * - **O'lcham** is `products.size_system_id`, written through its own door.
 *   Naming a system turns the size boxes into that system's values, so `43` is
 *   offered rather than typed and a European 43 never lands on the same card
 *   as a UK 9.
 *
 * The systems are grouped by `family`; a chip is labelled by its `scale`
 * (EUR / UK / US) when it has one, and by the run of its values (`S–XXXL`)
 * when it does not — the first draft printed `run.name` there, which drew
 * "Kiyim  Kiyim" and "Kamar  Kamar", a label stuttering at its own chip.
 *
 * **Sizeless is a chosen answer, not an empty box.** §6.3 says a card is sized
 * or sizeless and never both, so *O'lchamsiz* is one of the chips and it
 * writes `null` deliberately.
 */

import { Loader2, X } from "lucide-react"
import { useState } from "react"

import { Swatch } from "@/components/card-form/bits"
import { ColourModal } from "@/components/card-form/colour-modal"
import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { bySize, tidySize } from "@/lib/format"
import { useColours, useSizeSystems } from "@/lib/queries"
import type { SizeSystem } from "@/lib/types"

/** `S–XXXL`, `42–58`: what a scale-less system offers, said by its ends. */
function runOf(values: string[]): string {
  if (!values.length) return "—"
  return values.length === 1 ? values[0] : `${values[0]}–${values[values.length - 1]}`
}

export function Attributes({
  colours,
  onColours,
  system,
  sizeless,
  onSystem,
  sizes,
  onSizes,
  saving = false,
  error,
}: {
  colours: string[]
  onColours: (colours: string[]) => void
  /** What this card is numbered in, or `null` when nothing is named yet. */
  system: SizeSystem | null
  /** The card has said it has no sizes at all — a cap, a bag. */
  sizeless: boolean
  onSystem: (slug: string | null) => void
  sizes: string[]
  onSizes: (sizes: string[]) => void
  saving?: boolean
  error?: unknown
}) {
  const systems = useSizeSystems()
  const palette = useColours()
  const [picking, setPicking] = useState(false)

  const hex = new Map((palette.data ?? []).map((row) => [row.name, row.hex]))

  // Grouped in the server's order, which is the order the picker draws them.
  const families = new Map<string, SizeSystem[]>()
  for (const one of systems.data ?? []) {
    const family = one.family || one.name
    const held = families.get(family)
    if (held) held.push(one)
    else families.set(family, [one])
  }

  return (
    <div className="space-y-4">
      {/* ------------------------------------------------------------- rang */}
      <div>
        <p className="mb-1.5 text-small font-medium">Rang</p>
        <div className="flex flex-wrap items-center gap-2">
          {colours.length ? (
            <span className="flex h-control items-center rounded-control border border-line">
              <button
                type="button"
                aria-label="Ranglarni tanlash"
                onClick={() => setPicking(true)}
                className={cn(
                  "flex h-full items-center gap-2 rounded-s-control ps-3 pe-2 text-small",
                  "transition-colors hover:bg-line-soft",
                  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
                )}
              >
                <span className="flex items-center gap-1">
                  {colours.map((name) => (
                    <Swatch key={name} hex={hex.get(name)} />
                  ))}
                </span>
                {/* The names, not only the dots: three swatches of near-white
                    are unreadable as dots alone. */}
                <span className="font-medium">
                  {colours.length > 3
                    ? `${colours.slice(0, 3).join(" · ")} +${colours.length - 3}`
                    : colours.join(" · ")}
                </span>
              </button>
              <button
                type="button"
                aria-label="Ranglarni o'chirish"
                onClick={() => onColours([])}
                className={cn(
                  "flex h-full items-center rounded-e-control ps-1 pe-2.5 text-ink-faint",
                  "transition-colors hover:text-danger",
                  "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
                )}
              >
                <X className="size-3.5" />
              </button>
            </span>
          ) : (
            <Button type="button" variant="secondary" onClick={() => setPicking(true)}>
              Ranglarni tanlash
            </Button>
          )}
          {colours.length ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => setPicking(true)}>
              O'zgartirish
            </Button>
          ) : null}
          {saving ? <Loader2 className="size-4 animate-spin text-ink-faint" /> : null}
        </div>
      </div>

      {/* ---------------------------------------------------------- o'lcham */}
      <div className="space-y-2">
        <p className="text-small font-medium">O'lcham</p>
        {[...families].map(([family, runs]) => {
          // One system, no scale: the family label and the chip would be the
          // same word twice, so the chip carries the whole row alone.
          const alone = runs.length === 1 && !runs[0].scale
          return (
            <div key={family} className="flex flex-wrap items-center gap-1.5">
              {/* The lone chip still gets the spacer, so every chip in the
                  grid starts on the same column. */}
              <span className="w-40 shrink-0 text-small text-ink-soft">
                {alone ? "" : family}
              </span>
              {runs.map((run) => (
                <button
                  key={run.slug}
                  type="button"
                  onClick={() => onSystem(run.slug)}
                  className={cn(
                    "h-control rounded-control border border-line px-3 text-small transition-colors hover:bg-line-soft",
                    system?.slug === run.slug &&
                      "border-brand bg-brand-soft font-medium text-brand-deep",
                  )}
                >
                  {alone ? family : run.scale || runOf(run.values)}
                </button>
              ))}
            </div>
          )
        })}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="w-40 shrink-0 text-small text-ink-soft">Yoki</span>
          <button
            type="button"
            onClick={() => {
              onSizes([])
              // Back to "nothing named" is the same write as sizeless, and the
              // two are told apart by whether the card has sizes on it.
              onSystem(null)
            }}
            className={cn(
              "h-control rounded-control border border-line px-3 text-small transition-colors hover:bg-line-soft",
              sizeless && "border-brand bg-brand-soft font-medium text-brand-deep",
            )}
          >
            O'lchamsiz — bu tovarda o'lcham yo'q
          </button>
        </div>
        <Problem error={systems.error} />
      </div>

      {/* The values of the named system, offered rather than typed. A size
          already on the card that the system does not list is still drawn —
          a 47 booked in before the list was shortened is on a shelf, and a
          form that stops showing it is a form that quietly un-picks it. */}
      {system ? (
        <div>
          <p className="mb-1.5 text-small font-medium">
            {system.name} — <span className="font-normal text-ink-soft">kartada bor o'lchamlar</span>
          </p>
          <div className="flex flex-wrap gap-1.5">
            {[...new Set([...system.values, ...sizes])]
              .map(tidySize)
              .sort(bySize)
              .map((size) => {
                const on = sizes.includes(size)
                return (
                  <button
                    key={size}
                    type="button"
                    onClick={() =>
                      onSizes(
                        on ? sizes.filter((one) => one !== size) : [...sizes, size],
                      )
                    }
                    className={cn(
                      "h-control min-w-11 rounded-control border border-line px-2 text-small tabular transition-colors hover:bg-line-soft",
                      on && "border-brand bg-brand font-medium text-brand-ink",
                    )}
                  >
                    {size}
                  </button>
                )
              })}
          </div>
        </div>
      ) : null}

      <Problem error={error} />

      <ColourModal
        open={picking}
        onOpenChange={setPicking}
        chosen={colours}
        onDone={onColours}
      />
    </div>
  )
}
