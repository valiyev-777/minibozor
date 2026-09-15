/**
 * §5.2 ·6 — the defined attributes: at most five, each a chip you can take off.
 *
 * Two of them do real work and the rest of the list is the shop's to grow.
 *
 * - **Rang** opens the palette modal. It is stored as which colours the
 *   variant grid carries — there is no `product_attributes` table and there
 *   should not be one, because a colour that is not on a variant is a colour
 *   nothing can be sold in.
 * - **An o'lcham system** is `products.size_system_id`, written through its own
 *   door. Naming one turns the size boxes into that system's values, so `43`
 *   is offered rather than typed and a European 43 never lands on the same
 *   card as a UK 9.
 *
 * The systems are grouped by `family`, which is why the server sends `family`
 * and `scale` apart from `name`: *Erkaklar poyabzali* is drawn once with
 * EUR / UK / US / RUS under it, rather than as four unrelated strings that
 * happen to share a prefix. Splitting the display name on a space would work
 * until the first system called `Kamar`.
 *
 * **Sizeless is a chosen answer, not an empty box.** §6.3 says a card is sized
 * or sizeless and never both, so *O'lchamsiz* is one of the things you can
 * pick here and it writes `null` deliberately.
 */

import { Loader2, Plus, X } from "lucide-react"
import { useState } from "react"

import { Swatch } from "@/components/card-form/bits"
import { ColourModal } from "@/components/card-form/colour-modal"
import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import { bySize, tidySize } from "@/lib/format"
import { useColours, useSizeSystems } from "@/lib/queries"
import type { SizeSystem } from "@/lib/types"

/** §5.2 ·6: "the defined attributes, at most five". */
const MOST = 5

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
  const [offering, setOffering] = useState(false)

  const hex = new Map((palette.data ?? []).map((row) => [row.name, row.hex]))

  // Grouped in the server's order, which is the order the picker draws them.
  const families = new Map<string, SizeSystem[]>()
  for (const one of systems.data ?? []) {
    const family = one.family || one.name
    const held = families.get(family)
    if (held) held.push(one)
    else families.set(family, [one])
  }

  const chosen = [
    colours.length ? "rang" : null,
    system ? system.slug : sizeless ? "o-lchamsiz" : null,
  ].filter(Boolean)
  const full = chosen.length >= MOST

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* The chip is the way back into the palette, not only a receipt for
            it. Adding a seventh colour used to mean taking the chip off — and
            `onColours([])` on a card with a live variant grid clears every
            colour it sells in. Two sibling buttons rather than one inside the
            other: a chip that opens the picker and a cross that empties it are
            two acts, and only one of them should ever happen by accident. */}
        {colours.length ? (
          <span className="flex h-control items-center rounded-control border border-line text-small">
            <button
              type="button"
              aria-label="Ranglarni tanlash"
              onClick={() => setPicking(true)}
              className={cn(
                "flex h-full items-center gap-2 rounded-s-control ps-2 pe-1",
                "transition-colors hover:bg-line-soft",
                "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
              )}
            >
              <span className="font-medium">Rang</span>
              <span className="flex items-center gap-1">
                {colours.map((name) => (
                  <Swatch key={name} hex={hex.get(name)} />
                ))}
              </span>
            </button>
            <button
              type="button"
              aria-label="Rangni o'chirish"
              onClick={() => onColours([])}
              className={cn(
                "flex h-full items-center rounded-e-control ps-1 pe-2 text-ink-faint",
                "transition-colors hover:text-danger",
                "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand",
              )}
            >
              <X className="size-3.5" />
            </button>
          </span>
        ) : null}

        {system || sizeless ? (
          <span className="flex h-control items-center gap-2 rounded-control border border-line px-2 text-small">
            <span className="font-medium">{system ? system.name : "O'lchamsiz"}</span>
            <button
              type="button"
              aria-label="O'lcham tizimini o'chirish"
              onClick={() => {
                onSizes([])
                // Back to "nothing named" is the same write as sizeless, and
                // the two are told apart by whether the card has sizes on it.
                onSystem(null)
              }}
              className="text-ink-faint hover:text-danger"
            >
              <X className="size-3.5" />
            </button>
          </span>
        ) : null}

        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-1"
          disabled={full}
          onClick={() => setOffering((was) => !was)}
        >
          <Plus className="size-4" />
          Xususiyat tanlash
        </Button>
        {saving ? <Loader2 className="size-4 animate-spin text-ink-faint" /> : null}
      </div>

      {offering ? (
        <div className="space-y-3 rounded-control border border-line p-3">
          <div>
            <p className="mb-1 text-micro text-ink-soft">Rang</p>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setPicking(true)
                setOffering(false)
              }}
            >
              Ranglarni tanlash
            </Button>
          </div>

          <div className="space-y-2">
            <p className="text-micro text-ink-soft">O'lcham tizimi</p>
            {[...families].map(([family, runs]) => (
              <div key={family} className="flex flex-wrap items-center gap-1">
                <span className="mr-1 w-full text-small sm:w-auto">{family}</span>
                {runs.map((run) => (
                  <button
                    key={run.slug}
                    type="button"
                    onClick={() => {
                      onSystem(run.slug)
                      setOffering(false)
                    }}
                    className={cn(
                      "h-control-sm rounded-control border border-line px-2.5 text-micro hover:bg-line-soft",
                      system?.slug === run.slug && "border-brand bg-brand-soft",
                    )}
                  >
                    {run.scale || run.name}
                  </button>
                ))}
              </div>
            ))}
            <button
              type="button"
              onClick={() => {
                onSizes([])
                onSystem(null)
                setOffering(false)
              }}
              className="h-control-sm rounded-control border border-line px-2.5 text-micro hover:bg-line-soft"
            >
              O'lchamsiz — bu tovarda o'lcham yo'q
            </button>
          </div>

          <Problem error={systems.error} />
        </div>
      ) : null}

      {/* The values of the named system, offered rather than typed. A size
          already on the card that the system does not list is still drawn —
          a 47 booked in before the list was shortened is on a shelf, and a
          form that stops showing it is a form that quietly un-picks it. */}
      {system ? (
        <div>
          <p className="mb-1 text-micro text-ink-soft">
            {system.name} — bu kartada bor o'lchamlar
          </p>
          <div className="flex flex-wrap gap-1">
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
                      "h-control min-w-11 rounded-control border border-line px-2 text-small tabular hover:bg-line-soft",
                      on && "border-brand bg-brand text-brand-ink",
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
