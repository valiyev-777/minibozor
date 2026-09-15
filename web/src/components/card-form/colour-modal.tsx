/**
 * §5.2 ·6 — Rang: a list you tick, not a box you spell.
 *
 * This shop's database holds `Oq`, `Qora`, `Ko'k` **and** `Siniy`, which is
 * one blue written twice and counted as two colours by every filter, every
 * photograph group and the publishing gate that wants a picture per colour.
 * The cure is not validation at the text box — it is not having a text box.
 *
 * **"+ yangi rang" writes to the palette, not to the card.** A colour the shop
 * has not sold before is a real event and it happens at the bench with a sack
 * open. If adding one needed the owner, nobody would wait; they would type it
 * into the nearest box that accepts it, which is how the four spellings above
 * happened. The server guards this door as `CatalogReader` for that exact
 * reason, so the next person picks the colour instead of retyping it.
 */

import { Loader2, Plus, Search } from "lucide-react"
import { useMemo, useState } from "react"

import { Swatch } from "@/components/card-form/bits"
import { Problem } from "@/components/page"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/cn"
import { useAddColour, useColours } from "@/lib/queries"

export function ColourModal({
  open,
  onOpenChange,
  /** The colours this card already comes in, by name as the variants hold it. */
  chosen,
  onDone,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  chosen: string[]
  /** The full list after the tick — names, in palette order. */
  onDone: (colours: string[]) => void
}) {
  const palette = useColours()
  const add = useAddColour()
  const [ticked, setTicked] = useState<string[]>(chosen)
  const [query, setQuery] = useState("")
  const [adding, setAdding] = useState("")

  // Re-seeded whenever the modal opens, so a cancelled tick is really
  // cancelled rather than remembered into the next opening.
  const [openedWith, setOpenedWith] = useState<string | null>(null)
  const key = chosen.join("\u0000")
  if (open && openedWith !== key) {
    setOpenedWith(key)
    setTicked(chosen)
    setQuery("")
  }
  if (!open && openedWith !== null) setOpenedWith(null)

  const rows = palette.data ?? []

  // Colours already on the card that the palette has never heard of — a card
  // written before the palette existed. They still need a row, or ticking
  // anything at all would silently drop them off the card.
  const strays = chosen.filter(
    (name) => !rows.some((row) => row.name.toLowerCase() === name.toLowerCase()),
  )

  const shown = useMemo(() => {
    const wanted = query.trim().toLowerCase()
    const all = [
      ...strays.map((name) => ({ id: -1, slug: name, name, hex: "" })),
      ...rows,
    ]
    return wanted ? all.filter((row) => row.name.toLowerCase().includes(wanted)) : all
  }, [rows, strays, query])

  function toggle(name: string) {
    setTicked((was) =>
      was.includes(name) ? was.filter((one) => one !== name) : [...was, name],
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rang</DialogTitle>
        </DialogHeader>

        <DialogBody className="space-y-3">
          <label className="relative block">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-faint" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Rang qidirish"
              aria-label="Rang qidirish"
              className="pl-9"
            />
          </label>

          {palette.isLoading ? (
            <p className="text-micro text-ink-soft">Palitra yuklanmoqda…</p>
          ) : null}

          <ul className="space-y-0.5">
            {shown.map((row) => {
              const on = ticked.includes(row.name)
              return (
                <li key={`${row.id}-${row.slug}`}>
                  <label
                    className={cn(
                      "flex h-control cursor-pointer items-center gap-3 rounded-control px-2 text-small hover:bg-line-soft",
                      on && "bg-brand-soft",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(row.name)}
                      className="size-4 accent-brand"
                    />
                    <Swatch hex={row.hex} />
                    <span className="min-w-0 flex-1">{row.name}</span>
                    {row.id === -1 ? (
                      <span className="text-micro text-ink-faint">palitrada yo'q</span>
                    ) : null}
                  </label>
                </li>
              )
            })}
          </ul>

          {shown.length === 0 && !palette.isLoading ? (
            <p className="text-micro text-ink-soft">Bunday rang topilmadi.</p>
          ) : null}

          {/* Adding here and not on another screen, for the same reason the
              category form takes a new category: somebody standing at a bench
              with goods of a new colour will not go and find a settings page. */}
          <form
            className="flex items-end gap-2 border-t border-line pt-3"
            onSubmit={(event) => {
              event.preventDefault()
              const wanted = adding.trim()
              if (!wanted) return
              add.mutate(
                { name: wanted },
                {
                  onSuccess: (made) => {
                    setAdding("")
                    setTicked((was) =>
                      was.includes(made.name) ? was : [...was, made.name],
                    )
                  },
                },
              )
            }}
          >
            <label className="min-w-0 flex-1">
              <span className="mb-1 block text-micro text-ink-soft">Yangi rang</span>
              <Input
                value={adding}
                onChange={(event) => setAdding(event.target.value)}
                placeholder="Feruza"
                aria-label="Yangi rang"
              />
            </label>
            <Button
              type="submit"
              variant="secondary"
              className="gap-1"
              disabled={!adding.trim() || add.isPending}
            >
              {add.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}
              Qo'shish
            </Button>
          </form>

          <Problem error={palette.error || add.error} />
        </DialogBody>

        <DialogFooter showCloseButton>
          <Button
            type="button"
            onClick={() => {
              // Back into palette order, so the card's colours are always in
              // the order the picker draws them rather than the order somebody
              // happened to tick.
              const order = new Map(rows.map((row, at) => [row.name, at]))
              onDone(
                [...ticked].sort(
                  (one, two) =>
                    (order.get(one) ?? Number.MAX_SAFE_INTEGER) -
                    (order.get(two) ?? Number.MAX_SAFE_INTEGER),
                ),
              )
              onOpenChange(false)
            }}
          >
            OK
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
